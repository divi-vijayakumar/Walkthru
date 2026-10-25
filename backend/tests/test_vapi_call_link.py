# Vapi call-id linking: /portal/{token}/call/link, /vapi/tools + status-update linking, end-of-call-report matching by
# vapi_call_id with safe fallback; seeded sessions all ended with realistic durations. TEST_ leads only, cleaned up.
import os
from datetime import datetime
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
H = {"X-Vapi-Secret": os.environ["VAPI_SERVER_SECRET"]}


@pytest.fixture(scope="module")
def s(owner_token):
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {owner_token}", "Origin": BASE_URL})
    return sess


@pytest.fixture(scope="module")
def L(s):
    made = {}

    def make(key):
        if key in made:
            return made[key]
        r = s.post(f"{API}/leads", json={"name": f"TEST_LINK {key}", "phone": SAFE_PHONE, "source": "website", "ask": "Bathroom remodel"})
        assert r.status_code == 200, r.text
        lead = r.json()["lead"]
        if not lead.get("portal_token"):
            s.post(f"{API}/leads/{lead['id']}/start-agent")
        made[key] = _db.leads.find_one({"id": lead["id"]}, {"_id": 0})
        return made[key]
    yield make
    for lead in made.values():
        for c in ("itemizer_sessions", "itemizer_insights", "itemizer_goals", "quotes", "sms_log", "call_sessions", "followups",
                  "pricing_states", "contracts", "payments"):
            _db[c].delete_many({"lead_id": lead["id"]})
        _db.leads.delete_one({"id": lead["id"]})


def start(tok):
    r = requests.post(f"{API}/portal/{tok}/call/start")
    assert r.status_code == 200, r.text
    return r.json()["id"]


def link(tok, cid):
    return requests.post(f"{API}/portal/{tok}/call/link", json={"vapi_call_id": cid})


def sess(sid):
    return _db.call_sessions.find_one({"id": sid}, {"_id": 0})


def report(tok, cid, summary):
    msg = {"message": {"type": "end-of-call-report",
                       "call": {"id": cid, "assistantOverrides": {"variableValues": {"lead_token": tok}}},
                       "artifact": {"messages": [{"role": "bot", "message": "Hi"}, {"role": "user", "message": "Hello"}]},
                       "analysis": {"summary": summary}}}
    r = requests.post(f"{API}/vapi/webhook", json=msg, headers=H)
    assert r.json() == {"received": True}


class TestPortalLink:
    def test_link_idempotent_and_no_overwrite(self, L):
        tok = L("portal")["portal_token"]
        sid = start(tok)
        r = link(tok, "TEST_cid_portal_1")
        assert r.status_code == 200 and r.json() == {"linked": True}
        assert sess(sid)["vapi_call_id"] == "TEST_cid_portal_1"
        assert link(tok, "TEST_cid_portal_1").json() == {"linked": True}
        # a different id must not overwrite an already-linked session
        assert link(tok, "TEST_cid_portal_2").json() == {"linked": False}
        assert sess(sid)["vapi_call_id"] == "TEST_cid_portal_1"
        requests.post(f"{API}/portal/{tok}/call/end", json={})
        assert link(tok, "TEST_cid_portal_3").json() == {"linked": False}
        assert sess(sid)["vapi_call_id"] == "TEST_cid_portal_1"

    def test_link_no_open_session(self, L):
        tok = L("nosession")["portal_token"]
        assert link(tok, "TEST_cid_none").json() == {"linked": False}
        assert _db.call_sessions.count_documents({"vapi_call_id": "TEST_cid_none"}) == 0

    def test_link_validation(self, L):
        tok = L("nosession")["portal_token"]
        assert link(tok, "").status_code == 422
        assert requests.post(f"{API}/portal/{tok}/call/link", json={}).status_code == 422
        assert link("TEST_badtoken", "TEST_x").status_code == 404

    def test_link_existing_id_other_lead(self, L):
        # id already on lead A's session: linking from lead B reports linked:true but must not move it
        tok_a, tok_b = L("portal")["portal_token"], L("other")["portal_token"]
        sid_b = start(tok_b)
        r = link(tok_b, "TEST_cid_portal_1").json()
        print("cross-lead link response:", r)
        assert sess(sid_b).get("vapi_call_id") is None
        assert _db.call_sessions.count_documents({"vapi_call_id": "TEST_cid_portal_1"}) == 1
        requests.post(f"{API}/portal/{tok_b}/call/end", json={})


