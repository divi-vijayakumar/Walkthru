# Walkthru v2 API regression: health, dashboard, vapi tools/webhook, start-agent, dev helpers, portal flow
import os
from datetime import datetime, timezone
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.post(f"{API}/dev/reset")
    yield sess
    sess.post(f"{API}/dev/reset")


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
    r = s.post(f"{API}/vapi/tools", json=body)
    assert r.status_code == 200
    return r.json()["results"]


BATH_ARGS = {"project_type": "bathroom_remodel", "room_size": "medium", "finish_level": "standard",
             "requested_changes": ["walk-in shower and double vanity"]}


# Health + dashboard
def test_health(s):
    r = s.get(f"{API}/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_dashboard_seed(s):
    d = dash(s)
    assert len(d["leads"]) == 9
    c = d["counts"]
    assert c["quote_generated"] == 2
    for st in ["new", "invited", "walkthru_initiated", "walkthru_completed", "contract_sent",
               "pending_deposit", "deposit_received"]:
        assert c[st] == 1, st
    assert d["median_time_to_quote_s"] is not None and 300 <= d["median_time_to_quote_s"] <= 500
    assert all("_id" not in l for l in d["leads"])
    assert d["leads"][0]["status"] == "walkthru_initiated" and d["leads"][0]["live"]


# Vapi tools
@pytest.mark.parametrize("body", [b"garbage", b"{}", b'{"message": {"toolCallList": [{"id": "x"}]}}', b"[]"])
def test_tools_garbage_200(s, body):
    r = s.post(f"{API}/vapi/tools", data=body, headers={"Content-Type": "application/json"})
    assert r.status_code == 200 and "results" in r.json()


def test_tools_unknown_tool(s):
    res = tool_call(s, "demo-luis", "nope", {})
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
    res = tool_call(s, token, "get_quote_estimate", BATH_ARGS)
    out = json.loads(res[0]["result"])
    assert (out["total"], out["low"], out["high"]) == (27600, 25000, 30500)
    res = tool_call(s, token, "request_adjustment", json.dumps(
        {"change_type": "discount_request", "can_sign_within_7_days": True, "flexible_timeline_weeks": 4}))
    out = json.loads(res[0]["result"])
    assert out["total"] == 27600 - round(27600 * 0.06)
    res = tool_call(s, token, "request_adjustment",
                    {"change_type": "discount_request", "can_sign_within_7_days": True, "flexible_timeline_weeks": 8})
    out = json.loads(res[0]["result"])
    assert out["status"] == "limit_reached"
    # non-bathroom
    res = tool_call(s, token, "get_quote_estimate", {"project_type": "kitchen_remodel"})
    assert json.loads(res[0]["result"])["status"] == "needs_human"
    # webhook end-of-call -> quote_generated
    body = {"message": {"type": "end-of-call-report",
                        "call": {"assistantOverrides": {"variableValues": {"lead_token": token}}}}}
    assert s.post(f"{API}/vapi/webhook", json=body).status_code == 200
    l = next(x for x in dash(s)["leads"] if x["id"] == lid)
    hist = [h["status"] for h in l["status_history"]]
    assert l["status"] == "quote_generated" and hist[-2] == "walkthru_completed"


def test_webhook_no_quote_pending(s):
    created = new_lead(s, "TEST_No Quote", ask="Deck repair")
    lid = created["lead"]["id"]
    if created["lead"]["status"] == "new":
        s.post(f"{API}/leads/{lid}/start-agent")
    token = next(l for l in dash(s)["leads"] if l["id"] == lid)["portal_token"]
    s.post(f"{API}/portal/{token}/call/start")
    body = {"message": {"type": "end-of-call-report",
                        "call": {"assistantOverrides": {"variableValues": {"lead_token": token}}}}}
    assert s.post(f"{API}/vapi/webhook", json=body).status_code == 200
    l = next(x for x in dash(s)["leads"] if x["id"] == lid)
    assert l["status"] == "walkthru_completed" and l["quote_pending"] is True
    due = datetime.fromisoformat(l["quote_pending_due_at"])
    mins = (due - datetime.now(timezone.utc)).total_seconds() / 60
    assert 13 <= mins <= 16


def test_webhook_garbage(s):
    r = s.post(f"{API}/vapi/webhook", data=b"xx", headers={"Content-Type": "application/json"})
    assert r.status_code == 200


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
    assert p["lead"]["status"] == "invited" and p["voice"]["mode"] == "mock"
    s.post(f"{API}/portal/{token}/call/start")
    assert s.post(f"{API}/portal/{token}/call/caption", json={"role": "user", "text": "hi"}).status_code == 200
    tool_call(s, token, "get_quote_estimate", BATH_ARGS)
    assert s.post(f"{API}/portal/{token}/call/end", json={}).json()["ended"] is True
    assert s.get(f"{API}/portal/{token}").json()["lead"]["status"] == "quote_generated"
    assert s.post(f"{API}/portal/{token}/contract/sign", json={"name": "X Y"}).status_code == 400
    assert s.post(f"{API}/portal/{token}/contract/open").status_code == 200
    assert s.post(f"{API}/portal/{token}/contract/sign", json={"name": "a"}).status_code == 422
    r = s.post(f"{API}/portal/{token}/contract/sign", json={"name": "TEST Portal"})
    assert r.status_code == 200 and r.json()["payment"]["amount"] == 1380
    r = s.post(f"{API}/portal/{token}/deposit/pay")
    assert r.status_code == 200 and r.json()["payment"]["status"] == "paid"
    assert s.get(f"{API}/portal/{token}").json()["lead"]["status"] == "deposit_received"
    assert s.post(f"{API}/leads/{lid}/recall-quote").status_code == 400


def test_portal_priya_fallback(s):
    p = s.get(f"{API}/portal/demo-priya").json()
    assert p["lead"]["first_name"] == "Priya" and p["quote"] is None


def test_portal_404(s):
    assert s.get(f"{API}/portal/bogus-token").status_code == 404


# Recall, take-over, transcript
def test_recall_takeover_transcript(s):
    q = next(l for l in dash(s)["leads"] if l["status"] == "quote_generated" and not l["name"].startswith("TEST_"))
    assert s.post(f"{API}/leads/{q['id']}/recall-quote").status_code == 200
    l = next(x for x in dash(s)["leads"] if x["id"] == q["id"])
    assert l["status"] == "walkthru_completed" and l["quote_total"] is None and l["quote_pending"]
    maya = lead_by_name(s, "Maya Rios")
    r = s.post(f"{API}/leads/{maya['id']}/take-over")
    assert r.status_code == 200 and r.json()["escalated"] is True
    t = s.get(f"{API}/leads/{maya['id']}/transcript").json()
    assert len(t["sessions"]) >= 1 and any(x["role"] == "system" for x in t["sessions"][0]["transcript"])
