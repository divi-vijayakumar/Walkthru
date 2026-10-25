# Iteration 11: one test per real-Vapi-call fix (1-13): question budget, price on request, room-aware facts, no duplicate
# tasks, never drop scope, floating vanity, fast camera, camera measuring, confirm, can't-answer facts, room options,
# exactly-once insights, plain-sentence insights. Only TEST_ leads with (408) 555-0199; cleans up after itself.
import os
import json
import time
import subprocess
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
_db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
SAFE_PHONE = "(408) 555-0199"
REAL = ("I want to replace the tiles with hardwood floors, swap the vanity for a new floating small vanity, "
        "replace the glass with a small elegant one, update the pendant, and paint the walls")
GLASS = "replace the glass with a small elegant one"
# iteration 16: the glass clause now maps to the KB job 'Remove glass shower panel'; an out-of-KB clause exercises the Apex line
SAUNA = "build a small sauna in the corner"
REAL_CUSTOM = REAL.replace(GLASS, SAUNA)
P0_VALS = {"floor_new": "tile", "floor_area": "40", "wall_area": "300", "finish_level": "standard", "partition_kind": "glass",
           "custom_out": "nothing", "custom_in": "a small sauna", "custom_size": "4 by 4 feet", "wall_replacement": "fully open",
           "wall_length": "10", "wall_floor_finish": "patch", "replacing_vanity": "new", "new_vanity_mount": "floating", "new_vanity_sinks": "1"}
G3 = {"finish_level": "standard", "water_damage": "no", "timeline": "in two months", "sinks": "1", "replacing_vanity": "open"}
FLOOR_GOAL = ("Estimate the floor area in square feet. Use the tile count and tile size, and objects of known size "
              "(interior door 80 in tall, toilet about 28 in deep, vanity about 21 in deep). Reply with value and unit sq_ft.")


@pytest.fixture(scope="module")
def s(owner_token):
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {owner_token}", "Origin": BASE_URL})
    return sess


@pytest.fixture(scope="module")
def L(s):
    made = {}

    def make(key, ask="Bathroom remodel"):
        if key in made:
            return made[key]
        r = s.post(f"{API}/leads", json={"name": f"TEST_Call11 {key}", "phone": SAFE_PHONE, "source": "website", "ask": ask})
        assert r.status_code == 200, r.text
        lead = r.json()["lead"]
        if not lead.get("portal_token"):
            s.post(f"{API}/leads/{lead['id']}/start-agent")
        made[key] = _db.leads.find_one({"id": lead["id"]}, {"_id": 0})
        return made[key]
    yield make
    s.post(f"{API}/kb/reset")
    for lead in made.values():
        sids = [c["id"] for c in _db.call_sessions.find({"lead_id": lead["id"]}, {"id": 1})]
        gids = [g["goal_id"] for g in _db.itemizer_goals.find({"lead_id": lead["id"]}, {"goal_id": 1})]
        _db.percia_goals.delete_many({"$or": [{"session_id": {"$in": sids}}, {"goal_id": {"$in": gids}}]})
        _db.percia_frames.delete_many({"goal_id": {"$in": gids}})
        _db.media.delete_many({"session_id": {"$in": sids}})
        for c in ("itemizer_sessions", "itemizer_insights", "itemizer_goals", "itemizer_tips", "quotes", "sms_log", "call_sessions", "followups",
                  "pricing_states", "contracts", "payments", "frames"):
            _db[c].delete_many({"lead_id": lead["id"]})
        _db.leads.delete_one({"id": lead["id"]})


def turn(s, lid, said="", answers=None, camera_on=False, wants_price=False):
    r = s.post(f"{API}/itemizer/{lid}/turn", json={"said": said, "answers": answers or {}, "camera_on": camera_on, "wants_price": wants_price})
    assert r.status_code == 200, r.text
    return r.json()


def opening(s, lid, said, answers, camera_on=False):
    """iteration 17 rule 3: a turn with answers creates no items from said -> say the work first, then answer."""
    turn(s, lid, said, {}, camera_on)
    return turn(s, lid, "", answers, camera_on)


def goal(s, lid, fact_id, status, conf=0.0, value=None):
    r = s.post(f"{API}/itemizer/{lid}/goal-result", json={"fact_id": fact_id, "status": status, "confidence": conf, "value": value,
                                                          "frame_url": "https://x/f.jpg", "box": [0.1, 0.1, 0.5, 0.5], "label": "TEST"})
    assert r.status_code == 200, r.text
    return r.json()


