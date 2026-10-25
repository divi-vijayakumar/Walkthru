"""Itemizer: words -> KB tasks -> items + facts (ladders) -> one next_action -> deterministic price. The LLM never prices."""
import re
import copy
import uuid
from core.db import db, iso
from core.quotes import latest_quote, save_quote
from pricing.engine import r500, is_rush, margin_discount_cap, DEPOSIT_PCT, RUSH_SURCHARGE
from itemizer.kb import load_kb
from itemizer import llm

TIERS = {"refresh": 0, "standard": 1, "premium": 2}
UNKNOWN = {"unknown", "not sure", "don't know", "dont know", "no idea", "", None}
MAX_SHOWS = 3
QUESTION_BUDGET = 5
MIN_ASK_IMPACT, PRIORITY_IMPACT = 300, 1000
YES = {"yes", "yeah", "yep", "right", "correct", "that's right", "true", "sure", "yup"}
NO = {"no", "nope", "wrong", "not right", "incorrect"}
PRICE_WORDS = re.compile(r"\b(quote|price|pricing|how much)\b", re.I)
WORK_WORDS = re.compile(r"\b(replace|new|add|install|remove|swap|redo|change|update|upgrade|fix|repair|put in|move|redo|get rid of)\b", re.I)
CLAUSES = re.compile(r"[,.;!?]+|\band also\b|\balso\b|\bplus\b|\band then\b")


def detect_room(said, current):
    t = (said or "").lower()
    for room, words in (("bathroom", ["bath", "shower", "toilet", "vanity", "powder room"]), ("kitchen", ["kitchen"]),
                        ("living room", ["living room", "family room"]), ("bedroom", ["bedroom"])):
        if any(w in t for w in words):
            return room
    return current


def fact_key(name, scope, item_id, room):
    return f"{name}@{item_id if scope == 'item' else room if scope == 'room' else 'job'}"


def steps(a, b, step):
    a *= 2.5
    if b:
        return a * b * 2.5, "steps"
    return (a * a if step == "square" else a * step if isinstance(step, (int, float)) else a), "steps"


def measure(value, step=None):
    """Returns (sq ft or ft or count, method). A step is about 2.5 ft; step = how one step-count turns into the fact's unit."""
    if isinstance(value, (int, float)):
        return float(value), "known"
    if isinstance(value, dict):
        m = value.get("method")
        if m == "tiles":
            return value["x"] * value["y"] * (value.get("tile_in", 12) / 12.0) ** 2, "tiles"
        if m == "steps":
            return steps(value["a"], value.get("b"), step)
        if m == "tape":
            return value["a"] * value.get("b", 1), "tape"
    t = str(value).lower()
    if "step" in t:
        nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", t)]
        if nums:
            return steps(nums[0], nums[1] if len(nums) > 1 else None, step)
    tm = re.search(r"(\d+)\s*(?:tiles?\s*)?(?:by|x)\s*(\d+)(?:\s*tiles?)?(?:\s*(?:at|of)\s*(\d+)\s*(?:in|inch))?", t)
    if tm and ("tile" in t or tm[3]):
        return int(tm[1]) * int(tm[2]) * ((int(tm[3] or 12)) / 12.0) ** 2, "tiles"
    if tm:
        return float(tm[1]) * float(tm[2]), "tape"
    n = re.search(r"\d+(\.\d+)?", t)
    return (float(n[0]), "known") if n else (None, None)


def unit_words(label):
    unit = label[label.find("(") + 1: label.find(")")] if "(" in label else ""
    return label.split(" (")[0], {"sq ft": "square feet", "linear ft": "feet", "ft": "feet"}.get(unit, unit)


def num_text(v):
    v = float(v)
    return str(int(v)) if v.is_integer() else f"{v:.1f}"


