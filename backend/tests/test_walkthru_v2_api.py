# Walkthru v2 API regression: health, dashboard, portal agent tools/end (vapi locked), start-agent, dev helpers, portal flow
import os
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def s(owner_token):
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {owner_token}"})
    sess.post(f"{API}/dev/reset")
    before = sess.get(f"{API}/dashboard").json()["contractor"].get("agent_enabled")
    yield sess
    sess.post(f"{API}/dev/reset")
    sess.patch(f"{API}/contractor", json={"agent_enabled": bool(before)})


def dash(s):
    return s.get(f"{API}/dashboard").json()


def lead_by_name(s, name):
    return next(l for l in dash(s)["leads"] if l["name"] == name)


def set_agent(s, on):
    r = s.patch(f"{API}/contractor", json={"agent_enabled": on})
    assert r.status_code == 200 and r.json()["agent_enabled"] is on


def new_lead(s, name, ask="Bathroom remodel", phone="555-010-1234"):
    r = s.post(f"{API}/leads", json={"name": name, "phone": phone, "source": "website", "ask": ask})
    assert r.status_code == 200, r.text
    return r.json()


def tool_call(s, token, name, args, tid="tc1"):
    body = {"message": {"type": "tool-calls", "call": {"assistantOverrides": {"variableValues": {"lead_token": token}}},
                        "toolCallList": [{"id": tid, "function": {"name": name, "arguments": args}}]}}
    r = s.post(f"{API}/portal/{token}/agent/tools", json=body)
    assert r.status_code == 200
    return r.json()["results"]


def end_call(s, token):
    body = {"message": {"type": "end-of-call-report",
                        "call": {"assistantOverrides": {"variableValues": {"lead_token": token}}}}}
    r = s.post(f"{API}/portal/{token}/agent/end", json=body)
    assert r.status_code == 200
    return r.json()


def token_of(s, name):
    return lead_by_name(s, name)["portal_token"]


# update_scope args that price in one turn (itemizer): remove vanity, leave open, floor mount
BATH_ARGS = {"said": "I want this sink gone", "camera_on": False, "answers": {
    "finish_level": "standard", "water_damage": "no", "timeline": "in two months", "sinks": "1",
    "replacing_vanity": "open", "vanity_mount": "floor"}}


