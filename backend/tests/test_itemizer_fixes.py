# Iteration 9: retests for iteration-8 itemizer fixes (confirm, floor dedupe, steps, KB ids/validation, goal versions, skips, water damage).
# Uses only TEST_ leads with a non-allowlisted phone; never calls /dev/reset; cleans up after itself.
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
G3_ANS = {"finish_level": "standard", "water_damage": "no", "timeline": "in two months", "sinks": "1", "replacing_vanity": "open"}
VANITY_Q = "Are you putting a new vanity there, or leaving the space open?"


@pytest.fixture(scope="module")
def s(owner_token):
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {owner_token}", "Origin": BASE_URL})
    return sess


@pytest.fixture(scope="module")
def L(s):
    made = {}

    def make(key, ask):
        if key in made:
            return made[key]
        r = s.post(f"{API}/leads", json={"name": f"TEST_Fix9 {key}", "phone": SAFE_PHONE, "source": "website", "ask": ask})
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
        for c in ("itemizer_sessions", "quotes", "sms_log", "call_sessions", "followups", "pricing_states", "contracts", "payments", "frames"):
            _db[c].delete_many({"lead_id": lead["id"]})
        _db.leads.delete_one({"id": lead["id"]})


def turn(s, lid, said="", answers=None, camera_on=False):
    r = s.post(f"{API}/itemizer/{lid}/turn", json={"said": said, "answers": answers or {}, "camera_on": camera_on})
    assert r.status_code == 200, r.text
    return r.json()


def goal(s, lid, fact_id, status, conf=0.0, value=None, code=200):
    r = s.post(f"{API}/itemizer/{lid}/goal-result", json={"fact_id": fact_id, "status": status, "confidence": conf, "value": value})
    assert r.status_code == code, r.text
    return r.json()


def reset(s, lid):
    assert s.post(f"{API}/itemizer/{lid}/reset").json() == {"reset": True}


def fact(s, lid, name):
    return [x for x in s.get(f"{API}/itemizer/{lid}").json()["facts"] if x["name"] == name][0]


def drive(s, lid, r, vals, camera_on=False, n=20):
    for _ in range(n):
        if r["status"] == "ok":
            return r
        r = turn(s, lid, "", {r["fact"]: vals.get(r["fact"], "not sure")}, camera_on)
    return r


# FIX 1 confirm flow
def test_confirm_yes(s, L):
    lid = L("bath", "Bathroom remodel")["id"]
    reset(s, lid)
    turn(s, lid, "I want this sink gone", {}, True)
    goal(s, lid, "vanity_mount@it1", "ambiguous", 0.5, "floor")
    r = turn(s, lid, "", G3_ANS, True)
    assert r["next_action"] == "confirm" and r["fact"] == "vanity_mount" and "floor" in r["next_text"], r
    r = turn(s, lid, "", {"vanity_mount": "Yes."}, True)
    f = fact(s, lid, "vanity_mount")
    assert f["value"] == "floor" and f["basis"] == "seen" and f.get("pending_confirm") is None, f
    assert r["status"] == "ok" and any(ln["label"] == "Retile under old vanity" for ln in r["lines"]), r


def test_confirm_no_moves_down_ladder(s, L):
    lid = L("bath", "Bathroom remodel")["id"]
    reset(s, lid)
    turn(s, lid, "I want this sink gone", {}, True)
    goal(s, lid, "vanity_mount@it1", "ambiguous", 0.5, "floor")
    turn(s, lid, "", G3_ANS, True)
    r = turn(s, lid, "", {"vanity_mount": "no"}, True)
    f = fact(s, lid, "vanity_mount")
    print(r, f["ladder"], f["idx"], f["state"])
    assert f["value"] != "floor" or f["basis"] != "seen"
    assert f.get("pending_confirm") is None
    assert any(a.get("result") == "rejected" for a in f["attempts"])
    assert r["fact"] == "vanity_mount" and r["next_action"] in ("show", "ask"), r