class Itemizer:
    def __init__(self, session, kb, contractor=None):
        self.s, (self.tasks, self.kbf, self.rules) = session, kb
        self.contractor = contractor
        self.confirmed = set()
        self._impact = {}
        self.s.setdefault("asked", 0)

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

    def assume(self, f, camera_pending=False):
        d = self.kbf[f["name"]]
        f.update(state="assumed", value=d["default"], basis="assumed", confidence=0.5, camera_pending=camera_pending or f.get("camera_pending", False),
                 site_visit=d.get("can_answer") is False)

    def enter(self, f, camera_on):
        while True:
            ch = self.channel(f)
            if ch == "assume":
                self.assume(f)
                return
            if ch == "ask" and self.kbf[f["name"]].get("can_answer") is False:  # homeowners can't know this: show or default
                f["idx"] += 1
                continue
            if ch == "camera" and not camera_on:  # move on now; a later clip can still answer it
                f["camera_pending"] = True
                f["idx"] += 1
                continue
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
        f["skips"] = 0
        self.enter(f, camera_on)

    def resolve(self, f, value, basis, confidence=1.0, evidence=None):
        f.update(state="resolved", value=value, basis=basis, confidence=confidence, evidence=evidence or {}, camera_pending=False)

    def open_fact(self, name, item, camera_on):
        d = self.kbf[name]
        if item["room"] in (d.get("not_rooms") or []):
            return
        fid = fact_key(name, d["scope"], item["item_id"], item["room"])
        if any(f["fact_id"] == fid for f in self.s["facts"]):
            return
        f = {"fact_id": fid, "name": name, "scope": d["scope"], "item_id": item["item_id"] if d["scope"] == "item" else None,
             "room": item["room"], "ladder": d["ladder"], "idx": 0, "value": None, "confidence": None, "basis": None,
             "evidence": {}, "state": "open", "attempts": []}
        self.s["facts"].append(f)
        self.enter(f, camera_on)
        for val, pattern in (d.get("from_said") or {}).items():  # "a new floating small vanity" -> mount floating, 1 sink
            if item.get("said") and re.search(pattern, item["said"], re.I):
                self.resolve(f, val, "said", evidence={"utterance": item["said"]})
                break

    def normalize(self, name, val):
        d, t = self.kbf[name], str(val).strip().lower()
        syn = d.get("synonyms") or {}
        for k in sorted(syn, key=len, reverse=True):
            if re.search(rf"\b{re.escape(k)}\b", t):
                return syn[k]
        opts = [str(o) for o in d.get("options") or []]
        if set(opts) == {"yes", "no"}:
            words = set(re.findall(r"[a-z']+", t))
            if words & YES:
                return "yes"
            if words & NO:
                return "no"
        for o in sorted(opts, key=len, reverse=True):
            if re.search(rf"\b{re.escape(o.lower())}\b", t):
                return o
        return t

    # --- items and rules -----------------------------------------------------
    def live_items(self):
        return [i for i in self.s["items"] if i["status"] != "removed"]

    def has(self, task_id):
        return any(i["task_id"] == task_id for i in self.live_items())

    def groups(self):
        return {self.tasks[i["task_id"]].get("group") for i in self.live_items() if i["task_id"] in self.tasks} - {None}

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
        self.apply_implies()
        return item

    def add_custom(self, words):
        label = f"To be priced by Apex: {words}"
        if any(i["label"].lower() == label.lower() for i in self.live_items()):
            return None
        item = {"item_id": f"it{len(self.s['items']) + 1}", "task_id": "custom", "room": self.s["room"], "said": words, "status": "proposed",
                "label": label, "rule_id": None, "basis": "said", "evidence": {}, "custom": True}
        self.s["items"].append(item)
        return item

    def apply_implies(self):
        for it in self.live_items():
            for name, val in (self.tasks.get(it["task_id"], {}).get("implies") or {}).items():
                for f in self.facts_named(name):
                    if f["state"] not in ("resolved", "assumed"):
                        self.resolve(f, val, "said", evidence={"implied_by": it["label"]})

    def rule_ok(self, r):
        if not all(self.has(t) for t in r["has"]) or any(self.has(t) for t in r["lacks"]):
            return False
        for name, vals in r["facts"].items():
            if str(self.value(name)).lower() not in [str(v) for v in vals]:
                return False
        for name, vals in (r.get("not") or {}).items():
            if str(self.value(name)).lower() in [str(v) for v in vals]:
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
            if name not in self.kbf:
                continue
            numeric = self.kbf[name].get("numeric")
            for f in self.facts_named(name):
                if f["state"] in ("resolved",) and f["basis"] in ("seen", "measured") or f["fact_id"] in self.confirmed:
                    continue
                if f.get("pending_confirm") is not None and isinstance(val, str):
                    v, seen = val.strip().lower().rstrip(".!"), f["pending_confirm"]
                    f["pending_confirm"] = None
                    if v in YES | NO:
                        self.confirmed.add(f["fact_id"])
                    if v in YES:
                        self.resolve(f, float(seen) if numeric else seen, "measured" if numeric else "seen", 1.0, f["evidence"])
                        continue
                    if v in NO:
                        self.advance(f, camera_on, "rejected")
                        continue
                if isinstance(val, str) and val.strip().lower() in UNKNOWN or val is None:
                    if f["state"] in ("open", "asked"):
                        self.advance(f, camera_on, "unknown")
                    continue
                if numeric:
                    num, method = measure(val, self.kbf[name].get("step"))
                    if num is None:
                        continue
                    self.resolve(f, round(num, 1), "measured" if method in ("tiles", "steps", "tape") else "said", evidence={"utterance": str(val), "method": method})
                else:
                    self.resolve(f, self.normalize(name, val), "said", evidence={"utterance": str(val)})

    # --- which questions are worth asking -------------------------------------
    def fill_defaults(self):
        for f in self.s["facts"]:
            if f["state"] not in ("resolved", "assumed"):
                f.update(state="assumed", value=self.kbf[f["name"]]["default"], pending_confirm=None)

    def total_if(self, f, val):
        twin = Itemizer(copy.deepcopy(self.s), (self.tasks, self.kbf, self.rules), self.contractor)
        g = next(x for x in twin.s["facts"] if x["fact_id"] == f["fact_id"])
        g.update(state="assumed", value=val)
        for _ in range(3):
            twin.fill_defaults()
            if not twin.apply_rules(False):
                break
        twin.fill_defaults()
        return twin.price(self.contractor)["total"] if twin.live_items() else 0

    def alternatives(self, d):
        if d.get("alts"):
            return d["alts"]
        if d.get("numeric"):
            v = float(d["default"] or 0)
            return [v * 0.5, v * 2] if "(" in d["label"] else [0, max(2, v * 2)]
        return [o for o in d.get("options") or [] if str(o) != str(d["default"])]

    def impact(self, f):
        """How much the total can move if this fact isn't its default."""
        if f["fact_id"] not in self._impact:
            d, alts = self.kbf[f["name"]], self.alternatives(self.kbf[f["name"]])
            base = self.total_if(f, d["default"]) if alts and self.contractor else 0
            self._impact[f["fact_id"]] = max([abs(self.total_if(f, a) - base) for a in alts] or [0]) if self.contractor else 0
        return self._impact[f["fact_id"]]

    def worth_asking(self, f):
        p, imp = self.kbf[f["name"]].get("priority"), self.impact(f)
        return imp >= MIN_ASK_IMPACT and (p == 1 or (p != 2 and imp >= PRIORITY_IMPACT))

    def question(self, f):
        d = self.kbf[f["name"]]
        return (d.get("room_questions") or {}).get(f["room"]) or d["question"]

    def confirm_text(self, f):
        d, v = self.kbf[f["name"]], f["pending_confirm"]
        tpl = d.get("confirm") or {}
        if isinstance(tpl, str):
            return tpl.format(v=num_text(v) if d.get("numeric") else v)
        if str(v) in tpl:
            return tpl[str(v)]
        noun, unit = unit_words(d["label"])
        if d.get("numeric"):
            return f"Looks like the {noun} is about {num_text(v)} {unit}. Does that sound right?".replace("  ", " ")
        return f"Looks like the {noun} is {v}. Is that right?"

    # --- next action -----------------------------------------------------------
    def next_action(self, camera_on, wants_price=False):
        if wants_price:
            return "price", "", None
        open_f = [f for f in self.s["facts"] if f["state"] in ("open", "asked")]
        conf = [f for f in open_f if f.get("pending_confirm") is not None]
        if conf and self.s["asked"] < QUESTION_BUDGET:
            self.s["asked"] += 1
            return "confirm", self.confirm_text(conf[0]), conf[0]
        missed = [f for f in open_f if any(a.get("result") in ("not_found", "ambiguous") for a in f["attempts"])]
        for ch, pool in (("show", missed), ("ask", open_f), ("show", open_f), ("measure", open_f)):
            for f in pool:
                if self.channel(f) != ch or f["state"] not in ("open", "asked") or f.get("pending_confirm") is not None:
                    continue
                if ch == "show" and not (camera_on and self.s["shows_used"] < MAX_SHOWS):
                    self.advance(f, camera_on, "camera off")
                    continue
                if ch in ("ask", "measure"):
                    if not self.worth_asking(f):
                        self.assume(f)
                        continue
                    if self.s["asked"] >= QUESTION_BUDGET:
                        return "price", "", None
                    self.s["asked"] += 1
                if ch == "show":
                    self.s["shows_used"] += 1
                    f["state"] = "waiting_on_camera"
                else:
                    f["state"] = "asked"
                d = self.kbf[f["name"]]
                f["attempts"].append({"channel": ch, "at": iso()})
                return ch, d["show"] if ch in ("show", "measure") else self.question(f), f
        return "price", "", None

    def finalize(self, camera_on):
        """Before pricing: every open fact takes its default (camera findings still waiting keep listening)."""
        added = []
        for _ in range(3):
            for f in self.s["facts"]:
                if f.get("pending_confirm") is not None:
                    v = f.pop("pending_confirm")
                    f.update(state="assumed", value=float(v) if self.kbf[f["name"]].get("numeric") else v, basis="seen", from_camera=True)
                elif f["state"] in ("open", "asked", "waiting_on_camera"):
                    self.assume(f, camera_pending=self.channel(f) in ("camera", "show"))
            more = self.apply_rules(camera_on)
            added += more
            if not more:
                break
        return added

    def note(self, f):
        d = self.kbf[f["name"]]
        noun, unit = unit_words(d["label"])
        v = f"{num_text(f['value'])} {unit}".strip() if d.get("numeric") else f["value"]
        if f.get("from_camera"):
            return f"{noun[:1].upper() + noun[1:]}: about {v} from the camera, to confirm at the site visit"
        if f.get("site_visit"):
            return f"Assumed {d['label']}: {f['value']} (confirmed at the site visit)"
        return f"Assumed {d['label']}: {f['value']}"

    # --- price -----------------------------------------------------------------
    def price(self, contractor):
        tier = TIERS.get(str(self.value("finish_level") or "standard"), 1)
        lines, trades = [], set()
        for it in self.live_items():
            if it.get("custom"):
                lines.append({"key": it["item_id"], "label": it["label"], "amount": None, "basis": "said", "evidence": {}, "custom": True})
                continue
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
        priced_items = [i for i in self.live_items() if not i.get("custom")]
        rooms = {i["room"] for i in priced_items}
        if priced_items:
            lines.append({"key": "protection", "label": "Protection and cleanup", "amount": 450 * len(rooms), "basis": "assumed", "evidence": {}})
            if any("removal" in self.tasks[i["task_id"]]["tags"] for i in priced_items):
                lines.append({"key": "demolition", "label": "Demolition and haul-away", "amount": 650 if len(rooms) == 1 else 1200, "basis": "assumed", "evidence": {}})
            if trades:
                lines.append({"key": "permit", "label": f"Permit ({', '.join(sorted(trades))})", "amount": 450 * len(trades), "basis": "assumed", "evidence": {}})
        total = sum(line["amount"] or 0 for line in lines)
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
        notes = [self.note(f) for f in assumed]
        if self.has("water_damage_allowance"):
            notes.append("Water damage allowance until the site visit")
        notes += [f"{i['label']} (not in this total)" for i in self.live_items() if i.get("custom")]
        return {"lines": lines, "total": int(total), "low": low, "high": high, "range_pct": int(pct * 100),
                "assumptions": notes,
                "drivers": [i["label"] for i in self.live_items()][:3], "deposit_percent": DEPOSIT_PCT,
                "deposit_amount": int(round(total * DEPOSIT_PCT / 100.0))}

    # --- plain-sentence camera insights ------------------------------------------
    def describe(self, f):
        d, v = self.kbf[f["name"]], f["value"]
        seen = d.get("seen") or {}
        sinks = {"1": "Single-sink", "2": "Double-sink"}.get(str(self.value("sinks")), "The")
        text = seen.get(str(v)) if isinstance(seen, dict) else seen
        if text:
            return text.format(v=num_text(v) if d.get("numeric") else v, sinks=sinks)
        noun, unit = unit_words(d["label"])
        return f"The {noun} looks like about {num_text(v)} {unit}".strip() if d.get("numeric") else f"The {noun} looks like {v}"

    def insight(self, f, added, change):
        parts = [self.describe(f)] + [self.tasks[i["task_id"]].get("because") or f"that adds {i['label'].lower()}" for i in added]
        text = "; ".join(parts)
        return text + (f" (+${change:,})" if change > 0 else f" (-${-change:,})" if change < 0 else "")


