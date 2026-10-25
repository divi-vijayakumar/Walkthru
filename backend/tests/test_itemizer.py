# Itemizer + KB + update_scope tool tests. Uses only TEST_ leads (never /dev/reset), cleans up after itself.
import os
import json
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
VANITY_Q = "Are you putting a new vanity there, or leaving the space open?"
SHOW_Q = "Could you point the camera at the bottom of the vanity for a second?"
ASK_Q = "Does it sit right on the floor, or hang on the wall with space underneath?"
G3_ANS = {"finish_level": "standard", "water_damage": "no", "timeline": "in two months", "sinks": "1", "replacing_vanity": "open"}


@pytest.fixture(scope="module")
def s(owner_token):
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {owner_token}", "Origin": BASE_URL})
    return sess


@pytest.fixture(scope="module")
def leads(s):
    made = {}

    def make(key, ask):
        r = s.post(f"{API}/leads", json={"name": f"TEST_Itemizer {key}", "phone": SAFE_PHONE, "source": "website", "ask": ask})
        assert r.status_code == 200, r.text
        lead = r.json()["lead"]
        if not lead.get("portal_token"):
            s.post(f"{API}/leads/{lead['id']}/start-agent")
            lead = _db.leads.find_one({"id": lead["id"]}, {"_id": 0})
        made[key] = lead
        return lead
    yield make
    s.post(f"{API}/kb/reset")
    for lead in made.values():
        for c in ("itemizer_sessions", "itemizer_insights", "itemizer_goals", "itemizer_tips", "quotes", "sms_log", "call_sessions", "followups", "pricing_states", "contracts", "payments", "frames"):
            _db[c].delete_many({"lead_id": lead["id"]})
        _db.leads.delete_one({"id": lead["id"]})


def turn(s, lid, said="", answers=None, camera_on=False):
    r = s.post(f"{API}/itemizer/{lid}/turn", json={"said": said, "answers": answers or {}, "camera_on": camera_on})
    assert r.status_code == 200, r.text
    return r.json()


def goal(s, lid, fact_id, status, conf=0.0, value=None):
    r = s.post(f"{API}/itemizer/{lid}/goal-result", json={"fact_id": fact_id, "status": status, "confidence": conf, "value": value, "frame_url": "https://x/f.jpg"})
    assert r.status_code == 200, r.text
    return r.json()


def reset(s, lid):
    assert s.post(f"{API}/itemizer/{lid}/reset").json() == {"reset": True}


def opening(s, lid, said, answers, camera_on=False):
    """iteration 17 rule 3: a turn with answers creates no items from said -> say the work first, then answer."""
    turn(s, lid, said, {}, camera_on)
    return turn(s, lid, "", answers, camera_on)


def gate3_neither(s, lid):
    reset(s, lid)
    # iteration 16: Remove vanity carries the camera-only sink_type fact; answer it so only vanity_mount is assumed
    r1 = opening(s, lid, "I want this sink gone", dict(G3_ANS, sink_type="vanity cabinet"), False)
    goal(s, lid, "vanity_mount@it1", "not_found")
    return r1, turn(s, lid, "", {"vanity_mount": "not sure"}, False)


# --- Auth
def test_auth_required(leads):
    for m, p in (("get", "/kb"), ("post", "/kb/reset"), ("get", "/itemizer/x"), ("post", "/itemizer/x/turn"), ("put", "/kb/tasks/toilet")):
        assert getattr(requests, m)(f"{API}{p}", json={}).status_code == 401, p


# --- Gate 1
def test_gate1_sink_gone(s, leads):
    lid = leads("bath", "Bathroom remodel")["id"]
    reset(s, lid)
    r = turn(s, lid, "I want this sink gone", {}, True)
    print(r)
    assert "Remove vanity" in r["new_items"]
    assert r["next_action"] == "ask" and r["next_text"] == VANITY_Q and r["fact"] == "replacing_vanity"