def reset(s, lid):
    assert s.post(f"{API}/itemizer/{lid}/reset").json() == {"reset": True}


def sess(s, lid):
    return s.get(f"{API}/itemizer/{lid}").json()


def facts(s, lid, name):
    return [x for x in sess(s, lid)["facts"] if x["name"] == name]


def drive(s, lid, r, vals=None, camera_on=False, n=20):
    log = []
    for _ in range(n):
        if r["status"] == "ok":
            break
        log.append((r["fact"], r["next_action"], r["next_text"]))
        r = turn(s, lid, "", {r["fact"]: (vals or {}).get(r["fact"], "not sure")}, camera_on)
    return r, log


def tool(lead, args):
    body = {"message": {"toolCallList": [{"id": "t1", "function": {"name": "update_scope", "arguments": args}}]}}
    r = requests.post(f"{API}/portal/{lead['portal_token']}/agent/tools", json=body)
    assert r.status_code == 200, r.text
    res = r.json()["results"][0]
    return json.loads(res["result"]) if "result" in res else res


# FIX 1 question budget: real-call sentence priced within 5 questions; <$300 facts never asked; range widens
def test_fix1_question_budget(s, L):
    lid = L("real")["id"]
    reset(s, lid)
    r = turn(s, lid, REAL)
    r, log = drive(s, lid, r, P0_VALS)
    print(log, r)
    # iteration 17: ONE budget of 5 questions per call incl. must-asks and camera confirmations, then price
    asked = [x for x in log if x[1] in ("ask", "measure", "confirm")]
    assert r["status"] == "ok" and r["total"] > 0
    assert sess(s, lid)["asked"] <= 5 and len(asked) <= 5, log
    assert "sinks" not in [f for f, _, _ in log]
    assert len(r["assumptions"]) >= 3 and all("(assumed, to confirm at the site visit)" in a or "not in this total" in a
                                               or "until the site visit" in a for a in r["assumptions"]), r["assumptions"]
    assert "low" not in r and "high" not in r  # one exact number
    # sinks on Remove vanity ($350 vs $550) is below $300 impact -> never asked
    reset(s, lid)
    r = opening(s, lid, "I want this sink gone", {k: v for k, v in G3.items() if k != "sinks"})
    r, log = drive(s, lid, r)
    assert "sinks" not in [f for f, _, _ in log], log


# Iteration 16 regression: "replace the glass ..." in a bathroom must never turn into a Wall removal (+ engineer/permit) when the
# homeowner answers "not sure" to the partition question (LLM maps the clause to glass_panel_removal AND partition_check)
def test_glass_clause_never_adds_wall_removal(s, L):
    lid = L("glass")["id"]
    reset(s, lid)
    r = turn(s, lid, REAL)
    r, log = drive(s, lid, r)
    labels = [i["label"] for i in sess(s, lid)["items"] if i["status"] != "removed"]
    print(log, labels)
    assert "Wall removal" not in labels, labels
    assert "Patch floor where the wall stood" not in labels, labels


# Iteration 16 regression: ONE "not sure" to a must-ask fact must re-ask it (only the 2nd takes the usual answer).
# RCA: turn() runs apply_answers 3x per turn, so f["unknowns"] hits 3 on the first "not sure".
def test_p0_single_not_sure_reasks(s, L):
    lid = L("p0unsure")["id"]
    reset(s, lid)
    r = turn(s, lid, "I want to take out the tiles")
    assert r["fact"] == "tile_where" or r["fact"] in ("tile_replacement",), r
    first = r["fact"]
    turn(s, lid, "", {first: "not sure"})
    f = facts(s, lid, first)[0]
    print(f)
    assert f["state"] == "assumed", f  # 15:34 rule: 'not sure' -> assumed now, never asked again
    r = turn(s, lid, "")
    assert r["fact"] != first, r


# FIX 2 price on request
@pytest.mark.parametrize("said,flag", [("", True), ("how much would that be", False), ("can I get a quote", False), ("what's the price", False)])
def test_fix2_wants_price(s, L, said, flag):
    lid = L("price")["id"]
    reset(s, lid)
    r = turn(s, lid, "I want a new floor and paint the walls")
    assert r["status"] == "needs_info"
    r = turn(s, lid, said, {}, False, flag)
    print(r)
    # iteration 17: a price request prices now; open must-asks take their defaults as listed assumptions
    assert r["next_action"] == "price" and r["status"] == "ok" and r["total"] > 0, r
    assert not r["next_text"].startswith("Just so the number means something"), r
    assert any("(assumed, to confirm at the site visit)" in a for a in r["assumptions"]), r["assumptions"]


