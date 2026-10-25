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
WORK_WORDS = re.compile(r"\b(replace|new|add|install|remove|swap|redo|change|update|upgrade|fix|repair|put in|move|get rid of|take out|rip out|"
                        r"tear out|knock down|open up|improve|better|nicer|build|refresh)\b", re.I)
CLAUSES = re.compile(r"[,.;!?]+|\band also\b|\balso\b|\bplus\b|\band then\b|\band (?=(?:make|change|take|replace|remove|add|put|get|rip|knock|"
                     r"open|install|redo|swap|fix|move|update|upgrade|paint|build)\b)")
VAGUE_SINK = re.compile(r"\bsink( area)?\b", re.I)
CLUES = ("floor_above", "wall_central", "beam_nearby")
SCENARIO_MIN = 2000
SCENARIOS = {"load_bearing": {"likely": "If it isn't load-bearing, the price drops by about ${d:,}.",
                              "unlikely": "If it turns out to be load-bearing, the price goes up by about ${d:,}."},
             "water_damage": {"no": "If we find hidden water damage, the price goes up by about ${d:,}.",
                              "yes": "If there's no water damage after all, the price drops by about ${d:,}."}}
FLIP = {"likely": "unlikely", "unlikely": "likely", "yes": "no", "no": "yes"}
SURVEY_KEYS = {"sink": "sink_type", "mirror": "mirror_type", "floor": "floor_type", "walls": "wall_finish", "water_damage": "water_damage"}
SEEN_PHRASE = {"sink_type": "a {v} sink", "mirror_type": "a {v} mirror", "floor_type": "a {v} floor",
               "wall_finish": {"paint": "painted walls", "tile": "tiled walls", "wallpaper": "wallpapered walls"},
               "water_damage": {"yes": "signs of water damage"}}
SUGGEST = [("mirror_type", None, "mirror_replace", "Would you like the mirror replaced too?"),
           ("sink_type", ["pedestal", "wall-mounted"], "new_vanity", "Would you like a vanity with storage in place of the {v} sink?")]


