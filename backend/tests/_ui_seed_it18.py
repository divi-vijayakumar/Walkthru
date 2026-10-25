import os, sys, json, requests
sys.path.insert(0, "/app/backend/tests")
from conftest import make_session, _db
from dotenv import load_dotenv
load_dotenv("/app/frontend/.env")
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
COLLS = ("itemizer_sessions", "itemizer_insights", "itemizer_goals", "itemizer_tips", "quotes", "sms_log", "call_sessions", "followups", "pricing_states")
if sys.argv[1] == "seed":
    tok, uid, _ = make_session("divi@velvee.ai")
    s = requests.Session(); s.headers.update({"Authorization": f"Bearer {tok}"})
    lead = s.post(f"{API}/leads", json={"name": "TEST_UI Quote", "phone": "(408) 555-0199", "source": "website", "ask": "Bathroom remodel"}).json()["lead"]
    l = _db.leads.find_one({"id": lead["id"]})
    if not l.get("portal_token"):
        s.post(f"{API}/leads/{lead['id']}/start-agent"); l = _db.leads.find_one({"id": lead["id"]})
    pt = l["portal_token"]
    requests.post(f"{API}/portal/{pt}/call/start")
    msg = lambda a: {"message": {"type": "tool-calls", "toolCallList": [{"id": "t", "function": {"name": "update_scope", "arguments": json.dumps(a)}}]}}
    print(requests.post(f"{API}/portal/{pt}/agent/tools", json=msg({"said": "Retile the shower walls, LED mirror, wallpaper the wall"})).json())
    print(requests.post(f"{API}/portal/{pt}/agent/end", json={"message": {"type": "end-of-call-report"}}).json())
    q = _db.quotes.find_one({"lead_id": lead["id"]}, sort=[("version", -1)])
    print(json.dumps({"session": tok, "lead_id": lead["id"], "portal": pt, "total": q["total"], "quote_id": q["id"]}))
else:
    for l in _db.leads.find({"name": {"$regex": "^TEST_"}}, {"id": 1, "name": 1}):
        print("delete", l["name"])
        _db.leads.delete_one({"id": l["id"]})
        for c in COLLS:
            _db[c].delete_many({"lead_id": l["id"]})
    _db.user_sessions.delete_many({"session_token": {"$regex": "^test_session_"}})