class TestVapiLinking:
    def test_tools_links_call_id(self, L):
        tok = L("tools")["portal_token"]
        sid = start(tok)
        body = {"message": {"type": "tool-calls",
                            "call": {"id": "TEST_cid_tools", "assistantOverrides": {"variableValues": {"lead_token": tok}}},
                            "toolCallList": [{"id": "tc1", "function": {"name": "TEST_no_such_tool", "arguments": {}}}]}}
        r = requests.post(f"{API}/vapi/tools", json=body, headers=H)
        assert r.status_code == 200 and r.json()["results"][0]["toolCallId"] == "tc1"
        assert sess(sid)["vapi_call_id"] == "TEST_cid_tools"
        requests.post(f"{API}/portal/{tok}/call/end", json={})

    def test_tools_unauthorized_does_not_link(self, L):
        tok = L("tools_unauth")["portal_token"]
        sid = start(tok)
        body = {"message": {"call": {"id": "TEST_cid_unauth", "assistantOverrides": {"variableValues": {"lead_token": tok}}},
                            "toolCallList": [{"id": "tc1", "function": {"name": "x", "arguments": {}}}]}}
        r = requests.post(f"{API}/vapi/tools", json=body, headers={"X-Vapi-Secret": "wrong"})
        assert r.json()["results"][0]["error"] == "Unauthorized"
        assert sess(sid).get("vapi_call_id") is None
        requests.post(f"{API}/portal/{tok}/call/end", json={})

    def test_status_update_links(self, L):
        tok = L("status")["portal_token"]
        sid = start(tok)
        body = {"message": {"type": "status-update", "status": "in-progress",
                            "call": {"id": "TEST_cid_status", "assistantOverrides": {"variableValues": {"lead_token": tok}}}}}
        r = requests.post(f"{API}/vapi/webhook", json=body, headers=H)
        assert r.json() == {"received": True}
        assert sess(sid)["vapi_call_id"] == "TEST_cid_status"
        lead = _db.leads.find_one({"portal_token": tok})
        assert lead["status"] == "walkthru_initiated"  # status-update does not end anything
        requests.post(f"{API}/portal/{tok}/call/end", json={})


class TestReportMatching:
    def test_report_matches_older_session_by_id(self, L):
        tok = L("match")["portal_token"]
        sid_a = start(tok)
        link(tok, "TEST_cid_A")
        requests.post(f"{API}/portal/{tok}/call/end", json={})
        sid_b = start(tok)  # newer open session
        report(tok, "TEST_cid_A", "TEST summary A")
        a, b = sess(sid_a), sess(sid_b)
        assert a["summary"] == "TEST summary A" and a["vapi_call_id"] == "TEST_cid_A"
        assert b.get("summary") is None and b.get("vapi_call_id") is None and b["ended_at"] is None
        assert _db.leads.find_one({"portal_token": tok})["status"] == "walkthru_initiated"
        # unknown id -> falls back to latest session without a vapi_call_id (B), ends it
        report(tok, "TEST_cid_B", "TEST summary B")
        a, b = sess(sid_a), sess(sid_b)
        assert a["summary"] == "TEST summary A" and a["vapi_call_id"] == "TEST_cid_A"
        assert b["summary"] == "TEST summary B" and b["vapi_call_id"] == "TEST_cid_B" and b["ended_at"]

    def test_report_unknown_id_never_overwrites(self, L):
        tok = L("match")["portal_token"]  # both sessions now linked
        before = list(_db.call_sessions.find({"lead_id": _db.leads.find_one({"portal_token": tok})["id"]}, {"_id": 0, "id": 1, "summary": 1, "vapi_call_id": 1}))
        report(tok, "TEST_cid_C", "TEST summary C")
        after = list(_db.call_sessions.find({"lead_id": _db.leads.find_one({"portal_token": tok})["id"]}, {"_id": 0, "id": 1, "summary": 1, "vapi_call_id": 1}))
        assert before == after


class TestSeeded:
    def test_seeded_sessions_ended_realistic(self):
        rows = list(_db.call_sessions.find({"id": {"$regex": "^session-lead-"}}, {"_id": 0, "id": 1, "started_at": 1, "ended_at": 1}))
        assert rows
        for r in rows:
            assert r["ended_at"], r["id"]
            d = (datetime.fromisoformat(r["ended_at"]) - datetime.fromisoformat(r["started_at"])).total_seconds()
            print(r["id"], int(d))
            assert 0 < d < 3600, (r["id"], d)