def and_list(xs):
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


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
        force = self.s.get("force") or {}
        if name in force:
            return force[name]
        if name == "load_bearing":  # never asked: two or more clues mean likely
            return "likely" if sum(str(self.value(n)).lower() == "yes" for n in CLUES) >= 2 else "unlikely"
        fs = [f for f in self.facts_named(name) if f["state"] in ("resolved", "assumed")]
        if item_id:
            fs = [f for f in fs if f.get("item_id") in (item_id, None)] or fs
        return fs[0]["value"] if fs else None

    def channel(self, f):
        return f["ladder"][f["idx"]] if f["idx"] < len(f["ladder"]) else "assume"

    def assume(self, f, camera_pending=False):
        if f.get("p0"):  # must-ask facts are never defaulted
            f["state"] = "open"
            return
        d = self.kbf[f["name"]]
        f.update(state="assumed", value=d["default"], basis="assumed", confidence=0.5, camera_pending=camera_pending or f.get("camera_pending", False),
                 site_visit=d.get("can_answer") is False)

    def p0_ladder(self, d):
        lad = [c for c in d["ladder"] if c != "assume"]
        return lad if any(c in ("ask", "measure") for c in lad) else lad + ["ask"]

    def make_p0(self, f, camera_on):
        f.update(p0=True, ladder=self.p0_ladder(self.kbf[f["name"]]))
        if f["state"] != "resolved":
            f.update(state="open", value=None, basis=None, idx=0)
            self.enter(f, camera_on)

    def enter(self, f, camera_on):
        while True:
            if f.get("p0") and f["idx"] >= len(f["ladder"]):
                f.update(idx=len(f["ladder"]) - 1, state="open")
                return
            ch = self.channel(f)
            if ch == "assume":
                self.assume(f)
                return
            if ch == "ask" and self.kbf[f["name"]].get("can_answer") is False and not f.get("p0"):  # homeowners can't know this: show or default
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

    def open_fact(self, name, item, camera_on, p0=False):
        d = self.kbf[name]
        if item["room"] in (d.get("not_rooms") or []):
            return
        fid = fact_key(name, d["scope"], item["item_id"], item["room"])
        old = next((f for f in self.s["facts"] if f["fact_id"] == fid), None)
        if old:
            if p0 and not old.get("p0"):
                self.make_p0(old, camera_on)
            return
        f = {"fact_id": fid, "name": name, "scope": d["scope"], "item_id": item["item_id"] if d["scope"] == "item" else None,
             "room": item["room"], "ladder": d["ladder"], "idx": 0, "value": None, "confidence": None, "basis": None,
             "evidence": {}, "state": "open", "attempts": []}
        if p0:
            f.update(p0=True, ladder=self.p0_ladder(d))
        self.s["facts"].append(f)
        self.enter(f, camera_on)
        for val, pattern in (d.get("from_said") or {}).items():  # "a new floating small vanity" -> mount floating, 1 sink
            if item.get("said") and re.search(pattern, item["said"], re.I):
                self.resolve(f, val, "said", evidence={"utterance": item["said"]})
                break
        sv = (self.s.get("survey") or {}).get(name)  # the camera survey already saw it
        if sv and f["state"] != "resolved":
            if d.get("numeric"):
                f.update(state="open", pending_confirm=num_text(sv["value"]), evidence=sv["evidence"], camera_pending=False)
            else:
                self.resolve(f, sv["value"], "seen", 0.8, sv["evidence"])

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

    def is_size(self, name):
        label = self.kbf[name]["label"]
        return any(u in label for u in ("sq ft", "linear ft", "(ft)"))

    def add_item(self, task_id, said, camera_on, rule=None, basis="said", evidence=None):
        if self.has(task_id):
            return None
        task = self.tasks[task_id]
        n = len(self.s["items"]) + 1
        item = {"item_id": f"it{n}", "task_id": task_id, "room": self.s["room"], "said": said, "status": "proposed",
                "label": task["label"], "rule_id": rule, "basis": basis, "evidence": evidence or {}}
        self.s["items"].append(item)
        p0 = set(task.get("p0") or []) | {c["qty"] for c in task["price"] if c.get("qty") in task["facts"] and self.is_size(c["qty"])}
        for name in task["facts"]:
            self.open_fact(name, item, camera_on, name in p0)
        self.open_fact("finish_level", item, camera_on, not task.get("split"))
        for name in ("water_damage", "timeline"):
            self.open_fact(name, item, camera_on)
        self.apply_implies()
        return item

    def add_custom(self, words, camera_on=False):
        """Work the KB doesn't know: ask what comes out, what goes in, how big and what finish, so Apex can price it."""
        label = f"To be priced by Apex: {words}"
        if any(i["label"].lower() == label.lower() for i in self.live_items()):
            return None
        item = {"item_id": f"it{len(self.s['items']) + 1}", "task_id": "custom", "room": self.s["room"], "said": words, "status": "proposed",
                "label": label, "rule_id": None, "basis": "said", "evidence": {}, "custom": True}
        self.s["items"].append(item)
        for name in ("custom_out", "custom_in", "custom_size", "finish_level"):
            self.open_fact(name, item, camera_on, True)
        return item

    def priced_items(self):
        return [i for i in self.live_items() if not i.get("custom") and not self.tasks.get(i["task_id"], {}).get("split")]

    def p0_open(self):
        live = {i["item_id"] for i in self.live_items()}
        fs = [f for f in self.s["facts"] if f.get("p0") and f["state"] != "resolved" and (f.get("item_id") is None or f["item_id"] in live)]
        return sorted(fs, key=lambda f: self.kbf[f["name"]].get("p0_rank", 3))

    def ready(self):
        return bool(self.priced_items()) and not self.p0_open()

    def resolved_value(self, name, item_id):
        return next((f["value"] for f in self.facts_named(name) if f.get("item_id") in (item_id, None) and f["state"] == "resolved"), None)

    def custom_details(self, it):
        return {"words": it["said"], "room": it["room"], "out": self.resolved_value("custom_out", it["item_id"]),
                "in": self.resolved_value("custom_in", it["item_id"]), "size": self.resolved_value("custom_size", it["item_id"]),
                "finish": self.value("finish_level"), "frames": it.get("frames") or []}

    def apply_splits(self, camera_on):
        """'Take out the tiles' -> floor, wall or both once answered; a 'no' to a vague-match confirm drops those items."""
        added = []
        for it in list(self.live_items()):
            task = self.tasks.get(it["task_id"]) or {}
            for name, targets in (task.get("split") or {}).items():
                f = next((x for x in self.facts_named(name) if x.get("item_id") == it["item_id"] and x["state"] == "resolved"), None)
                if not f or str(f["value"]) not in targets:
                    continue
                it["status"] = "removed"
                added += [n for t in targets[str(f["value"])] if (n := self.add_item(t, it["said"], camera_on, basis=f["basis"], evidence=f.get("evidence")))]
                for src, dst in (task.get("carry") or {}).items():
                    v = self.resolved_value(src, it["item_id"])
                    opts = [str(o) for o in self.kbf[dst].get("options") or []]
                    for g in self.facts_named(dst):
                        if v is not None and g["state"] != "resolved" and str(v) in opts:
                            self.resolve(g, v, "said", evidence={"utterance": str(v)})
            if it.get("confirm") and self.resolved_value(it["confirm"], None) == "no":
                it["status"] = "removed"
                added += [n for n in [self.add_custom(it.get("clause") or it["said"], camera_on)] if n]
        return added

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
                    if f.get("p0"):  # asked again a different way; after two "not sure"s take the usual answer as theirs
                        f["unknowns"] = f.get("unknowns", 0) + 1
                        if f["unknowns"] >= 2:
                            self.resolve(f, self.kbf[name]["default"], "unsure", 0.5)
                            continue
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
        if self.kbf[f["name"]].get("always_ask"):
            return True
        p, imp = self.kbf[f["name"]].get("priority"), self.impact(f)
        return imp >= MIN_ASK_IMPACT and (p == 1 or (p != 2 and imp >= PRIORITY_IMPACT))

    def question(self, f):
        d = self.kbf[f["name"]]
        q = (d.get("room_questions") or {}).get(f["room"]) or d["question"]
        it = next((i for i in self.s["items"] if i["item_id"] == f.get("item_id") and i.get("custom")), None)
        return f"About the {it['said']}: {q[:1].lower()}{q[1:]}" if it else q

    def ask_p0(self, f, camera_on, wants_price):
        d, ch = self.kbf[f["name"]], self.channel(f)
        f["attempts"].append({"channel": ch, "at": iso()})
        if ch == "show" and camera_on and self.s["shows_used"] < MAX_SHOWS and not wants_price:
            self.s["shows_used"] += 1
            f["state"] = "waiting_on_camera"
            return "show", d["show"], f
        measure = d.get("numeric") and d["show"] and (ch == "measure" or not d["question"])
        text = d["show"] if measure else self.question(f) or d["show"]
        f["state"] = "asked"
        if wants_price:
            text = f"Just so the number means something: {text[:1].lower()}{text[1:]}"
        return ("measure" if measure else "ask"), text, f

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
        """Must-ask (P0) facts first and never skipped; the 5-question budget only covers the rest, which take defaults."""
        live = {i["item_id"] for i in self.live_items()}
        open_f = [f for f in self.s["facts"] if f["state"] in ("open", "asked") and (f.get("item_id") is None or f["item_id"] in live)]
        conf = sorted([f for f in open_f if f.get("pending_confirm") is not None], key=lambda f: not f.get("p0"))
        if conf and (conf[0].get("p0") or (self.s["asked"] < QUESTION_BUDGET and not wants_price)):
            self.s["asked"] += 0 if conf[0].get("p0") else 1
            return "confirm", self.confirm_text(conf[0]), conf[0]
        p0 = [f for f in self.p0_open() if f.get("pending_confirm") is None]
        ready = [f for f in p0 if f["state"] in ("open", "asked")]
        if ready:
            return self.ask_p0(ready[0], camera_on, wants_price)
        if not wants_price:
            out = self.next_optional(camera_on, [f for f in open_f if not f.get("p0")])
            if out:
                return out
        if p0:  # only camera-waiting must-asks left: ask them directly
            return self.ask_p0(p0[0], camera_on, wants_price)
        return "price", "", None

    def next_optional(self, camera_on, open_f):
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
                        return None
                    self.s["asked"] += 1
                if ch == "show":
                    self.s["shows_used"] += 1
                    f["state"] = "waiting_on_camera"
                else:
                    f["state"] = "asked"
                d = self.kbf[f["name"]]
                f["attempts"].append({"channel": ch, "at": iso()})
                return ch, d["show"] if ch in ("show", "measure") else self.question(f), f
        return None

    def finalize(self, camera_on):
        """Before pricing: every open fact takes its default (camera findings still waiting keep listening)."""
        added = []
        for _ in range(3):
            for f in self.s["facts"]:
                if f.get("p0"):
                    continue
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
                lines.append({"key": it["item_id"], "label": it["label"], "amount": None, "basis": "said", "evidence": {}, "custom": True,
                              "details": self.custom_details(it)})
                continue
            task = self.tasks[it["task_id"]]
            if task.get("split"):
                continue
            trades |= {t for t in task["tags"] if t in ("plumbing", "electrical", "gas", "structural", "shower")}
            amt = 0.0
            for c in task["price"]:
                if any(str(self.value(n, it["item_id"])).lower() not in [str(v) for v in vals] for n, vals in (c.get("when") or {}).items()):
                    continue
                base = c["tiers"][tier] if "tiers" in c else c["amount"]
                qty = float(self.value(c["qty"], it["item_id"]) or 0) if c.get("qty") else 1
                amt += max(base * qty * c.get("mult", 1), c.get("min", 0))
            used = [f for f in self.s["facts"] if f.get("item_id") == it["item_id"] or (f["name"] in {c.get("qty") for c in task["price"]})]
            lines.append({"key": it["item_id"], "label": it["label"], "amount": int(round(amt)), "basis": it["basis"],
                          "evidence": it["evidence"], "facts": [{"name": f["name"], "value": f["value"], "basis": f["basis"]} for f in used]})
        priced_items = self.priced_items()
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

    def scenario(self, contractor, priced):
        """Big unknowns only a site visit settles: price the likely case, say what the other case costs."""
        best = None
        for name, texts in SCENARIOS.items():
            if (name == "load_bearing" and not self.has("wall_removal")) or (name == "water_damage" and not self.facts_named(name)):
                continue
            cur = str(self.value(name)).lower()
            if cur not in texts:
                continue
            twin = Itemizer(copy.deepcopy(self.s), (self.tasks, self.kbf, self.rules), self.contractor)
            twin.s["force"] = {**(twin.s.get("force") or {}), name: FLIP[cur]}
            for _ in range(3):
                if not twin.apply_rules(False):
                    break
            twin.fill_defaults()
            alt = twin.price(contractor)["total"]
            diff = alt - priced["total"]
            if abs(diff) > SCENARIO_MIN and (not best or abs(diff) > abs(best["diff"])):
                best = {"fact": name, "total": alt, "diff": diff, "say": texts[cur].format(d=int(round(abs(diff), -2)))}
        return best

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