# FIX 3 room-aware facts
def test_fix3_room_aware(s, L):
    lid = L("room")["id"]
    reset(s, lid)
    r = turn(s, lid, "update the pendant and redo the floors")
    names = {f["name"] for f in sess(s, lid)["facts"]}
    labels = [i["label"] for i in sess(s, lid)["items"]]
    print(labels, names)
    assert "stairs" not in names and "fan_count" not in names
    assert "Exhaust fan and lights" in labels and "Lighting and ceiling fans" not in labels


# FIX 4 no duplicate tasks
def test_fix4_no_duplicates(s, L):
    lid = L("dup")["id"]
    reset(s, lid)
    turn(s, lid, "update the pendant lights and the light fixtures, and new tile floor and new flooring")
    labels = [i["label"] for i in sess(s, lid)["items"] if i["status"] != "removed"]
    print(labels)
    assert labels.count("Exhaust fan and lights") == 1 and "Lighting and ceiling fans" not in labels
    assert "Bathroom floor" in labels and "Flooring" not in labels  # iteration 16 label
    turn(s, lid, "also add some recessed lighting and hardwood floors")
    labels2 = [i["label"] for i in sess(s, lid)["items"] if i["status"] != "removed"]
    print(labels2)
    assert "Lighting and ceiling fans" not in labels2 and "Flooring" not in labels2


# FIX 5 never drop scope
def test_fix5_custom_line(s, L):
    lid = L("custom")["id"]
    reset(s, lid)
    r = turn(s, lid, REAL_CUSTOM)
    print(r)
    label = f"To be priced by Apex: {SAUNA}"
    assert label in r["new_items"]
    assert f"I've noted {SAUNA} for Apex Remodeling to price" in r["next_text"]
    r, _ = drive(s, lid, r, P0_VALS)  # iteration 16: answer the must-ask facts (incl. the four custom questions) first
    r = turn(s, lid, "", {}, False, True)
    line = [ln for ln in r["lines"] if ln["label"] == label]
    assert line and line[0]["amount"] is None
    assert label in r["to_be_priced"]
    assert r["total"] == sum(ln["amount"] or 0 for ln in r["lines"])
    lead = L("custom")
    requests.post(f"{API}/portal/{lead['portal_token']}/call/start")
    t = tool(lead, {"said": "", "wants_price": True})
    print(t)
    assert label in t["to_be_priced"]
    q = _db.quotes.find_one({"lead_id": lid}, sort=[("version", -1)])
    assert any(li["label"] == label and li["amount"] is None for li in q["line_items"])


# FIX 6 new floating small vanity
def test_fix6_floating_vanity(s, L):
    lid = L("float")["id"]
    reset(s, lid)
    r = turn(s, lid, "swap the vanity for a new floating small vanity")
    r, log = drive(s, lid, r)
    ss = sess(s, lid)
    labels = [i["label"] for i in ss["items"] if i["status"] != "removed"]
    fv = {f["name"]: f for f in ss["facts"]}
    print(labels, log)
    assert "New vanity" in labels
    assert fv["new_vanity_mount"]["value"] == "floating" and fv["new_vanity_mount"]["basis"] == "said"
    assert fv["new_vanity_sinks"]["value"] == "1" and fv["new_vanity_sinks"]["basis"] == "said"
    assert fv["replacing_vanity"]["state"] == "resolved" and fv["replacing_vanity"]["value"] == "new"
    asked = [f for f, _, _ in log]
    assert not {"new_vanity_mount", "new_vanity_sinks", "replacing_vanity"} & set(asked)


# FIX 7 camera speed: one Percia pass for all open camera facts, first finding <= 30 s
def test_fix7_camera_speed(s, L):
    lead = L("cam")
    lid = lead["id"]
    reset(s, lid)
    cs = requests.post(f"{API}/portal/{lead['portal_token']}/call/start").json()
    sid = cs.get("id") or cs.get("session", {}).get("id")
    requests.post(f"{API}/portal/{lead['portal_token']}/call/camera", json={"on": True})
    tool(lead, {"said": "I want this sink gone", "camera_on": True})
    with open("/tmp/clip/first8.mp4", "rb") as fh:
        clip = fh.read()
    t0 = time.time()
    up = requests.post(f"{API}/media", data={"session_id": sid, "kind": "video", "seq": "0", "t_start_ms": "0", "duration_ms": "8000"},
                       files={"file": ("clip.mp4", clip, "video/mp4")}, headers={"X-Portal-Token": lead["portal_token"]})
    assert up.status_code == 200, up.text
    first = None
    while time.time() - t0 < 90:
        if _db.itemizer_goals.find_one({"lead_id": lid, "status": "done"}):
            first = time.time() - t0
            break
        time.sleep(0.5)
    goals = list(_db.itemizer_goals.find({"lead_id": lid}, {"_id": 0}))
    pg = list(_db.percia_goals.find({"goal_id": {"$in": [g["goal_id"] for g in goals]}}, {"_id": 0, "goal_id": 1, "status": 1, "updated_at": 1, "media": 1, "value": 1, "result": 1}))
    print("first finding s:", first, [(g["fact_id"], g["status"]) for g in goals], pg)
    assert len(goals) >= 2
    assert len({tuple(m["media_id"] for m in p["media"]) for p in pg}) == 1
    assert first is not None and first <= 30, f"first finding after {first}s"


