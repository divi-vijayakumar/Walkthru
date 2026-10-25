"""Itemizer: words -> KB tasks -> items + facts (ladders) -> one next_action -> deterministic price. The LLM never prices."""
import re
from core.db import db, iso
from core.quotes import latest_quote, save_quote
from pricing.engine import r500, is_rush, margin_discount_cap, DEPOSIT_PCT, RUSH_SURCHARGE
from itemizer.kb import load_kb
from itemizer import llm

TIERS = {"refresh": 0, "standard": 1, "premium": 2}
UNKNOWN = {"unknown", "not sure", "don't know", "dont know", "no idea", "", None}
MAX_SHOWS = 3
YES = {"yes", "yeah", "yep", "right", "correct", "that's right", "true"}
NO = {"no", "nope", "wrong", "not right", "incorrect"}


def detect_room(said, current):
    t = (said or "").lower()
    for room, words in (("bathroom", ["bath", "shower", "toilet", "vanity"]), ("kitchen", ["kitchen"]),
                        ("living room", ["living room", "family room"]), ("bedroom", ["bedroom"])):
        if any(w in t for w in words):
            return room
    return current


def fact_key(name, scope, item_id, room):
    return f"{name}@{item_id if scope == 'item' else room if scope == 'room' else 'job'}"


def steps(a, b, area):
    a *= 2.5
    return (a * b * 2.5 if b else a * a if area else a), "steps"


def measure(value, area=False):
    """Returns (sq ft or ft or count, method) from a measurement answer. A step is about 2.5 ft."""
    if isinstance(value, (int, float)):
        return float(value), "known"
    if isinstance(value, dict):
        m = value.get("method")
        if m == "tiles":
            return value["x"] * value["y"] * (value.get("tile_in", 12) / 12.0) ** 2, "tiles"
        if m == "steps":
            return steps(value["a"], value.get("b"), area)
        if m == "tape":
            return value["a"] * value.get("b", 1), "tape"
    t = str(value).lower()
    if "step" in t:
        nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", t)]
        if nums:
            return steps(nums[0], nums[1] if len(nums) > 1 else None, area)
    tm = re.search(r"(\d+)\s*(?:tiles?\s*)?(?:by|x)\s*(\d+)(?:\s*tiles?)?(?:\s*(?:at|of)\s*(\d+)\s*(?:in|inch))?", t)
    if tm and ("tile" in t or tm[3]):
        return int(tm[1]) * int(tm[2]) * ((int(tm[3] or 12)) / 12.0) ** 2, "tiles"
    if tm:
        return float(tm[1]) * float(tm[2]), "tape"
    n = re.search(r"\d+(\.\d+)?", t)
    return (float(n[0]), "known") if n else (None, None)