def split_clauses(said):
    out = [re.sub(r"^\s*(and|so|then|um|uh)\s+", "", c.strip(), flags=re.I).strip() for c in CLAUSES.split(said or "")]
    return [c for c in out if c]


def clause_hits(clause, room, tasks):
    """Trigger matches for one clause; returns (task ids, the clause if it vaguely meant the sink area)."""
    t = clause.lower()
    hits = [tid for tid, task in tasks.items() if not task.get("auto") and task["room"] in (None, room) and any(re.search(p, t) for p in task["triggers"])]
    drop = set()
    if "remove_vanity" in hits and "new_vanity" in hits and not re.search(r"\b(new|floating|swap|for an?|with an?)\b", t):
        drop.add("new_vanity")
    if {"floor_tile", "wall_tile", "walk_in_shower", "backsplash", "flooring"} & set(hits):
        drop.add("tile_work")
    if {"wall_tile", "accent_wallpaper", "partition_check", "glass_panel_removal"} & set(hits):
        drop.add("wall_removal")
    if "vanity_light" in hits and not re.search(r"\b(fan|exhaust)\b", t):
        drop.add("exhaust_fan_lights")
    hits = [h for h in hits if h not in drop]
    if room == "bathroom" and VAGUE_SINK.search(t) and not {"remove_vanity", "new_vanity", "faucet_replace"} & set(hits):
        return hits + ["remove_vanity", "new_vanity"], clause
    return hits, None