# --- Gate 2
def test_gate2_camera_floor_floating(s, leads):
    lid = _db.leads.find_one({"name": "TEST_Itemizer bath"})["id"]
    reset(s, lid)
    turn(s, lid, "I want this sink gone", {}, True)
    r2 = turn(s, lid, "", {"replacing_vanity": "new"}, True)
    print("r2", r2)
    assert "New vanity" in r2["new_items"]
    g = goal(s, lid, "vanity_mount@it1", "met", 0.88, "floor")
    print("goal", g)
    assert g["ok"] and g["fact"]["basis"] == "seen" and g["fact"]["value"] == "floor"
    r3 = turn(s, lid, "", {"new_vanity_mount": "floating"}, True)
    print("r3", r3)
    sess = s.get(f"{API}/itemizer/{lid}").json()
    items = [i for i in sess["items"] if i["status"] != "removed"]
    retile = [i for i in items if i["label"] == "Retile under old vanity"]
    assert len(retile) == 1 and retile[0]["basis"] == "seen" and retile[0]["rule_id"] == "retile_floating"
    all_insights = r2["insights"] + r3["insights"]
    assert len(all_insights) == 1, all_insights
    assert "650" in all_insights[0]
    # drive to price and check the line amount
    for _ in range(15):
        if r3["status"] == "ok":
            break
        r3 = turn(s, lid, "", {r3["fact"]: "not sure"}, True)
    assert r3["status"] == "ok"
    line = [ln for ln in r3["lines"] if ln["label"] == "Retile under old vanity"]
    assert line and line[0]["amount"] == 650 and line[0]["basis"] == "seen"
    assert r3["insights"] == []


# --- Gate 3
def test_gate3_show_when_camera_on(s, leads):
    lid = _db.leads.find_one({"name": "TEST_Itemizer bath"})["id"]
    reset(s, lid)
    # camera goal fails while Alex is still asking other things -> show request next
    turn(s, lid, "I want this sink gone", {}, True)
    goal(s, lid, "vanity_mount@it1", "not_found")
    # iteration 16 spec: finish level is a must-ask (P0) for every job, so it is answered first; then the show request
    r = turn(s, lid, "", {"replacing_vanity": "open", "finish_level": "standard"}, True)
    print(r)
    assert r["next_action"] == "show" and r["next_text"] == SHOW_Q and r["fact"] == "vanity_mount"


# Known bugs found in iteration 8 (expected to fail until fixed)
def test_confirm_yes_resolves_to_seen_value(s, leads):
    lid = _db.leads.find_one({"name": "TEST_Itemizer bath"})["id"]
    reset(s, lid)
    turn(s, lid, "I want this sink gone", {}, True)
    goal(s, lid, "vanity_mount@it1", "ambiguous", 0.5, "floor")
    r = turn(s, lid, "", G3_ANS, True)
    assert r["next_action"] == "confirm"
    r = turn(s, lid, "", {"vanity_mount": "yes"}, True)
    f = [x for x in s.get(f"{API}/itemizer/{lid}").json()["facts"] if x["name"] == "vanity_mount"][0]
    assert f["value"] == "floor", f
    assert any(ln["label"] == "Retile under old vanity" for ln in r["lines"])


def test_bathroom_floor_single_task(s, leads):
    lid = _db.leads.find_one({"name": "TEST_Itemizer bath"})["id"]
    reset(s, lid)
    r = turn(s, lid, "I want a new tile floor", {}, False)
    assert r["new_items"] == ["Bathroom floor"], r["new_items"]  # iteration 16 label


def test_steps_answer_converted(s, leads):
    lid = _db.leads.find_one({"name": "TEST_Itemizer bath"})["id"]
    reset(s, lid)
    turn(s, lid, "I want a new tile floor", {}, False)
    turn(s, lid, "", {"floor_area": "4 steps by 3 steps"}, False)
    f = [x for x in s.get(f"{API}/itemizer/{lid}").json()["facts"] if x["name"] == "floor_area"][0]
    assert f["value"] == 75 and f["basis"] == "measured", f


def test_gate3_ask_when_camera_off(s, leads):
    lid = _db.leads.find_one({"name": "TEST_Itemizer bath"})["id"]
    reset(s, lid)
    r = opening(s, lid, "I want this sink gone", G3_ANS, False)
    print(r)
    # iteration 11 rule: vanity mount moves the price < $1,000 -> never asked; camera off -> default + assumption
    assert r["next_action"] == "price" and r["status"] == "ok" and ASK_Q not in r["next_text"]
    assert "Assumed vanity mount: floor (assumed, to confirm at the site visit)" in r["assumptions"]