def keyword_tasks(said, room, tasks):
    t = (said or "").lower()
    hits = []
    for tid, task in tasks.items():
        if task.get("auto") or (task["room"] and task["room"] != room):
            continue
        if any(re.search(p, t) for p in task["triggers"]):
            hits.append(tid)
    if "remove_vanity" in hits and "new_vanity" in hits and not re.search(r"\b(new|floating|swap|for an?|with an?)\b", t):
        hits.remove("new_vanity")
    keep = {}
    other_floor = re.search(r"\b(hardwood|engineered|vinyl|laminate|carpet|lvp)\b", t)
    for tid in hits:  # one task per group; the room-specific task beats the whole-house one
        g = tasks[tid].get("group") or tid
        prefer = tasks[tid]["room"] and not tasks[keep[g]]["room"] if g in keep else True
        if g == "floor" and other_floor and g in keep:  # a stated non-tile material needs the Flooring task
            prefer = tid == "flooring"
        if prefer:
            keep[g] = tid
    return [tid for tid in hits if keep.get(tasks[tid].get("group") or tid) == tid]


def unmatched_clauses(said, room, tasks):
    """Parts of what the homeowner said that name work but match no task."""
    out = []
    for c in CLAUSES.split(said or ""):
        c = re.sub(r"^\s*(and|so|then|um|uh)\s+", "", c.strip(), flags=re.I).strip()
        if len(c.split()) < 3 or PRICE_WORDS.search(c) or not WORK_WORDS.search(c) or keyword_tasks(c, room, tasks):
            continue
        out.append(c[:120])
    return out