def match_tasks(said, room, tasks):
    hits, vague = [], None
    for c in split_clauses(said):
        h, v = clause_hits(c, room, tasks)
        hits += [x for x in h if x not in hits]
        vague = vague or v
    t = (said or "").lower()
    keep = {}
    other_floor = re.search(r"\b(hardwood|engineered|vinyl|laminate|carpet|lvp)\b", t) and room != "bathroom"
    for tid in hits:  # one task per group; the room-specific task beats the whole-house one
        g = tasks[tid].get("group") or tid
        prefer = tasks[tid]["room"] and not tasks[keep[g]]["room"] if g in keep else True
        if g == "floor" and other_floor and g in keep:  # a stated non-tile material needs the Flooring task
            prefer = tid == "flooring"
        if prefer:
            keep[g] = tid
    return [tid for tid in hits if keep.get(tasks[tid].get("group") or tid) == tid], vague


def keyword_tasks(said, room, tasks):
    return match_tasks(said, room, tasks)[0]


def unmatched_clauses(said, room, tasks):
    """Clauses that name work but match no trigger (these go to the LLM, then to Apex)."""
    return [c[:120] for c in split_clauses(said)
            if len(c.split()) >= 3 and not PRICE_WORDS.search(c) and WORK_WORDS.search(c) and not clause_hits(c, room, tasks)[0]]


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
    said = re.sub(r"\bsync\b", "sink", said or "", flags=re.I)
    s["camera_on"] = camera_on
    s["room"] = detect_room(said, s["room"])
    for f in s["facts"]:  # asked twice and not answered -> next channel
        if f["state"] == "asked" and f["name"] not in (answers or {}):
            f["skips"] = f.get("skips", 0) + 1
            if f["skips"] >= 2:
                iz.advance(f, camera_on, "no answer")
    new, custom = [], []
    if said.strip():
        groups = iz.groups()
        tids, vague = match_tasks(said, s["room"], iz.tasks)
        tids = [t for t in tids if (iz.tasks[t].get("group") or t) not in groups]
        catalog = {k: v["label"] for k, v in iz.tasks.items() if not v.get("auto") and v["room"] in (None, s["room"])}
        for c in unmatched_clauses(said, s["room"], iz.tasks):  # triggers missed this clause: ask the LLM, else Apex prices it
            ids = [t for t in await llm.map_tasks(c, s["room"], catalog) if t in catalog and t not in tids and (iz.tasks[t].get("group") or t) not in groups]
            if ids:
                tids += ids
            elif (it := iz.add_custom(c, camera_on)):
                custom.append(it)
        for tid in tids:
            it = iz.add_item(tid, said, camera_on)
            if not it:
                continue
            new.append(it)
            if vague and tid in ("remove_vanity", "new_vanity"):
                it.update(confirm="vanity_plan", clause=vague)
                iz.open_fact("vanity_plan", it, camera_on, True)
        if not new and not custom and not tids and not answers and not wants_price and not iz.live_items() and WORK_WORDS.search(said):
            custom = [it for it in [iz.add_custom(said.strip()[:120], camera_on)] if it]
    for _ in range(3):
        iz.apply_answers(answers, camera_on)
        new += iz.apply_splits(camera_on)
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
        if iz.p0_open():  # finalizing added work with its own must-ask facts
            action, text, fact = iz.next_action(camera_on, wants_price)
    new += custom
    note = " ".join(f"I've noted {c['said']} for {contractor['name']} to price." for c in custom)
    tips = " ".join(s.pop("suggest", []))
    out = {"status": "needs_info", "next_action": action, "next_text": f"{note} {text} {tips}".strip(), "fact": fact["name"] if fact else "",
           "new_items": [i["label"] for i in new]}
    if action == "price":
        priced = iz.price(contractor) if iz.priced_items() else None
        if not priced or priced["total"] <= 0:  # never price an empty scope
            ask = "Is there anything else you'd like done while we're at it?" if iz.live_items() else "What work would you like done?"
            out.update(next_action="ask", next_text=f"{note} {ask}".strip(), fact="scope")
            priced = None
        else:
            priced["if_not"] = iz.scenario(contractor, priced)
            s["last_total"] = priced["total"]
            out.update(status="ok", next_text=f"{note} {tips}".strip(), **{k: priced[k] for k in ("total", "low", "high", "range_pct", "drivers", "deposit_percent", "deposit_amount", "assumptions", "if_not")})
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
    priced = iz.price(contractor) if s.get("last_total") is not None and iz.ready() else None
    if priced:
        priced["if_not"] = iz.scenario(contractor, priced)
        s["last_total"] = priced["total"]
    await save_session(s)
    q = await save_itemized(lead, priced) if priced else None
    return {"ok": True, "fact": f, "added": [i["label"] for i in added], "total_before": before, "total_after": after, "version": q["version"] if q else None}