class Itemizer:
    def __init__(self, session, kb):
        self.s, (self.tasks, self.kbf, self.rules) = session, kb

    # --- facts ---------------------------------------------------------------
    def facts_named(self, name):
        return [f for f in self.s["facts"] if f["name"] == name]

    def value(self, name, item_id=None):
        fs = [f for f in self.facts_named(name) if f["state"] in ("resolved", "assumed")]
        if item_id:
            fs = [f for f in fs if f.get("item_id") in (item_id, None)] or fs
        return fs[0]["value"] if fs else None

    def channel(self, f):
        return f["ladder"][f["idx"]] if f["idx"] < len(f["ladder"]) else "assume"

    def enter(self, f, camera_on):
        while True:
            ch = self.channel(f)
            if ch == "assume":
                f.update(state="assumed", value=self.kbf[f["name"]]["default"], basis="assumed", confidence=0.5)
                return
            if ch == "show" and not (camera_on and self.s["shows_used"] < MAX_SHOWS):
                f["idx"] += 1
                continue
            f["state"] = "waiting_on_camera" if ch == "camera" else "open"
            if ch == "camera":
                f["attempts"].append({"channel": "camera", "goal": self.kbf[f["name"]]["goals"], "at": iso()})
            return

    def advance(self, f, camera_on, why):
        f["attempts"].append({"channel": self.channel(f), "result": why, "at": iso()})
        f["idx"] += 1
        self.enter(f, camera_on)

    def resolve(self, f, value, basis, confidence=1.0, evidence=None):
        f.update(state="resolved", value=value, basis=basis, confidence=confidence, evidence=evidence or {})

    def open_fact(self, name, item, camera_on):
        d = self.kbf[name]
        fid = fact_key(name, d["scope"], item["item_id"], item["room"])
        if any(f["fact_id"] == fid for f in self.s["facts"]):
            return
        f = {"fact_id": fid, "name": name, "scope": d["scope"], "item_id": item["item_id"] if d["scope"] == "item" else None,
             "room": item["room"], "ladder": d["ladder"], "idx": 0, "value": None, "confidence": None, "basis": None,
             "evidence": {}, "state": "open", "attempts": []}
        self.s["facts"].append(f)
        self.enter(f, camera_on)

    # --- items and rules -----------------------------------------------------
    def live_items(self):
        return [i for i in self.s["items"] if i["status"] != "removed"]

    def has(self, task_id):
        return any(i["task_id"] == task_id for i in self.live_items())

    def add_item(self, task_id, said, camera_on, rule=None, basis="said", evidence=None):
        if self.has(task_id):
            return None
        n = len(self.s["items"]) + 1
        item = {"item_id": f"it{n}", "task_id": task_id, "room": self.s["room"], "said": said, "status": "proposed",
                "label": self.tasks[task_id]["label"], "rule_id": rule, "basis": basis, "evidence": evidence or {}}
        self.s["items"].append(item)
        for name in self.tasks[task_id]["facts"]:
            self.open_fact(name, item, camera_on)
        for name in ("finish_level", "water_damage", "timeline"):
            self.open_fact(name, item, camera_on)
        return item

    def rule_ok(self, r):
        if not all(self.has(t) for t in r["has"]) or any(self.has(t) for t in r["lacks"]):
            return False
        for name, vals in r["facts"].items():
            if str(self.value(name)).lower() not in [str(v) for v in vals]:
                return False
        for name, limit in r["lt"].items():
            v = self.value(name)
            if v is None or float(v) >= limit:
                return False
        return True

    def apply_rules(self, camera_on):
        added = []
        for _ in range(3):
            for item in [i for i in self.live_items() if i.get("rule_id")]:
                if not any(r["rule_id"] == item["rule_id"] and self.rule_ok(r) for r in self.rules):
                    item["status"] = "removed"
            for r in self.rules:
                if self.rule_ok(r) and not self.has(r["add"]):
                    src = [f for n in r["facts"] for f in self.facts_named(n) if f["state"] in ("resolved", "assumed")]
                    basis = src[0]["basis"] if src else "said"
                    it = self.add_item(r["add"], "", camera_on, r["rule_id"], basis, src[0]["evidence"] if src else {})
                    if it:
                        added.append(it)
        return added

    def apply_answers(self, answers, camera_on):
        for name, val in (answers or {}).items():
            for f in self.facts_named(name):
                if f["state"] in ("resolved",) and f["basis"] in ("seen", "measured"):
                    continue
                if f.get("pending_confirm") is not None and isinstance(val, str):
                    v, seen = val.strip().lower().rstrip(".!"), f["pending_confirm"]
                    f["pending_confirm"] = None
                    if v in YES:
                        self.resolve(f, seen, "seen", 1.0, f["evidence"])
                        continue
                    if v in NO:
                        self.advance(f, camera_on, "rejected")
                        continue
                if isinstance(val, str) and val.strip().lower() in UNKNOWN or val is None:
                    if f["state"] in ("open", "asked"):
                        self.advance(f, camera_on, "unknown")
                    continue
                if self.kbf[name].get("numeric"):
                    num, method = measure(val, "sq ft" in self.kbf[name]["label"])
                    if num is None:
                        continue
                    self.resolve(f, round(num, 1), "measured" if method in ("tiles", "steps", "tape") else "said", evidence={"utterance": str(val), "method": method})
                else:
                    self.resolve(f, str(val).strip().lower(), "said", evidence={"utterance": str(val)})

    # --- next action -----------------------------------------------------------
    def next_action(self, camera_on):
        for _ in range(4):
            open_f = [f for f in self.s["facts"] if f["state"] in ("open", "asked")]
            conf = [f for f in open_f if f.get("pending_confirm") is not None]
            if conf:
                f = conf[0]
                return "confirm", f"I can see {self.kbf[f['name']]['label']}: {f['pending_confirm']}. Is that right?", f
            missed = [f for f in open_f if any(a.get("result") in ("not_found", "ambiguous") for a in f["attempts"])]
            for ch, kind, pool in (("show", "show", missed), ("ask", "ask", open_f), ("show", "show", open_f), ("measure", "measure", open_f)):
                for f in pool:
                    if self.channel(f) != ch:
                        continue
                    if ch == "show" and not (camera_on and self.s["shows_used"] < MAX_SHOWS):
                        self.advance(f, camera_on, "camera off")
                        continue
                    if ch == "show":
                        self.s["shows_used"] += 1
                        f["state"] = "waiting_on_camera"
                    else:
                        f["state"] = "asked"
                    d = self.kbf[f["name"]]
                    f["attempts"].append({"channel": ch, "at": iso()})
                    return kind, d["show"] if ch in ("show", "measure") else d["question"], f
            waiting = [f for f in self.s["facts"] if f["state"] == "waiting_on_camera"]
            if not waiting:
                break
            for f in waiting:  # Percia is not wired yet: treat the camera as unavailable
                self.advance(f, camera_on, "camera unavailable")
        return "price", "", None

    # --- price -----------------------------------------------------------------
    def price(self, contractor):
        tier = TIERS.get(str(self.value("finish_level") or "standard"), 1)
        lines, trades = [], set()
        for it in self.live_items():
            task = self.tasks[it["task_id"]]
            trades |= {t for t in task["tags"] if t in ("plumbing", "electrical", "gas", "structural", "shower")}
            amt = 0.0
            for c in task["price"]:
                if any(str(self.value(n, it["item_id"])).lower() not in [str(v) for v in vals] for n, vals in (c.get("when") or {}).items()):
                    continue
                base = c["tiers"][tier] if "tiers" in c else c["amount"]
                qty = float(self.value(c["qty"], it["item_id"]) or 0) if c.get("qty") else 1
                amt += base * qty * c.get("mult", 1)
            used = [f for f in self.s["facts"] if f.get("item_id") == it["item_id"] or (f["name"] in {c.get("qty") for c in task["price"]})]
            lines.append({"key": it["item_id"], "label": it["label"], "amount": int(round(amt)), "basis": it["basis"],
                          "evidence": it["evidence"], "facts": [{"name": f["name"], "value": f["value"], "basis": f["basis"]} for f in used]})
        rooms = {i["room"] for i in self.live_items()}
        if lines:
            lines.append({"key": "protection", "label": "Protection and cleanup", "amount": 450 * len(rooms), "basis": "assumed", "evidence": {}})
            if any("removal" in self.tasks[i["task_id"]]["tags"] for i in self.live_items()):
                lines.append({"key": "demolition", "label": "Demolition and haul-away", "amount": 650 if len(rooms) == 1 else 1200, "basis": "assumed", "evidence": {}})
            if trades:
                lines.append({"key": "permit", "label": f"Permit ({', '.join(sorted(trades))})", "amount": 450 * len(trades), "basis": "assumed", "evidence": {}})
        total = sum(line["amount"] for line in lines)
        lev = self.s["levers"]
        if is_rush(self.value("timeline")):
            rush = int(round(total * RUSH_SURCHARGE))
            lines.append({"key": "rush", "label": "Rush schedule (8%)", "amount": rush, "basis": "said", "evidence": {}})
            total += rush
        disc = min(lev.get("disc", 0), contractor["max_discount_pct"], margin_discount_cap(contractor["min_margin_pct"]))
        if disc:
            d = int(round(total * disc / 100.0))
            lines.append({"key": "discount", "label": f"Discount ({disc}%)", "amount": -d, "basis": "said", "evidence": {}})
            total -= d
        assumed = [f for f in self.s["facts"] if f["state"] == "assumed"]
        pct = min(25, 10 + 5 * len(assumed)) / 100.0
        low, high = min(r500(total * (1 - pct)), total), max(r500(total * (1 + pct)), total)
        notes = [f"Assumed {self.kbf[f['name']]['label']}: {f['value']}" for f in assumed]
        if self.has("water_damage_allowance"):
            notes.append("Water damage allowance until the site visit")
        return {"lines": lines, "total": int(total), "low": low, "high": high, "range_pct": int(pct * 100),
                "assumptions": notes,
                "drivers": [i["label"] for i in self.live_items()][:3], "deposit_percent": DEPOSIT_PCT,
                "deposit_amount": int(round(total * DEPOSIT_PCT / 100.0))}


