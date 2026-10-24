# WhatsApp channel (MESSAGE_CHANNEL) simulation tests. Never resets data; never touches Dhivya's real lead.
import os
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
TOKEN = os.environ.get("TEST_SESSION_TOKEN")
mongo = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
REAL = "Dhivya Vijayakumar"


@pytest.fixture(scope="module")
def api():
    if not TOKEN:
        pytest.skip("TEST_SESSION_TOKEN not set")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    yield s
    # cleanup TEST_ leads
    ids = [lead["id"] for lead in mongo.leads.find({"name": {"$regex": "^TEST_"}}, {"id": 1})]
    for coll in ("sms_log", "call_sessions", "quotes"):
        mongo[coll].delete_many({"lead_id": {"$in": ids}})
    mongo.leads.delete_many({"id": {"$in": ids}})


@pytest.fixture(scope="module")
def dana_backup():
    doc = mongo.leads.find_one({"name": "Dana Kim"})
    yield doc
    if doc:  # restore seeded lead to its original state
        mongo.sms_log.delete_many({"lead_id": doc["id"]})
        mongo.leads.replace_one({"_id": doc["_id"]}, doc)


# Lead creation with a non-allowlisted number -> simulated whatsapp
def test_create_lead_simulated_whatsapp(api):
    before = mongo.sms_log.count_documents({"to": "+16462380338"})
    r = api.post(f"{BASE_URL}/api/leads", json={"name": "TEST_Wa Lead", "phone": "(408) 555-0199",
                                                 "source": "thumbtack", "ask": "Bathroom remodel"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["lead"]["status"] == "invited"
    assert d["lead"]["phone"] == "(408) 555-0199"
    sms = d["agent"]["sms"]
    assert sms["channel"] == "whatsapp"
    assert sms["simulated"] is True and sms["sent"] is False
    assert sms["reason"] == "Number not on SMS allowlist"
    assert sms["to"] == "+14085550199"
    assert d["agent"]["link"] in sms["body"]
    assert "_id" not in sms
    log = mongo.sms_log.find_one({"lead_id": d["lead"]["id"]})
    assert log and log["channel"] == "whatsapp" and log["simulated"] is True
    assert mongo.sms_log.count_documents({"to": "+16462380338"}) == before


# Start agent + resend on a seeded new lead
def test_start_agent_and_resend_seeded(api, dana_backup):
    assert dana_backup and dana_backup["status"] == "new"
    r = api.post(f"{BASE_URL}/api/leads/{dana_backup['id']}/start-agent")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "invited"
    assert d["sms"]["simulated"] is True and d["sms"]["channel"] == "whatsapp"
    assert d["sms"]["reason"] == "Number not on SMS allowlist"
    r2 = api.post(f"{BASE_URL}/api/leads/{dana_backup['id']}/start-agent")
    assert r2.status_code == 200
    assert r2.json()["sms"]["simulated"] is True
    assert r2.json()["link"] == d["link"]
    dash = api.get(f"{BASE_URL}/api/dashboard").json()
    dana = next(lead for lead in dash["leads"] if lead["id"] == dana_backup["id"])
    assert dana["status"] == "invited"


# Dashboard shows real lead (read only)
def test_dashboard_shows_dhivya(api):
    r = api.get(f"{BASE_URL}/api/dashboard")
    assert r.status_code == 200
    leads = [lead for lead in r.json()["leads"] if lead["name"] == REAL]
    assert len(leads) == 1
    lead = leads[0]
    assert lead["source"] == "thumbtack" and lead["ask"] == "Bathroom remodel"
    assert lead["phone"] == "(646) 238-0338" and lead["status"] == "invited"
    assert lead["portal_token"]


# Portal for Dhivya (public, read only)
def test_portal_dhivya(api):
    lead = next(lead for lead in api.get(f"{BASE_URL}/api/dashboard").json()["leads"] if lead["name"] == REAL)
    r = requests.get(f"{BASE_URL}/api/portal/{lead['portal_token']}")
    assert r.status_code == 200, r.text
    assert "Dhivya" in r.text


def test_dashboard_requires_auth():
    assert requests.get(f"{BASE_URL}/api/dashboard").status_code == 401


def test_dev_config(api):
    r = api.get(f"{BASE_URL}/api/dev/config")
    assert r.status_code == 200
    d = r.json()
    assert d["voice_mode"] == "vapi"
    assert d["allowlist_count"] == 1