async def get_session(lead):
    s = await db.itemizer_sessions.find_one({"lead_id": lead["id"]}, {"_id": 0})
    if not s:
        room = detect_room(lead["ask"], "bathroom" if "bath" in lead["ask"].lower() else "kitchen" if "kitchen" in lead["ask"].lower() else "living room")
        s = {"lead_id": lead["id"], "room": room, "items": [], "facts": [], "shows_used": 0, "levers": {"disc": 0}, "camera_on": False, "asked": 0}
    s.pop("insights", None)
    return s


async def save_session(s):
    await db.itemizer_sessions.update_one({"lead_id": s["lead_id"]}, {"$set": s, "$unset": {"insights": ""}}, upsert=True)


async def add_insight(lead_id, text, key=None):
    """One pending insight per fact: a newer finding about the same fact replaces the undelivered one."""
    if key and await db.itemizer_insights.find_one_and_update({"lead_id": lead_id, "key": key, "delivered": False}, {"$set": {"text": text, "at": iso()}}):
        return
    await db.itemizer_insights.insert_one({"id": uuid.uuid4().hex, "lead_id": lead_id, "key": key, "text": text, "delivered": False, "at": iso()})


async def claim_insights(lead_id):
    """Each insight is handed out exactly once (portal poll or update_scope, whichever comes first)."""
    out = []
    async for i in db.itemizer_insights.find({"lead_id": lead_id, "delivered": False}, {"_id": 0}).sort("at", 1):
        if await db.itemizer_insights.find_one_and_update({"id": i["id"], "delivered": False}, {"$set": {"delivered": True, "delivered_at": iso()}}):
            out.append(i["text"])
    return out