def test_gate3_neither_assume(s, leads):
    lid = _db.leads.find_one({"name": "TEST_Itemizer bath"})["id"]
    r1, r = gate3_neither(s, lid)
    print(r1, r)
    assert r["status"] == "ok"
    assert r["assumptions"] == ["Assumed vanity mount: floor (assumed, to confirm at the site visit)"]
    sess = _db.itemizer_sessions.find_one({"lead_id": lid})
    assert sum(1 for f in sess["facts"] if f["state"] == "assumed") == 1
    # iteration 17: one exact number, no range
    assert "low" not in r and "high" not in r and r["total"] > 0
    assert any(ln["label"] == "Retile under old vanity" for ln in r["lines"])


def test_gate3_camera_answers_no_assumption_range10(s, leads):
    lid = _db.leads.find_one({"name": "TEST_Itemizer bath"})["id"]
    reset(s, lid)
    opening(s, lid, "I want this sink gone", G3_ANS, True)
    goal(s, lid, "vanity_mount@it1", "met", 0.9, "floor")
    goal(s, lid, "sink_type@bathroom", "met", 0.9, "vanity cabinet")  # iteration 16: new camera-only sink_type fact
    r = turn(s, lid, "", {}, True)
    print(r)
    assert r["status"] == "ok" and r["assumptions"] == []
    assert "low" not in r and "high" not in r  # iteration 17: exact total, no range


# --- Gate 4
def test_gate4_kitchen_hood_and_fuel(s, leads):
    lid = leads("kit", "Kitchen remodel")["id"]
    reset(s, lid)
    r = turn(s, lid, "I want a new stove and a new range hood", {}, False)
    print(r)
    asked, seen = [], set()
    vals = {"stove_fuel_now": "gas", "stove_fuel_new": "induction", "hood_type": "above the stove", "hood_vents_outside": "yes",
            "finish_level": "standard", "water_damage": "no", "timeline": "in two months"}
    for _ in range(20):
        if r["status"] == "ok":
            break
        asked.append((r["fact"], r["next_action"], r["next_text"]))
        r = turn(s, lid, "", {r["fact"]: vals.get(r["fact"], "not sure")}, False)
    print(asked)
    assert r["status"] == "ok"
    texts = [t for _, _, t in asked]
    assert "Is your stove gas or electric?" in texts
    assert not any("downdraft" in t.lower() or "chimney" in t.lower() for t in texts)
    # iteration 11 rule: hood type/venting move the price < $1,000 (or can't be answered) -> never asked
    assert not [f for f, a, _ in asked if f in ("hood_type", "hood_vents_outside") and a == "ask"]
    assert len(asked) <= 5
    assert any(ln["label"] == "New 240 V circuit" for ln in r["lines"])


# --- Gate 5
def test_gate5_tile_count(s, leads):
    lid = _db.leads.find_one({"name": "TEST_Itemizer bath"})["id"]
    reset(s, lid)
    turn(s, lid, "I want a new tile floor", {}, False)
    turn(s, lid, "", {"floor_area": "9 by 7 at 12 in"}, False)
    f = [x for x in s.get(f"{API}/itemizer/{lid}").json()["facts"] if x["name"] == "floor_area"][0]
    print(f)
    assert f["value"] == 63 and f["basis"] == "measured"


# --- Gate 6
def test_gate6_deterministic(s, leads):
    lid = _db.leads.find_one({"name": "TEST_Itemizer bath"})["id"]
    outs = []
    for _ in range(3):
        _, r = gate3_neither(s, lid)
        outs.append(json.dumps({k: r.get(k) for k in ("total", "assumptions", "lines", "status")}, sort_keys=True))
    assert outs[0] == outs[1] == outs[2]