def keyword_tasks(said, room, tasks):
    t = (said or "").lower()
    hits = []
    for tid, task in tasks.items():
        if task.get("auto") or (task["room"] and task["room"] != room):
            continue
        if any(re.search(p, t) for p in task["triggers"]):
            hits.append(tid)
    if "remove_vanity" in hits and "new_vanity" in hits and not re.search(r"\bnew\b", t):
        hits.remove("new_vanity")
    if "floor_tile" in hits and "flooring" in hits:
        hits.remove("flooring")
    return hits


async def get_session(lead):
    s = await db.itemizer_sessions.find_one({"lead_id": lead["id"]}, {"_id": 0})
    if not s:
        room = detect_room(lead["ask"], "bathroom" if "bath" in lead["ask"].lower() else "kitchen" if "kitchen" in lead["ask"].lower() else "living room")
        s = {"lead_id": lead["id"], "room": room, "items": [], "facts": [], "shows_used": 0, "insights": [], "levers": {"disc": 0}, "camera_on": False}
    return s


async def save_session(s):
    await db.itemizer_sessions.update_one({"lead_id": s["lead_id"]}, {"$set": s}, upsert=True)


async def turn(lead, said="", answers=None, camera_on=False):
    s, kb = await get_session(lead), await load_kb()
    iz = Itemizer(s, kb)
    s["camera_on"] = camera_on
    s["room"] = detect_room(said, s["room"])
    for f in s["facts"]:  # asked twice and not answered -> next channel
        if f["state"] == "asked" and f["name"] not in (answers or {}):
            f["skips"] = f.get("skips", 0) + 1
            if f["skips"] >= 2:
                iz.advance(f, camera_on, "no answer")
    new = []
    if said and said.strip():
        tids = keyword_tasks(said, s["room"], iz.tasks)
        if not tids and not answers:
            tids = await llm.map_tasks(said, s["room"], {k: v["label"] for k, v in iz.tasks.items() if not v.get("auto") and v["room"] in (None, s["room"])})
            if tids == ["needs_human"]:
                await save_session(s)
                return {"status": "needs_human", "next_action": "ask", "next_text": "That one needs a person to look at. I'll flag it for the team.",
                        "fact": "", "new_items": [], "insights": pop_insights(s)}, None
        new = [it for tid in tids if (it := iz.add_item(tid, said, camera_on))]
    for _ in range(2):
        iz.apply_answers(answers, camera_on)
        new += iz.apply_rules(camera_on)
    for it in new:
        if it.get("rule_id") and it["basis"] == "seen":
            amt = next((line["amount"] for line in iz.price(await db.contractors.find_one({"id": lead["contractor_id"]}, {"_id": 0}))["lines"] if line["key"] == it["item_id"]), 0)
            s["insights"].append({"text": f"Camera: {it['label'].lower()} is needed based on what I saw (+${amt:,}).", "delivered": False, "at": iso()})
    action, text, fact = iz.next_action(camera_on)
    out = {"status": "needs_info", "next_action": action, "next_text": text, "fact": fact["name"] if fact else "",
           "new_items": [i["label"] for i in new], "insights": pop_insights(s)}
    priced = None
    if action == "price":
        if not iz.live_items():
            out.update(next_action="ask", next_text="What work would you like done?")
        else:
            contractor = await db.contractors.find_one({"id": lead["contractor_id"]}, {"_id": 0})
            priced = iz.price(contractor)
            s["last_total"] = priced["total"]
            out.update(status="ok", next_text="", **{k: priced[k] for k in ("total", "low", "high", "drivers", "deposit_percent", "deposit_amount", "assumptions")})
    await save_session(s)
    return out, priced