async def resave(lead, s, iz, contractor):
    """After a camera finding: a quote already given gets a new version if the price moved."""
    priced = iz.price(contractor) if s.get("last_total") is not None and iz.ready() else None
    if priced:
        priced["if_not"] = iz.scenario(contractor, priced)
        s["last_total"] = priced["total"]
    await save_session(s)
    if priced:
        await save_itemized(lead, priced)


async def on_survey(lead, data):
    """One camera survey: fills matching facts, tells Alex what's visible, suggests (never adds) related jobs."""
    s, kb = await get_session(lead), await load_kb()
    contractor = await db.contractors.find_one({"id": lead["contractor_id"]}, {"_id": 0})
    iz = Itemizer(s, kb, contractor)
    hits = sorted(data.get("hits") or [], key=lambda h: -h.get("confidence", 0))
    found, extra = {}, []
    for h in hits:
        key, _, ans = (h.get("label") or "").partition(":")
        key, ans = key.strip().lower().replace(" ", "_"), ans.strip().lower()
        ev = {**{k: h.get(k) for k in ("frame_url", "t_ms", "box", "label")}, "goal_id": data.get("goal_id")}
        name = SURVEY_KEYS.get(key)
        if name and ans and name not in found:
            v = iz.normalize(name, ans)
            if str(v) in [str(o) for o in kb[1][name].get("options") or []]:
                found[name] = {"value": v, "evidence": ev}
        elif key == "toilet" and ans and ans not in ("no", "none"):
            extra.append("a toilet")
        elif key == "tub_shower" and ans and ans not in ("no", "none"):
            extra.append("a tub" if "tub" in ans else "a shower")
    area = data.get("value")
    if isinstance(area, (int, float)) and not isinstance(area, bool) and area > 0:
        best = hits[0] if hits else {}
        found["floor_area"] = {"value": float(area), "evidence": {k: best.get(k) for k in ("frame_url", "t_ms", "box", "label")}}
    if not found and not extra:
        return {"ok": False, "phrases": []}
    s.update(survey={**(s.get("survey") or {}), **found}, survey_done=True)
    for name, sv in found.items():
        for f in iz.facts_named(name):
            if f["state"] == "resolved" and f["basis"] in ("said", "measured", "unsure"):
                continue
            if kb[1][name].get("numeric"):
                f.update(state="open", pending_confirm=num_text(sv["value"]), evidence=sv["evidence"], camera_pending=False)
            else:
                iz.resolve(f, sv["value"], "seen", 0.8, sv["evidence"])
    iz.apply_rules(s.get("camera_on", False))
    phrases = []
    for name, sv in found.items():
        tpl = SEEN_PHRASE.get(name)
        tpl = tpl.get(str(sv["value"])) if isinstance(tpl, dict) else tpl
        if tpl:
            phrases.append("a medicine cabinet" if sv["value"] == "medicine cabinet" else tpl.format(v=sv["value"]))
    phrases += extra
    if phrases:
        await add_insight(lead["id"], f"I can see {and_list(phrases)}", "survey")
    for name, vals, task, tip in SUGGEST:
        if name in found and (vals is None or found[name]["value"] in vals) and not iz.has(task) and task not in s.get("suggested", []):
            s.setdefault("suggest", []).append(tip.format(v=found[name]["value"]))
            s.setdefault("suggested", []).append(task)
    await resave(lead, s, iz, contractor)
    return {"ok": True, "phrases": phrases, "found": list(found)}