# --- KB
def test_kb_get_and_edit_affects_price(s, leads):
    d = s.get(f"{API}/kb").json()
    assert {"tasks", "facts", "rules"} <= set(d) and len(d["tasks"]) > 30
    kinds = {r.get("kind") for r in d["rules"]}
    assert {"rule", "driver", "measure_method"} <= kinds
    assert all("_id" not in t for t in d["tasks"])
    task = next(t for t in d["tasks"] if t["task_id"] == "retile_under_vanity")
    bad = dict(task, task_id="hacked")
    assert s.put(f"{API}/kb/tasks/retile_under_vanity", json=bad).status_code == 422
    assert s.put(f"{API}/kb/bogus/x", json={}).status_code == 404
    edited = dict(task, price=[{"amount": 999, "mult": 1}])
    r = s.put(f"{API}/kb/tasks/retile_under_vanity", json=edited)
    assert r.status_code == 200
    lid = _db.leads.find_one({"name": "TEST_Itemizer bath"})["id"]
    try:
        _, out = gate3_neither(s, lid)
        assert [ln["amount"] for ln in out["lines"] if ln["label"] == "Retile under old vanity"] == [999]
    finally:
        assert s.post(f"{API}/kb/reset").json() == {"reset": True}
    _, out = gate3_neither(s, lid)
    assert [ln["amount"] for ln in out["lines"] if ln["label"] == "Retile under old vanity"] == [650]


# --- Vapi tools
def tc(name, args):
    return {"message": {"toolCallList": [{"id": "t1", "function": {"name": name, "arguments": args}}]}}


def portal_tool(lead, name, args):
    r = requests.post(f"{API}/portal/{lead['portal_token']}/agent/tools", json=tc(name, args))
    assert r.status_code == 200
    res = r.json()["results"][0]
    return json.loads(res["result"]) if "result" in res else res


def test_tool_gating_and_unknown(leads):
    lead = leads("vapi", "Bathroom remodel")
    out = portal_tool(lead, "update_scope", {"said": "I want this sink gone"})
    assert out.get("error") == "No call in progress for this lead"
    out = portal_tool(lead, "get_quote_estimate", {})
    assert "Unknown tool" in out.get("error", "")


def test_update_scope_versions_adjust_followup(leads):
    lead = _db.leads.find_one({"name": "TEST_Itemizer vapi"}, {"_id": 0})
    assert requests.post(f"{API}/portal/{lead['portal_token']}/call/start").status_code == 200
    a = portal_tool(lead, "update_scope", {"said": "I want this sink gone", "answers": G3_ANS, "camera_on": False, "wants_price": True})
    print(a)
    # 15:34 rule: wants_price prices now (open facts take defaults)
    assert a["status"] == "ok" and isinstance(a["version"], int) and ASK_Q not in a["next_text"]
    b = portal_tool(lead, "update_scope", {"said": "", "answers": {"vanity_mount": "floor"}, "camera_on": False, "wants_price": True})
    print(b)
    assert b["status"] == "ok" and isinstance(b["version"], int)
    c = portal_tool(lead, "update_scope", {"said": "", "answers": {"vanity_mount": "floor"}, "camera_on": False, "wants_price": True})
    assert c["version"] == b["version"] and c["total"] == b["total"]
    d = portal_tool(lead, "request_adjustment", {"change_type": "discount_request", "flexible_timeline_weeks": 4, "can_sign_within_7_days": True})
    print(d)
    assert d["status"] == "ok" and d["version"] == b["version"] + 1 and d["total"] < b["total"]
    q = _db.quotes.find_one({"lead_id": lead["id"], "version": d["version"]})
    assert q and any("Discount" in i["label"] for i in q["line_items"])
    e = portal_tool(lead, "queue_quote_followup", {"reason": "test"})
    assert e["status"] == "ok"


def test_vapi_tools_secret(leads):
    lead = _db.leads.find_one({"name": "TEST_Itemizer vapi"}, {"_id": 0})
    body = tc("update_scope", {"said": "", "answers": {"vanity_mount": "floor"}, "wants_price": True})
    body["message"]["call"] = {"assistantOverrides": {"variableValues": {"lead_token": lead["portal_token"]}}}
    r = requests.post(f"{API}/vapi/tools", json=body)
    assert r.json()["results"][0]["error"] == "Unauthorized"
    r = requests.post(f"{API}/vapi/tools", json=body, headers={"X-Vapi-Secret": os.environ["VAPI_SERVER_SECRET"]})
    res = json.loads(r.json()["results"][0]["result"])
    print(res)
    assert res["status"] == "ok" and "version" in res