# FIX 2
@pytest.mark.parametrize("said", ["I want a new tile floor", "new floor tile please", "replace the bathroom floor"])
def test_bath_floor_single(s, L, said):
    lid = L("bath", "Bathroom remodel")["id"]
    reset(s, lid)
    r = turn(s, lid, said, {}, False)
    assert "Flooring" not in r["new_items"], r["new_items"]


# FIX 3 steps
@pytest.mark.parametrize("ans,val", [("4 steps by 3 steps", 75), ("20 steps", 2500), ("9 by 7 at 12 in", 63)])
def test_floor_area_steps(s, L, ans, val):
    lid = L("bath", "Bathroom remodel")["id"]
    reset(s, lid)
    turn(s, lid, "I want a new tile floor", {}, False)
    turn(s, lid, "", {"floor_area": ans}, False)
    f = fact(s, lid, "floor_area")
    assert f["value"] == val and f["basis"] == "measured", f


def test_linear_steps_cabinets(s, L):
    lid = L("kit", "Kitchen remodel")["id"]
    reset(s, lid)
    turn(s, lid, "new cabinets", {}, False)
    turn(s, lid, "", {"cabinet_length": "20 steps"}, False)
    f = fact(s, lid, "cabinet_length")
    assert f["value"] == 50 and f["basis"] == "measured", f


def test_counter_area_steps_sane(s, L):
    """counter_area prompt says 'count your steps along the counters' (a linear run). 10 steps should not become 625 sq ft."""
    lid = L("kit", "Kitchen remodel")["id"]
    reset(s, lid)
    turn(s, lid, "new countertops", {}, False)
    turn(s, lid, "", {"counter_area": "10 steps"}, False)
    f = fact(s, lid, "counter_area")
    print(f)
    assert f["value"] < 150, f


# FIX 4
def test_rule_ids_unique(s, L):
    rules = s.get(f"{API}/kb").json()["rules"]
    ids = [r["rule_id"] for r in rules]
    assert len(ids) == 41 and len(set(ids)) == 41
    assert all(r["rule_id"].startswith("driver_") for r in rules if r["kind"] == "driver")
    assert all(r["rule_id"].startswith("measure_") for r in rules if r["kind"] == "measure_method")


# FIX 5 KB validation
def test_kb_validation(s, L):
    kb = s.get(f"{API}/kb").json()
    task = next(t for t in kb["tasks"] if t["task_id"] == "toilet") if any(t["task_id"] == "toilet" for t in kb["tasks"]) else kb["tasks"][0]
    tid = task["task_id"]
    factd = kb["facts"][0]
    rule = next(r for r in kb["rules"] if r["kind"] == "rule")
    drv = next(r for r in kb["rules"] if r["kind"] == "driver")
    try:
        bad = [("tasks", tid, {"task_id": tid}),
               ("tasks", tid, dict(task, price=[{"amount": "abc"}])),
               ("tasks", tid, dict(task, price=[])),
               ("tasks", tid, dict(task, triggers="x")),
               ("tasks", tid, dict(task, facts=["nope_fact"])),
               ("tasks", tid, dict(task, price=[{"tiers": [1, 2]}])),
               ("facts", factd["fact_id"], dict(factd, scope="planet")),
               ("facts", factd["fact_id"], dict(factd, ladder=["camera", "teleport"])),
               ("facts", factd["fact_id"], dict(factd, ladder=[])),
               ("rules", rule["rule_id"], dict(rule, add="not_a_task")),
               ("rules", drv["rule_id"], dict(drv, kind="weird"))]
        for kind, i, doc in bad:
            r = s.put(f"{API}/kb/{kind}/{i}", json=doc)
            assert r.status_code == 422, (kind, doc, r.status_code, r.text)
            assert isinstance(r.json()["detail"], str) and r.json()["detail"], r.text
        assert s.put(f"{API}/kb/tasks/zzz_missing", json=dict(task, task_id="zzz_missing")).status_code == 404
        # valid edits
        for kind, i, doc in (("facts", factd["fact_id"], factd), ("rules", rule["rule_id"], rule), ("rules", drv["rule_id"], dict(drv, name="X"))):
            r = s.put(f"{API}/kb/{kind}/{i}", json=doc)
            assert r.status_code == 200, (kind, r.text)
        # after bad attempts the itemizer still works (no 500)
        lid = L("bath", "Bathroom remodel")["id"]
        reset(s, lid)
        turn(s, lid, "replace the toilet", {}, False)
    finally:
        assert s.post(f"{API}/kb/reset").json() == {"reset": True}
    assert next(r for r in s.get(f"{API}/kb").json()["rules"] if r["rule_id"] == drv["rule_id"])["name"] == drv["name"]


