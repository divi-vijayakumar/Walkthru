# /dev/reset must rebuild only sample leads (id ^lead-) and keep real/non-sample leads + their data.
# Also: link_vapi_call scoped per lead, vapi tools/webhook link only with lead_token, seeded Maya ended_at not future.
import os
from datetime import datetime, timezone
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
REAL = ("Dhivya Vijayakumar", "Sathish Rajasekar")
LEAD_COLLS = ("itemizer_sessions", "itemizer_insights", "itemizer_goals", "quotes", "sms_log", "call_sessions",
              "followups", "pricing_states", "contracts", "payments", "frames", "messages", "scopes")


@pytest.fixture(scope="module")
def s(owner_token):
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {owner_token}", "Origin": BASE_URL})
    return sess


@pytest.fixture(scope="module")
def made(s):
    leads = []

    def make(name):
        r = s.post(f"{API}/leads", json={"name": name, "phone": SAFE_PHONE, "source": "website", "ask": "Bathroom remodel"})
        assert r.status_code == 200, r.text
        lead = r.json()["lead"]
        if not lead.get("portal_token"):
            s.post(f"{API}/leads/{lead['id']}/start-agent")
        doc = _db.leads.find_one({"id": lead["id"]}, {"_id": 0})
        leads.append(doc)
        return doc
    yield make
    for l in leads:
        for c in LEAD_COLLS:
            _db[c].delete_many({"lead_id": l["id"]})
        _db.leads.delete_one({"id": l["id"]})


def real_snapshot():
    return {l["name"]: l for l in _db.leads.find({"name": {"$in": list(REAL)}}, {"_id": 0})}


class TestResetPreservesReal:
    def test_reset_keeps_real_and_test_leads(self, s, made):
        before_real = real_snapshot()
        assert set(before_real) == set(REAL), f"real leads missing before test: {list(before_real)}"
        t = made("TEST_RESET keep")
        sid = requests.post(f"{API}/portal/{t['portal_token']}/call/start").json()["id"]
        r = s.post(f"{API}/dev/reset")
        assert r.status_code == 200 and r.json() == {"reset": True}
        after_real = real_snapshot()
        assert set(after_real) == set(REAL)
        for n in REAL:
            assert after_real[n] == before_real[n], f"{n} modified by reset"
            assert after_real[n]["status"] == "invited"
        assert _db.leads.find_one({"id": t["id"]}) is not None
        assert _db.call_sessions.find_one({"id": sid}) is not None
        samples = list(_db.leads.find({"id": {"$regex": "^lead-"}}, {"_id": 0, "id": 1}))
        assert len(samples) == 9
        dash = s.get(f"{API}/dashboard").json()["leads"]
        names = [l["name"] for l in dash]
        assert "TEST_RESET keep" in names and all(n in names for n in REAL)

    def test_dashboard_real_first(self, s):
        dash = s.get(f"{API}/dashboard").json()["leads"]
        ids = [l["id"] for l in dash]
        first_sample = next(i for i, x in enumerate(ids) if x.startswith("lead-"))
        assert all(x.startswith("lead-") for x in ids[first_sample:]), ids

    def test_maya_session_not_future(self):
        ses = _db.call_sessions.find_one({"lead_id": "lead-maya"}, {"_id": 0})
        assert ses and ses["ended_at"]
        end = datetime.fromisoformat(ses["ended_at"])
        assert end <= datetime.now(timezone.utc)
        assert end >= datetime.fromisoformat(ses["started_at"])


class TestLinkScoping:
    def test_link_other_leads_call_id_returns_false(self, made):
        a, b = made("TEST_SCOPE A"), made("TEST_SCOPE B")
        sa = requests.post(f"{API}/portal/{a['portal_token']}/call/start").json()["id"]
        sb = requests.post(f"{API}/portal/{b['portal_token']}/call/start").json()["id"]
        r = requests.post(f"{API}/portal/{a['portal_token']}/call/link", json={"vapi_call_id": "TEST_cid_scope_A"})
        assert r.json() == {"linked": True}
        r = requests.post(f"{API}/portal/{b['portal_token']}/call/link", json={"vapi_call_id": "TEST_cid_scope_A"})
        assert r.json() == {"linked": False}
        assert _db.call_sessions.find_one({"id": sb}).get("vapi_call_id") is None
        assert _db.call_sessions.find_one({"id": sa})["vapi_call_id"] == "TEST_cid_scope_A"

    def test_tools_without_token_never_links(self, made):
        c = made("TEST_NOTOKEN C")
        sc = requests.post(f"{API}/portal/{c['portal_token']}/call/start").json()["id"]
        body = {"message": {"type": "tool-calls", "call": {"id": "TEST_cid_notoken_tools"},
                            "toolCallList": [{"id": "x", "function": {"name": "queue_quote_followup", "arguments": {}}}]}}
        r = requests.post(f"{API}/vapi/tools", json=body, headers=H)
        assert r.status_code == 200
        assert _db.call_sessions.find_one({"vapi_call_id": "TEST_cid_notoken_tools"}) is None
        assert _db.call_sessions.find_one({"id": sc}).get("vapi_call_id") is None
        # cleanup any followup that fallback may have queued on a non-sample lead
        print("tools no-token result:", r.json())

    def test_webhook_status_update_without_token_never_links(self, made):
        d = made("TEST_NOTOKEN D")
        sd = requests.post(f"{API}/portal/{d['portal_token']}/call/start").json()["id"]
        body = {"message": {"type": "status-update", "status": "in-progress", "call": {"id": "TEST_cid_notoken_wh"}}}
        r = requests.post(f"{API}/vapi/webhook", json=body, headers=H)
        assert r.json() == {"received": True}
        assert _db.call_sessions.find_one({"vapi_call_id": "TEST_cid_notoken_wh"}) is None
        assert _db.call_sessions.find_one({"id": sd}).get("vapi_call_id") is None

    def test_webhook_status_update_with_token_links(self, made):
        e = made("TEST_TOKEN E")
        se = requests.post(f"{API}/portal/{e['portal_token']}/call/start").json()["id"]
        body = {"message": {"type": "status-update", "status": "in-progress",
                            "call": {"id": "TEST_cid_token_wh", "assistantOverrides": {"variableValues": {"lead_token": e["portal_token"]}}}}}
        assert requests.post(f"{API}/vapi/webhook", json=body, headers=H).json() == {"received": True}
        assert _db.call_sessions.find_one({"id": se})["vapi_call_id"] == "TEST_cid_token_wh"