# FIX 8 camera measuring goals
def test_fix8_measure_goals(s, L):
    kb = s.get(f"{API}/kb").json()["facts"]
    fa = next(f for f in kb if f["fact_id"] == "floor_area")
    wa = next(f for f in kb if f["fact_id"] == "wall_area")
    assert fa["goals"][0] == FLOOR_GOAL and fa["ladder"][0] == "camera"
    assert wa["ladder"][0] == "camera" and "length" in wa["goals"][0] and "unit ft" in wa["goals"][0] and wa.get("camera_scale") == 8
    lid = L("meas")["id"]
    reset(s, lid)
    turn(s, lid, "paint the walls", camera_on=True)
    goal(s, lid, "wall_area@bathroom", "met", 0.8, "30")
    r = turn(s, lid, "", {}, True)
    print(r)
    assert r["next_action"] == "confirm" and "240" in r["next_text"]


# FIX 9 confirm instead of ask
@pytest.mark.parametrize("answer,expect", [("yes", 30.0), ("40", 40.0)])
def test_fix9_confirm_numeric(s, L, answer, expect):
    lid = L("conf")["id"]
    reset(s, lid)
    turn(s, lid, "I want a new tile floor", camera_on=True)
    goal(s, lid, "floor_area@bathroom", "met", 0.9, "30")
    r = turn(s, lid, "", {}, True)
    assert r["next_action"] == "confirm"
    assert r["next_text"] == "Looks like the floor is about 30 square feet. Does that sound right?"
    turn(s, lid, "", {"floor_area": answer}, True)
    f = facts(s, lid, "floor_area")[0]
    print(f)
    assert f["state"] == "resolved" and float(f["value"]) == expect and f["basis"] in (("measured",) if answer == "yes" else ("said", "measured"))


def test_fix9_confirm_categorical(s, L):
    lid = L("conf2")["id"]
    reset(s, lid)
    opening(s, lid, "I want this sink gone", G3, True)
    goal(s, lid, "vanity_mount@it1", "met", 0.6, "floor")
    r = turn(s, lid, "", {}, True)
    print(r)
    assert r["next_action"] == "confirm" and r["fact"] == "vanity_mount"
    reset(s, lid)
    opening(s, lid, "I want this sink gone", G3, True)
    goal(s, lid, "vanity_mount@it1", "met", 0.9, "floor")
    f = facts(s, lid, "vanity_mount")[0]
    ins = sess(s, lid)["insights"]
    r = turn(s, lid, "", {}, True)
    print(f, ins, r)
    assert f["state"] == "resolved" and f["basis"] == "seen" and len(ins) == 1
    assert r["fact"] != "vanity_mount"


# FIX 10 never ask what homeowners can't answer
def test_fix10_cant_answer(s, L):
    lid = L("cant")["id"]
    reset(s, lid)
    r = opening(s, lid, "new exhaust fan", {"fan_exists": "yes"}, False)
    r, log = drive(s, lid, r)
    print(log, r["assumptions"])
    assert "fan_vents_outside" not in [f for f, _, _ in log]
    assert any("fan vents outside" in a and "(assumed, to confirm at the site visit)" in a for a in r["assumptions"]), r["assumptions"]
    reset(s, lid)
    r = opening(s, lid, "new exhaust fan", {"fan_exists": "yes"}, True)
    r, log = drive(s, lid, r, camera_on=True)
    print(log)
    shows = [t for f, a, t in log if f == "fan_vents_outside"]
    assert shows and all(a == "show" for f, a, _ in log if f == "fan_vents_outside")
    assert "Could you point the camera at the fan in the ceiling for a second?" in shows
    # hood and cast iron: never asked
    klid = L("cantk", "Kitchen remodel")["id"]
    reset(s, klid)
    r = turn(s, klid, "I want a new range hood")
    r, log = drive(s, klid, r)
    print(log)
    assert "hood_vents_outside" not in [f for f, a, _ in log if a == "ask"]
    reset(s, lid)
    r = turn(s, lid, "remove the tub")
    r, log = drive(s, lid, r)
    print(log)
    assert "cast_iron" not in [f for f, a, _ in log if a == "ask"]


