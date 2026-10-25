# Round 1 (calls first): 7-day week counts, seeded sessions ended, real-first sort, Sessions API (/api/calls),
# Vapi end-of-call-report saving (transcript/recording/summary, signed recording link), take over, in-person visit.
# Only TEST_ leads with (408) 555-0199 (WhatsApp simulated); cleans up after itself.
import os
import time
from datetime import datetime, timedelta, timezone
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
SECRET = os.environ["VAPI_SERVER_SECRET"]
AUDIO = "https://download.samplelib.com/wav/sample-3s.wav"
TAKEOVER_TPL = "Take over: call {name} now at {phone}. They're expecting your call."


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
        r = s.post(f"{API}/leads", json={"name": f"TEST_R1 {key}", "phone": SAFE_PHONE, "source": "website", "ask": ask})
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


def tools(token, name, args):
    r = requests.post(f"{API}/portal/{token}/agent/tools",
                      json={"message": {"toolCallList": [{"id": "tc1", "function": {"name": name, "arguments": args}}]}})
    assert r.status_code == 200, r.text
    return r.json()["results"][0]


# ---- Dashboard week line / sort / live
class TestDashboard:
    def test_week_counts_match_status_history(self, s):
        d = s.get(f"{API}/dashboard").json()
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        leads = list(_db.leads.find({"contractor_id": {"$exists": True}}, {"_id": 0}))
        exp = {}
        for k, st in (("invited", "invited"), ("completed", "walkthru_completed"), ("quotes", "quote_generated"), ("contracts", "pending_deposit")):
            exp[k] = {lead["id"] for lead in leads if any(h["status"] == st and h["at"] >= since for h in lead["status_history"])}
        exp["new"] = {lead["id"] for lead in leads if (lead.get("created_at") or lead["status_history"][0]["at"]) >= since}
        assert set(d["week"]) == {"invited", "completed", "quotes", "contracts", "new"}
        for k in exp:
            assert set(d["week"][k]) == exp[k], k
        print({k: len(v) for k, v in d["week"].items()})

    def test_seeded_sessions_ended_and_no_live_maya(self, s):
        assert _db.call_sessions.count_documents({"id": {"$regex": "^session-lead-"}, "ended_at": None}) == 0
        d = s.get(f"{API}/dashboard").json()
        maya = next(lead for lead in d["leads"] if lead["id"] == "lead-maya")
        assert maya["live"] is None
        assert maya["sample"] is True

    def test_real_leads_first(self, s):
        flags = [lead["sample"] for lead in s.get(f"{API}/dashboard").json()["leads"]]
        assert flags == sorted(flags)
        assert all(f == lead["id"].startswith("lead-") for f, lead in zip(flags, s.get(f"{API}/dashboard").json()["leads"]))