def test_kb_price_types(s, L):
    """bool/None/negative amounts and non-number qty mult"""
    kb = s.get(f"{API}/kb").json()
    task = next(t for t in kb["tasks"] if t["task_id"] == "retile_under_vanity")
    out = {}
    try:
        for name, p in (("bool", [{"amount": True}]), ("neg", [{"amount": -500}]), ("mult_str", [{"amount": 5, "mult": "x"}]),
                        ("qty_unknown", [{"amount": 5, "qty": "nope"}]), ("when_str", [{"amount": 5, "when": "x"}])):
            out[name] = s.put(f"{API}/kb/tasks/retile_under_vanity", json=dict(task, price=p)).status_code
            s.post(f"{API}/kb/reset")
    finally:
        s.post(f"{API}/kb/reset")
    print(out)
    assert out["mult_str"] == 422 and out["when_str"] == 422, out


# FIX 6 goal result after pricing -> versions
def test_goal_after_price_new_version(s, L):
    lead = L("bath", "Bathroom remodel")
    lid = lead["id"]
    reset(s, lid)
    _db.quotes.delete_many({"lead_id": lid})
    turn(s, lid, "I want this sink gone", G3_ANS, False)
    goal(s, lid, "vanity_mount@it1", "not_found")
    r = turn(s, lid, "", {"vanity_mount": "not sure"}, False)
    assert r["status"] == "ok"
    g = goal(s, lid, "vanity_mount@it1", "met", 0.95, "wall")
    print(g)
    assert isinstance(g["version"], int) and g["total_after"] < g["total_before"]
    q = _db.quotes.find_one({"lead_id": lid, "version": g["version"]}, {"_id": 0})
    assert q["total"] == g["total_after"] and q["assumptions"] == [] and q.get("source") == "itemizer"
    assert not any(i["label"] == "Retile under old vanity" for i in q["line_items"])
    g2 = goal(s, lid, "vanity_mount@it1", "met", 0.95, "wall")
    assert g2["version"] == g["version"]
    g3 = goal(s, lid, "vanity_mount@it1", "met", 0.95, "floor")
    assert g3["version"] == g["version"] + 1 and g3["total_after"] > g3["total_before"]


def test_goal_unknown_fact_404(s, L):
    lid = L("bath", "Bathroom remodel")["id"]
    r = s.post(f"{API}/itemizer/{lid}/goal-result", json={"fact_id": "nope@x", "status": "met", "confidence": 1, "value": "x"})
    assert r.status_code == 404
    r = s.post(f"{API}/itemizer/{lid}/goal-result", json={"fact_id": "x", "status": "bogus"})
    assert r.status_code == 422
    r = s.post(f"{API}/itemizer/nolead/goal-result", json={"fact_id": "x", "status": "met"})
    assert r.status_code == 404