def pop_insights(s):
    pending = [i["text"] for i in s["insights"] if not i["delivered"]]
    for i in s["insights"]:
        i["delivered"] = True
    return pending


async def on_goal_result(lead, goal):
    """goal: {fact_id, status: met|ambiguous|not_found, confidence, value, frame_url, t_ms, goal_id}"""
    s, kb = await get_session(lead), await load_kb()
    iz = Itemizer(s, kb)
    f = next((x for x in s["facts"] if x["fact_id"] == goal["fact_id"]), None)
    if not f:
        return {"ok": False, "error": "unknown fact"}
    contractor = await db.contractors.find_one({"id": lead["contractor_id"]}, {"_id": 0})
    before = iz.price(contractor)["total"] if iz.live_items() else 0
    ev = {"goal_id": goal.get("goal_id"), "frame_url": goal.get("frame_url"), "t_ms": goal.get("t_ms")}
    if goal["status"] == "met" and goal.get("confidence", 0) >= 0.75:
        iz.resolve(f, str(goal["value"]).lower(), "seen", goal["confidence"], ev)
    elif goal["status"] in ("met", "ambiguous"):
        f.update(state="open", pending_confirm=str(goal.get("value")), evidence=ev)
    elif f["state"] == "waiting_on_camera":
        iz.advance(f, s.get("camera_on", False), "not_found")
    added = iz.apply_rules(s.get("camera_on", False))
    after = iz.price(contractor)["total"] if iz.live_items() else 0
    if added or after != before:
        extra = f" (+${after - before:,})" if after > before else f" (-${before - after:,})" if after < before else ""
        what = "; ".join(i["label"].lower() for i in added) or "the estimate changed"
        s["insights"].append({"text": f"Camera: {kb[1][f['name']]['label']} is {f['value'] or goal.get('value')}; {what}{extra}.", "delivered": False, "at": iso()})
    priced = iz.price(contractor) if s.get("last_total") is not None and iz.live_items() else None
    if priced:
        s["last_total"] = priced["total"]
    await save_session(s)
    version = (await save_itemized(lead, priced))["version"] if priced else None
    return {"ok": True, "fact": f, "added": [i["label"] for i in added], "total_before": before, "total_after": after, "version": version}


async def save_itemized(lead, priced):
    """New quote version only when lines, total, range or assumptions change."""
    q = await latest_quote(lead["id"])
    lines = [{k: v for k, v in line.items() if k != "facts"} for line in priced["lines"]]
    if q and q.get("source") == "itemizer" and [(i["label"], i["amount"]) for i in q["line_items"]] == [(i["label"], i["amount"]) for i in lines] \
            and all(q.get(k) == priced[k] for k in ("total", "low", "high", "assumptions")):
        return q
    status = "live" if lead["status"] == "walkthru_initiated" else "sent"
    return await save_quote(lead, lines, priced["total"], status, {
        "low": priced["low"], "high": priced["high"], "drivers": priced["drivers"], "assumptions": priced["assumptions"],
        "range_pct": priced["range_pct"], "source": "itemizer"})