async def list_insights(lead_id):
    return [i async for i in db.itemizer_insights.find({"lead_id": lead_id}, {"_id": 0}).sort("at", 1)]


async def turn(lead, said="", answers=None, camera_on=False, wants_price=False):
    s, kb = await get_session(lead), await load_kb()
    contractor = await db.contractors.find_one({"id": lead["contractor_id"]}, {"_id": 0})
    iz = Itemizer(s, kb, contractor)
    call = await db.call_sessions.find_one({"lead_id": lead["id"], "ended_at": None}, {"_id": 0, "id": 1})
    if call and s.get("call_id") != call["id"]:  # the question budget is per call
        s.update(call_id=call["id"], asked=0)
    wants_price = bool(wants_price or PRICE_WORDS.search(said or ""))
    s["camera_on"] = camera_on
    s["room"] = detect_room(said, s["room"])
    for f in s["facts"]:  # asked twice and not answered -> next channel
        if f["state"] == "asked" and f["name"] not in (answers or {}):
            f["skips"] = f.get("skips", 0) + 1
            if f["skips"] >= 2:
                iz.advance(f, camera_on, "no answer")
    new, custom = [], []
    if said and said.strip():
        groups = iz.groups()
        tids = [t for t in keyword_tasks(said, s["room"], iz.tasks) if (iz.tasks[t].get("group") or t) not in groups]
        if not tids and not answers and not keyword_tasks(said, s["room"], iz.tasks):
            tids = await llm.map_tasks(said, s["room"], {k: v["label"] for k, v in iz.tasks.items() if not v.get("auto") and v["room"] in (None, s["room"])})
            if tids == ["needs_human"]:
                tids = []
        else:
            custom = [it for c in unmatched_clauses(said, s["room"], iz.tasks) if (it := iz.add_custom(c))]
        new = [it for tid in tids if (it := iz.add_item(tid, said, camera_on))]
        if not new and not custom and not tids and not answers and not wants_price and not iz.live_items():
            custom = [it for it in [iz.add_custom(said.strip()[:120])] if it] if WORK_WORDS.search(said) else []
    for _ in range(2):
        iz.apply_answers(answers, camera_on)
        new += iz.apply_rules(camera_on)
    iz.apply_implies()
    for it in new:
        if it.get("rule_id") and it["basis"] == "seen":
            src = next((f for n in next((r["facts"] for r in iz.rules if r["rule_id"] == it["rule_id"]), {}) for f in iz.facts_named(n)), None)
            amt = next((line["amount"] for line in iz.price(contractor)["lines"] if line["key"] == it["item_id"]), 0)
            if src:
                await add_insight(lead["id"], iz.insight(src, [it], amt), src["fact_id"])
    action, text, fact = iz.next_action(camera_on, wants_price)
    priced = None
    if action == "price":
        new += iz.finalize(camera_on)
    new += custom
    note = " ".join(f"I've noted {c['said']} for {contractor['name']} to price." for c in custom)
    out = {"status": "needs_info", "next_action": action, "next_text": f"{note} {text}".strip(), "fact": fact["name"] if fact else "",
           "new_items": [i["label"] for i in new]}
    if action == "price":
        if not iz.live_items():
            out.update(next_action="ask", next_text="What work would you like done?")
        else:
            priced = iz.price(contractor)
            s["last_total"] = priced["total"]
            out.update(status="ok", next_text=note, **{k: priced[k] for k in ("total", "low", "high", "range_pct", "drivers", "deposit_percent", "deposit_amount", "assumptions")})
            out["to_be_priced"] = [c["label"] for c in iz.live_items() if c.get("custom")]
    await save_session(s)
    out["insights"] = await claim_insights(lead["id"])
    return out, priced