# FIX 11 room-appropriate options
def test_fix11_no_carpet_in_bath(s, L):
    lid = L("opts")["id"]
    texts = []
    for said in (REAL_CUSTOM, "I want new carpet", "new flooring", "I want new floors"):
        reset(s, lid)
        r = turn(s, lid, said)
        r, log = drive(s, lid, r)
        texts += [t for _, _, t in log]
    print(texts)
    assert not any("carpet" in t.lower() for t in texts)
    kb = s.get(f"{API}/kb").json()["facts"]
    fn = next(f for f in kb if f["fact_id"] == "floor_new")
    assert "new tile, vinyl plank" in fn["room_questions"]["bathroom"] and "carpet" not in fn["room_questions"]["bathroom"].lower()  # iteration 16 wording


# FIX 12 insights exactly once (portal poll ?live=1 vs update_scope)
def test_fix12_insights_once(s, L):
    lead = L("ins")
    lid, tok = lead["id"], lead["portal_token"]
    reset(s, lid)
    assert requests.post(f"{API}/portal/{tok}/call/start").status_code == 200
    tool(lead, {"said": "I want this sink gone", "camera_on": True})
    tool(lead, {"said": "", "answers": G3, "camera_on": True})
    goal(s, lid, "vanity_mount@it1", "met", 0.9, "floor")
    assert requests.get(f"{API}/portal/{tok}").json()["insights"] == []
    assert _db.itemizer_insights.count_documents({"lead_id": lid, "delivered": False}) == 1
    # iteration 17 (VOICE_MODE=vapi): the portal poll never claims insights; update_scope returns them once, prepended to next_text
    a = requests.get(f"{API}/portal/{tok}?live=1").json()["insights"]
    assert a == [] and _db.itemizer_insights.count_documents({"lead_id": lid, "delivered": False}) == 1
    t = tool(lead, {"said": "", "answers": {}})
    print(t)
    assert len(t["insights"]) == 1 and t["next_text"].startswith(t["insights"][0].rstrip(".")), t
    t = tool(lead, {"said": "", "answers": {}})
    assert t["insights"] == [] and requests.get(f"{API}/portal/{tok}?live=1").json()["insights"] == []
    # undelivered insight comes back in update_scope, then never in the poll
    goal(s, lid, "water_damage@job", "met", 0.9, "yes") if facts(s, lid, "water_damage")[0]["state"] != "resolved" else None
    _db.itemizer_insights.insert_one({"id": "TEST_ins", "lead_id": lid, "key": "x", "text": "TEST insight", "delivered": False, "at": "2099"})
    t = tool(lead, {"said": "", "answers": {}})
    print(t["insights"])
    assert "TEST insight" in t["insights"]
    assert "TEST insight" not in requests.get(f"{API}/portal/{tok}?live=1").json()["insights"]
    assert all(i["delivered"] for i in sess(s, lid)["insights"])


# FIX 13 plain-sentence insights
def test_fix13_plain_insight(s, L):
    lid = L("plain")["id"]
    reset(s, lid)
    r = opening(s, lid, "I want this sink gone", G3, True)  # iteration 17: work first, then the answers
    out = goal(s, lid, "vanity_mount@it1", "met", 0.9, "floor")
    ins = [i["text"] for i in sess(s, lid)["insights"]]
    print(out, ins)
    assert ins == ["Single-sink vanity standing on the floor; the tile under it will need patching (+$650)"]
    assert not any("number of sinks" in i.lower() for i in ins)


# FIX 1/8 gap: a priority-1 camera-first fact (floor area, >= $1,000 swing) must not be silently defaulted when the camera is off
def test_fix1_camera_off_priority1_floor_area_measured(s, L):
    lid = L("camoff")["id"]
    reset(s, lid)
    r = turn(s, lid, "I want a new tile floor", {}, False)
    r, log = drive(s, lid, r, {"finish_level": "standard", "floor_new": "tile"})
    print(log, r)
    # iteration 17: still asked (within the 5-question budget), never silently defaulted
    assert "floor_area" in [f for f, a, _ in log if a in ("measure", "ask")], log