# Health + dashboard
def test_health(s):
    r = s.get(f"{API}/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_dashboard_seed(s):
    d = dash(s)
    samples = [l for l in d["leads"] if l["id"].startswith("lead-")]
    assert len(samples) == 9
    c = {st: sum(l["status"] == st for l in samples) for st in {l["status"] for l in samples}}
    assert c["quote_generated"] == 2
    for st in ["new", "invited", "walkthru_initiated", "walkthru_completed", "contract_sent",
               "pending_deposit", "deposit_received"]:
        assert c[st] == 1, st
    assert all("_id" not in l for l in d["leads"])


# Vapi tools
@pytest.mark.parametrize("body", [b"garbage", b"{}", b'{"message": {"toolCallList": [{"id": "x"}]}}', b"[]"])
def test_tools_garbage_200(s, body):
    tok = token_of(s, "Priya Shah")
    r = s.post(f"{API}/portal/{tok}/agent/tools", data=body, headers={"Content-Type": "application/json"})
    assert r.status_code == 200 and "results" in r.json()


def test_tools_unknown_tool(s):
    res = tool_call(s, token_of(s, "Priya Shah"), "nope", {})
    assert res[0]["toolCallId"] == "tc1" and "error" in res[0]


def test_estimate_and_discount(s):
    import json
    created = new_lead(s, "TEST_Bath Est")
    lid = created["lead"]["id"]
    if created["lead"]["status"] == "new":
        s.post(f"{API}/leads/{lid}/start-agent")
    token = s.get(f"{API}/dashboard").json()
    token = next(l for l in token["leads"] if l["id"] == lid)["portal_token"]
    assert s.post(f"{API}/portal/{token}/call/start").status_code == 200
    res = tool_call(s, token, "update_scope", {**BATH_ARGS, "wants_price": True})
    out = json.loads(res[0]["result"])
    assert out["status"] == "ok" and out["total"] > 0 and "low" not in out and "high" not in out
    base = out["total"]
    res = tool_call(s, token, "request_adjustment", json.dumps(
        {"change_type": "discount_request", "can_sign_within_7_days": True, "flexible_timeline_weeks": 4}))
    out = json.loads(res[0]["result"])
    assert out["total"] == base - round(base * 0.06)
    res = tool_call(s, token, "request_adjustment",
                    {"change_type": "discount_request", "can_sign_within_7_days": True, "flexible_timeline_weeks": 8})
    out = json.loads(res[0]["result"])
    assert out["status"] == "limit_reached"
    # non-bathroom
    # legacy tool is gone
    res = tool_call(s, token, "get_quote_estimate", {"project_type": "kitchen_remodel"})
    assert "Unknown tool" in res[0]["error"]
    # webhook end-of-call -> quote_generated
    assert end_call(s, token)["ended"] is True
    l = next(x for x in dash(s)["leads"] if x["id"] == lid)
    hist = [h["status"] for h in l["status_history"]]
    assert l["status"] == "quote_generated" and hist[-2] == "walkthru_completed"


def test_webhook_backstop_quote(s):
    created = new_lead(s, "TEST_No Quote", ask="Deck repair")
    lid = created["lead"]["id"]
    if created["lead"]["status"] == "new":
        s.post(f"{API}/leads/{lid}/start-agent")
    token = next(l for l in dash(s)["leads"] if l["id"] == lid)["portal_token"]
    s.post(f"{API}/portal/{token}/call/start")
    assert end_call(s, token)["ended"] is True
    l = next(x for x in dash(s)["leads"] if x["id"] == lid)
    assert l["status"] == "quote_generated" and l["quote_total"] > 0 and not l["quote_pending"]


def test_webhook_garbage(s):
    r = s.post(f"{API}/vapi/webhook", data=b"xx", headers={"Content-Type": "application/json"})
    assert r.status_code == 200 and r.json()["received"] is False
    tok = token_of(s, "Priya Shah")
    r = s.post(f"{API}/portal/{tok}/agent/end", data=b"xx", headers={"Content-Type": "application/json"})
    assert r.status_code in (200, 400, 422)


# Start agent
def test_start_agent(s):
    set_agent(s, False)
    lead = new_lead(s, "TEST_Start Agent")["lead"]
    assert lead["status"] == "new"
    r = s.post(f"{API}/leads/{lead['id']}/start-agent")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "invited" and d["sms"]["simulated"] is True and "/w/" in d["link"]
    r2 = s.post(f"{API}/leads/{lead['id']}/start-agent")
    assert r2.status_code == 200 and r2.json()["link"] == d["link"]
    maya = lead_by_name(s, "Maya Rios")
    assert s.post(f"{API}/leads/{maya['id']}/start-agent").status_code == 400
    assert s.post(f"{API}/leads/nope/start-agent").status_code == 404


def test_agent_on_autoinvite(s):
    set_agent(s, True)
    out = new_lead(s, "TEST_Auto Invite")
    assert out["lead"]["status"] == "invited" and out["agent"]["sms"]["simulated"] is True
    set_agent(s, False)


def test_lead_validation(s):
    r = s.post(f"{API}/leads", json={"name": "A", "phone": "1", "source": "x", "ask": ""})
    assert r.status_code == 422


# Dev advance through all statuses
def test_dev_advance_all(s):
    set_agent(s, False)
    lid = new_lead(s, "TEST_Advance", ask="Kitchen remodel")["lead"]["id"]
    seen = []
    for _ in range(7):
        r = s.post(f"{API}/dev/leads/{lid}/advance")
        assert r.status_code == 200, r.text
        seen.append(r.json()["lead_status"])
    assert seen == ["invited", "walkthru_initiated", "walkthru_completed", "quote_generated",
                    "contract_sent", "pending_deposit", "deposit_received"]
    assert s.post(f"{API}/dev/leads/{lid}/advance").status_code == 400
    assert s.post(f"{API}/dev/leads/{lid}/drop").json()["lead_status"] == "dropped"


# Portal full flow
def test_portal_flow(s):
    import json
    lid = new_lead(s, "TEST_Portal Flow")["lead"]["id"]
    s.post(f"{API}/leads/{lid}/start-agent")
    token = next(l for l in dash(s)["leads"] if l["id"] == lid)["portal_token"]
    p = s.get(f"{API}/portal/{token}").json()
    assert p["lead"]["status"] == "invited" and p["voice"]["mode"] in ("mock", "vapi")
    s.post(f"{API}/portal/{token}/call/start")
    assert s.post(f"{API}/portal/{token}/call/caption", json={"role": "user", "text": "hi"}).status_code == 200
    tool_call(s, token, "update_scope", BATH_ARGS)
    assert s.post(f"{API}/portal/{token}/call/end", json={}).json()["ended"] is True
    assert s.get(f"{API}/portal/{token}").json()["lead"]["status"] == "quote_generated"
    assert s.post(f"{API}/portal/{token}/contract/sign", json={"name": "X Y"}).status_code == 400
    assert s.post(f"{API}/portal/{token}/contract/open").status_code == 200
    assert s.post(f"{API}/portal/{token}/contract/sign", json={"name": "a"}).status_code == 422
    r = s.post(f"{API}/portal/{token}/contract/sign", json={"name": "TEST Portal"})
    q = s.get(f"{API}/portal/{token}").json()["quote"]
    assert r.status_code == 200 and r.json()["payment"]["amount"] == q["deposit_amount"]
    # simulated /deposit/pay was removed (Stripe now); use dev advance shortcut
    assert s.post(f"{API}/portal/{token}/deposit/pay").status_code in (404, 405)
    r = s.post(f"{API}/dev/leads/{lid}/advance")
    assert r.status_code == 200 and r.json()["lead_status"] == "deposit_received"
    assert s.get(f"{API}/portal/{token}").json()["lead"]["status"] == "deposit_received"
    assert s.post(f"{API}/leads/{lid}/recall-quote").status_code == 400


def test_portal_priya_fallback(s):
    p = s.get(f"{API}/portal/{token_of(s, 'Priya Shah')}").json()
    assert p["lead"]["status"] == "walkthru_completed"
    assert p["lead"]["first_name"] == "Priya" and p["quote"] is None


def test_portal_404(s):
    assert s.get(f"{API}/portal/bogus-token").status_code == 404


# Recall, take-over, transcript
def test_recall_takeover_transcript(s):
    q = next(l for l in dash(s)["leads"] if l["status"] == "quote_generated" and l["id"].startswith("lead-"))
    assert s.post(f"{API}/leads/{q['id']}/recall-quote").status_code == 200
    l = next(x for x in dash(s)["leads"] if x["id"] == q["id"])
    assert l["status"] == "walkthru_completed" and l["quote_total"] is None and l["quote_pending"]
    maya = lead_by_name(s, "Maya Rios")
    r = s.post(f"{API}/leads/{maya['id']}/take-over")
    assert r.status_code == 200 and r.json()["escalated"] is True
    t = s.get(f"{API}/leads/{maya['id']}/transcript").json()
    assert len(t["sessions"]) >= 1  # Maya's seeded call has ended, so no live-call system line is added