async def on_goal_result(lead, goal):
    """goal: {fact_id, status: met|ambiguous|not_found, confidence, value, frame_url, t_ms, goal_id}"""
    s, kb = await get_session(lead), await load_kb()
    contractor = await db.contractors.find_one({"id": lead["contractor_id"]}, {"_id": 0})
    iz = Itemizer(s, kb, contractor)
    f = next((x for x in s["facts"] if x["fact_id"] == goal["fact_id"]), None)
    if not f:
        return {"ok": False, "error": "unknown fact"}
    if f["state"] == "resolved" and f["basis"] in ("said", "measured"):
        return {"ok": True, "fact": f, "added": [], "ignored": "already answered by the homeowner", "version": None}
    d = kb[1][f["name"]]
    before = iz.price(contractor)["total"] if iz.live_items() else 0
    ev = {k: goal.get(k) for k in ("goal_id", "frame_url", "t_ms", "box", "label")}
    conf, value = goal.get("confidence", 0) or 0, goal.get("value")
    found = goal["status"] in ("met", "ambiguous") and value not in (None, "None", "")
    resolved = False
    if found and d.get("numeric"):  # measured from the camera: always confirm with the homeowner
        f.update(state="open", pending_confirm=num_text(float(value) * d.get("camera_scale", 1)), evidence=ev, camera_pending=False)
    elif found and goal["status"] == "met" and conf > 0.75:
        iz.resolve(f, str(value).lower(), "seen", conf, ev)
        resolved = True
    elif found and conf >= 0.5:
        f.update(state="open", pending_confirm=str(value).lower(), evidence=ev, camera_pending=False)
    elif f["state"] == "waiting_on_camera":
        iz.advance(f, s.get("camera_on", False), "not_found")
    added = iz.apply_rules(s.get("camera_on", False))
    after = iz.price(contractor)["total"] if iz.live_items() else 0
    related = []
    if resolved:  # items already added from this fact's default are now backed by the camera
        for it in iz.live_items():
            r = next((r for r in iz.rules if r["rule_id"] == it.get("rule_id")), None)
            if r and f["name"] in r["facts"] and it not in added:
                it.update(basis="seen", evidence=ev)
                related.append(it)
    if resolved or added:
        change = after - before or sum(line["amount"] or 0 for line in iz.price(contractor)["lines"] if line["key"] in {i["item_id"] for i in related})
        await add_insight(lead["id"], iz.insight(f, added + related, change), f["fact_id"])
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