# ---- Sessions API + Vapi end-of-call report
class TestCallsAndReport:
    def test_calls_requires_auth(self):
        assert requests.get(f"{API}/calls").status_code in (401, 403)

    def test_report_after_portal_end(self, s, L):
        lead = L("report")
        tok = lead["portal_token"]
        sess = requests.post(f"{API}/portal/{tok}/call/start").json()
        requests.post(f"{API}/portal/{tok}/call/caption", json={"role": "user", "text": "hi"})
        assert requests.post(f"{API}/portal/{tok}/call/end", json={}).status_code == 200
        before = _db.call_sessions.find_one({"id": sess["id"]})
        status_before = _db.leads.find_one({"id": lead["id"]})["status"]
        hist_len = len(_db.leads.find_one({"id": lead["id"]})["status_history"])
        msg = {"message": {"type": "end-of-call-report",
                           "call": {"id": "TEST_vapi_call_1", "assistantOverrides": {"variableValues": {"lead_token": tok}}},
                           "artifact": {"messages": [{"role": "system", "message": "sys"}, {"role": "bot", "message": "Hi, I'm Alex."},
                                                     {"role": "user", "message": "I want a new vanity."}],
                                        "recordingUrl": AUDIO},
                           "analysis": {"summary": "TEST summary: vanity swap."}}}
        r = requests.post(f"{API}/vapi/webhook", json=msg, headers={"X-Vapi-Secret": SECRET})
        assert r.json() == {"received": True}
        after = _db.call_sessions.find_one({"id": sess["id"]})
        assert after["ended_at"] == before["ended_at"]
        assert after["vapi_call_id"] == "TEST_vapi_call_1"
        assert after["summary"] == "TEST summary: vanity swap."
        assert after["recording_url"] == AUDIO
        assert [t["role"] for t in after["transcript"]] == ["assistant", "user"]
        lead2 = _db.leads.find_one({"id": lead["id"]})
        assert lead2["status"] == status_before and len(lead2["status_history"]) == hist_len
        for _ in range(20):
            if _db.call_sessions.find_one({"id": sess["id"]}).get("recording_path"):
                break
            time.sleep(1)
        assert _db.call_sessions.find_one({"id": sess["id"]}).get("recording_path")
        # list
        rows = s.get(f"{API}/calls").json()["calls"]
        row = next(c for c in rows if c["id"] == sess["id"])
        for k in ("id", "lead_name", "started_at", "ended_at", "duration_s", "outcome", "quote_total", "has_recording"):
            assert k in row
        assert row["has_recording"] is True and row["lead_name"] == "TEST_R1 report"
        # detail + signed link
        det = s.get(f"{API}/calls/{sess['id']}").json()
        assert det["summary"] == "TEST summary: vanity swap."
        assert len(det["transcript"]) == 2 and "/api/call-recordings/" in det["recording"] and "sig=" in det["recording"]
        for k in ("findings", "quotes"):
            assert isinstance(det[k], list)
        rec = requests.get(det["recording"])
        assert rec.status_code == 200 and rec.headers["content-type"].startswith("audio") and len(rec.content) > 1000
        bad = det["recording"].rsplit("sig=", 1)[0] + "sig=deadbeef"
        assert requests.get(bad).status_code == 403
        d = s.get(f"{API}/dashboard").json()
        assert next(x for x in d["leads"] if x["id"] == lead["id"])["last_call_id"] == sess["id"]
        # second report with same call.id finds by vapi_call_id
        msg["message"]["analysis"]["summary"] = "TEST summary 2"
        requests.post(f"{API}/vapi/webhook", json=msg, headers={"X-Vapi-Secret": SECRET})
        assert _db.call_sessions.find_one({"id": sess["id"]})["summary"] == "TEST summary 2"

    def test_webhook_unauthorized(self, L):
        lead = L("report")
        msg = {"message": {"type": "end-of-call-report", "call": {"id": "TEST_x", "assistantOverrides": {"variableValues": {"lead_token": lead["portal_token"]}}},
                           "analysis": {"summary": "TEST hacked"}}}
        r = requests.post(f"{API}/vapi/webhook", json=msg, headers={"X-Vapi-Secret": "wrong"})
        assert r.json()["received"] is False
        assert _db.call_sessions.find_one({"lead_id": lead["id"], "summary": "TEST hacked"}) is None

    def test_sample_lead_never_matched(self):
        maya = _db.leads.find_one({"id": "lead-maya"})
        before = list(_db.call_sessions.find({"lead_id": "lead-maya"}, {"_id": 0, "id": 1, "summary": 1, "vapi_call_id": 1}))
        msg = {"message": {"type": "end-of-call-report", "call": {"id": "TEST_sample", "assistantOverrides": {"variableValues": {"lead_token": maya.get("portal_token")}}},
                           "analysis": {"summary": "TEST sample"}}}
        requests.post(f"{API}/vapi/webhook", json=msg, headers={"X-Vapi-Secret": SECRET})
        after = list(_db.call_sessions.find({"lead_id": "lead-maya"}, {"_id": 0, "id": 1, "summary": 1, "vapi_call_id": 1}))
        assert before == after

    def test_call_detail_404(self, s):
        assert s.get(f"{API}/calls/TEST_nope").status_code == 404