async def on_custom_frames(lead, item_id, data):
    s = await get_session(lead)
    it = next((i for i in s["items"] if i["item_id"] == item_id), None)
    hits = sorted(data.get("hits") or [], key=lambda h: -h.get("confidence", 0))[:3]
    if it:
        it["frames"] = [{"frame_url": h["frame_url"], "t_ms": h.get("t_ms"), "label": h.get("label")} for h in hits if h.get("frame_url")]
        await save_session(s)


async def price_custom(lead, item_id, label, tiers, words):
    """The contractor prices a 'To be priced by Apex' line: it becomes a rate-card job, and this lead gets a new quote version."""
    s, kb = await get_session(lead), await load_kb()
    it = next((i for i in s["items"] if i["item_id"] == item_id and i.get("custom") and i["status"] != "removed"), None)
    if not it:
        return None
    tid = "custom_" + (re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:40] or "job")
    if tid in kb[0]:
        tid += "_" + uuid.uuid4().hex[:4]
    task = {"task_id": tid, "room": it["room"], "label": label, "facts": [], "price": [{"tiers": tiers, "mult": 1}],
            "triggers": [rf"\b{re.escape(w)}\b" for w in words], "tags": [], "auto": False, "group": None,
            "from_custom": {"words": it["said"], "lead_id": lead["id"], "details": Itemizer(s, kb).custom_details(it), "at": iso()}}
    await db.kb_tasks.insert_one(dict(task))
    kb[0][tid] = task
    it.update(task_id=tid, label=label, custom=False, priced_from_custom=True)
    contractor = await db.contractors.find_one({"id": lead["contractor_id"]}, {"_id": 0})
    iz = Itemizer(s, kb, contractor)
    priced = iz.price(contractor) if iz.priced_items() else None
    if priced and priced["total"] > 0:
        priced["if_not"] = iz.scenario(contractor, priced)
        s["last_total"] = priced["total"]
    await save_session(s)
    q = await save_itemized(lead, priced) if priced else None
    return {"task_id": tid, "quote": q}


async def save_itemized(lead, priced):
    """New quote version only when lines, total, range or assumptions change. Never a $0 quote."""
    if not priced or priced["total"] <= 0:
        return None
    q = await latest_quote(lead["id"])
    lines = [{k: v for k, v in line.items() if k != "facts"} for line in priced["lines"]]
    if q and q.get("source") == "itemizer" and [(i["label"], i["amount"]) for i in q["line_items"]] == [(i["label"], i["amount"]) for i in lines] \
            and all(q.get(k) == priced.get(k) for k in ("total", "low", "high", "assumptions", "if_not")):
        return q
    status = "live" if lead["status"] == "walkthru_initiated" else "sent"
    return await save_quote(lead, lines, priced["total"], status, {
        "low": priced["low"], "high": priced["high"], "drivers": priced["drivers"], "assumptions": priced["assumptions"],
        "range_pct": priced["range_pct"], "source": "itemizer", "if_not": priced.get("if_not")})