def test_dedupe_assumption_change_new_version(L):
    lead = L("vapi", "Bathroom remodel")
    assert requests.post(f"{API}/portal/{lead['portal_token']}/call/start").status_code == 200
    ans = dict(G3_ANS, water_damage="not sure", vanity_mount="floor")
    a = tool(lead, "update_scope", {"said": "I want this sink gone", "answers": ans})
    for _ in range(5):
        if a["status"] == "ok":
            break
        a = tool(lead, "update_scope", {"said": "", "answers": {a["fact"]: ans.get(a["fact"], "not sure")}})
    print(a)
    assert a["status"] == "ok" and "Assumed water damage: no" in a["assumptions"]
    b = tool(lead, "update_scope", {"said": "", "answers": {"water_damage": "no"}})
    print(b)
    assert b["total"] == a["total"] and b["assumptions"] == [] and b["version"] == a["version"] + 1
    c = tool(lead, "update_scope", {"said": "", "answers": {"water_damage": "no"}})
    assert c["version"] == b["version"]


def test_vapi_goal_then_update_scope_same_version(s, L):
    lead = L("vapi", "Bathroom remodel")
    g = goal(s, lead["id"], "vanity_mount@it1", "met", 0.95, "wall")
    assert isinstance(g["version"], int)
    c = tool(lead, "update_scope", {"said": "", "answers": {}})
    print(g, c)
    assert c["status"] == "ok" and c["version"] == g["version"] and c["total"] == g["total_after"]


# FIX 7 skips
def test_unanswered_reasked_once_then_advances(s, L):
    lid = L("bath", "Bathroom remodel")["id"]
    reset(s, lid)
    r = turn(s, lid, "I want this sink gone", {}, False)
    assert r["fact"] == "replacing_vanity" and r["next_text"] == VANITY_Q
    r = turn(s, lid, "", {"sinks": "1"}, False)
    print(r)
    assert r["fact"] == "replacing_vanity" and r["next_text"] == VANITY_Q, r
    f = fact(s, lid, "replacing_vanity")
    assert f["state"] == "asked"
    turn(s, lid, "", {"sinks": "1"}, False)
    f = fact(s, lid, "replacing_vanity")
    assert f["state"] == "assumed" and f["value"] == "new", f


def test_not_sure_advances_immediately(s, L):
    lid = L("bath", "Bathroom remodel")["id"]
    reset(s, lid)
    turn(s, lid, "I want this sink gone", {}, False)
    turn(s, lid, "", {"replacing_vanity": "not sure"}, False)
    f = fact(s, lid, "replacing_vanity")
    assert f["state"] == "assumed", f


# FIX 8
def test_water_damage_assumption(s, L):
    lid = L("bath", "Bathroom remodel")["id"]
    reset(s, lid)
    r = turn(s, lid, "I want this sink gone", dict(G3_ANS, water_damage="yes", vanity_mount="floor"), False)
    r = drive(s, lid, r, {"vanity_mount": "floor"})
    print(r)
    assert r["status"] == "ok"
    assert any(ln["label"] == "Water damage allowance" and ln["amount"] == 1800 for ln in r["lines"])
    assert "Water damage allowance until the site visit" in r["assumptions"]


# Tools
def tc(name, args):
    return {"message": {"toolCallList": [{"id": "t1", "function": {"name": name, "arguments": args}}]}}


def tool(lead, name, args):
    r = requests.post(f"{API}/portal/{lead['portal_token']}/agent/tools", json=tc(name, args))
    assert r.status_code == 200
    res = r.json()["results"][0]
    return json.loads(res["result"]) if "result" in res else res


def test_other_lead_token_scoping(L):
    """agent/tools with a bogus token is 404; vapi tools w/o secret is Unauthorized"""
    r = requests.post(f"{API}/portal/bogus-token/agent/tools", json=tc("update_scope", {"said": "x"}))
    assert r.status_code == 404
    r = requests.post(f"{API}/vapi/tools", json=tc("update_scope", {"said": "x"}), headers={"X-Vapi-Secret": "wrong"})
    assert r.json()["results"][0]["error"] == "Unauthorized"