# ---- Take over
class TestTakeOver:
    def test_take_over_flow(self, s, L):
        lead = L("takeover")
        tok = lead["portal_token"]
        sess = requests.post(f"{API}/portal/{tok}/call/start").json()
        d = s.get(f"{API}/dashboard").json()
        assert next(x for x in d["leads"] if x["id"] == lead["id"])["live"]["id"] == sess["id"]
        r = s.post(f"{API}/leads/{lead['id']}/take-over")
        assert r.status_code == 200
        assert r.json() == {"escalated": True, "phone": SAFE_PHONE, "name": "TEST_R1 takeover"}
        assert _db.leads.find_one({"id": lead["id"]})["escalated"] is True
        p = requests.get(f"{API}/portal/{tok}").json()
        assert p["session"]["takeover"] is True
        sms = _db.sms_log.find_one({"lead_id": lead["id"], "kind": "takeover_alert"}, {"_id": 0})
        assert sms and sms["body"] == TAKEOVER_TPL.format(name="TEST_R1 takeover", phone=SAFE_PHONE)
        print("takeover sms:", {k: sms.get(k) for k in ("to", "status", "simulated")})
        requests.post(f"{API}/portal/{tok}/call/end", json={})
        row = next(c for c in s.get(f"{API}/calls").json()["calls"] if c["id"] == sess["id"])
        assert row["outcome"] == "Taken over by contractor"


# ---- In-person visit
class TestVisit:
    def test_visit_followup_and_schedule(self, s, L):
        lead = L("visit")
        tok = lead["portal_token"]
        sess = requests.post(f"{API}/portal/{tok}/call/start").json()
        res = tools(tok, "queue_quote_followup", {"reason": "wants_visit", "summary": "TEST wants a visit",
                                                    "site_visit_requested": True, "preferred_visit_times": "Saturday morning"})
        assert "result" in res, res
        f = _db.followups.find_one({"lead_id": lead["id"]})
        assert f["site_visit_requested"] is True and f["preferred_visit_times"] == "Saturday morning"
        l2 = _db.leads.find_one({"id": lead["id"]})
        assert l2["visit_requested"] is True and l2["visit_times"] == "Saturday morning"
        v = next(x for x in s.get(f"{API}/dashboard").json()["visits"] if x["id"] == lead["id"])
        assert v["phone"] == SAFE_PHONE and v["visit_times"] == "Saturday morning" and v["visit_scheduled_for"] is None
        requests.post(f"{API}/portal/{tok}/call/end", json={})
        row = next(c for c in s.get(f"{API}/calls").json()["calls"] if c["id"] == sess["id"])
        assert row["outcome"] == "Visit requested"
        r = s.post(f"{API}/leads/{lead['id']}/visit", json={"when": "Saturday, Feb 7 at 10:00 AM"})
        assert r.status_code == 200 and r.json()["scheduled"] is True
        sms = _db.sms_log.find_one({"lead_id": lead["id"], "kind": "visit_scheduled"}, {"_id": 0})
        assert sms["body"] == ("Your visit with George from Apex Remodeling is set for Saturday, Feb 7 at 10:00 AM. "
                               "Reply here if you need to change it.")
        v = next(x for x in s.get(f"{API}/dashboard").json()["visits"] if x["id"] == lead["id"])
        assert v["visit_scheduled_for"] == "Saturday, Feb 7 at 10:00 AM"

    def test_visit_validation(self, s, L):
        lead = L("visit")
        assert s.post(f"{API}/leads/{lead['id']}/visit", json={"when": ""}).status_code == 422
        assert s.post(f"{API}/leads/TEST_nope/visit", json={"when": "Monday 9am"}).status_code == 404

    def test_followup_without_visit(self, s, L):
        lead = L("novisit")
        tok = lead["portal_token"]
        requests.post(f"{API}/portal/{tok}/call/start")
        tools(tok, "queue_quote_followup", {"reason": "x", "summary": "TEST no visit"})
        assert not _db.leads.find_one({"id": lead["id"]}).get("visit_requested")
        assert all(v["id"] != lead["id"] for v in s.get(f"{API}/dashboard").json()["visits"])
        requests.post(f"{API}/portal/{tok}/call/end", json={})
