# Seeds/cleans TEST_ UI data for round1 UI checks: `python ui_seed_round1.py seed|clean`. Prints owner token + ids.
import os
import sys
import time
import json
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
sys.path.insert(0, os.path.dirname(__file__))
from conftest import make_session  # noqa: E402

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
SECRET = os.environ["VAPI_SERVER_SECRET"]


def seed():
    token, _, _ = make_session("divi@velvee.ai")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}"})
    out = {"token": token}
    for key in ("UIcall", "UIvisit", "UIlive"):
        lead = s.post(f"{API}/leads", json={"name": f"TEST_R1 {key}", "phone": "(408) 555-0199", "source": "website", "ask": "Bathroom remodel"}).json()["lead"]
        if not lead.get("portal_token"):
            s.post(f"{API}/leads/{lead['id']}/start-agent")
        lead = db.leads.find_one({"id": lead["id"]}, {"_id": 0})
        tok = lead["portal_token"]
        sess = requests.post(f"{API}/portal/{tok}/call/start").json()
        out[key] = {"id": lead["id"], "token": tok, "session": sess["id"]}
        if key == "UIcall":
            requests.post(f"{API}/portal/{tok}/call/end", json={})
            msg = {"message": {"type": "end-of-call-report", "call": {"id": "TEST_ui_call", "assistantOverrides": {"variableValues": {"lead_token": tok}}},
                               "artifact": {"messages": [{"role": "bot", "message": f"Line {i} from Alex."} if i % 2 else {"role": "user", "message": f"Line {i} from homeowner."} for i in range(30)],
                                            "recordingUrl": "https://download.samplelib.com/wav/sample-3s.wav"},
                               "analysis": {"summary": "TEST UI summary"}}}
            requests.post(f"{API}/vapi/webhook", json=msg, headers={"X-Vapi-Secret": SECRET})
        if key == "UIvisit":
            requests.post(f"{API}/portal/{tok}/agent/tools", json={"message": {"toolCallList": [{"id": "t", "function": {"name": "queue_quote_followup", "arguments": {
                "reason": "visit", "summary": "TEST", "site_visit_requested": True, "preferred_visit_times": "Saturday morning"}}}]}})
            requests.post(f"{API}/portal/{tok}/call/end", json={})
    time.sleep(6)
    print(json.dumps(out))


def clean():
    ids = [x["id"] for x in db.leads.find({"name": {"$regex": "^TEST_R1 "}}, {"id": 1})]
    for c in ("itemizer_sessions", "itemizer_insights", "itemizer_goals", "quotes", "sms_log", "call_sessions", "followups", "pricing_states", "contracts", "payments"):
        db[c].delete_many({"lead_id": {"$in": ids}})
    db.leads.delete_many({"id": {"$in": ids}})
    db.user_sessions.delete_many({"session_token": {"$regex": "^test_session_"}})
    print("cleaned", len(ids))


if __name__ == "__main__":
    seed() if sys.argv[1] == "seed" else clean()
