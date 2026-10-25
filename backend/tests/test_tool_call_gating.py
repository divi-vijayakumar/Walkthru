# Agent tool calls only run while lead is in an active call (status walkthru_initiated)
import os
import json
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
_db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
NO_CALL = "No call in progress for this lead"


@pytest.fixture(scope="module")
def s(owner_token):
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {owner_token}", "Origin": BASE_URL})
    assert sess.post(f"{API}/dev/reset").status_code == 200
    yield sess
    sess.post(f"{API}/dev/reset")


def lead(s, name):
    return next(l for l in s.get(f"{API}/dashboard").json()["leads"] if l["name"] == name)


def body(name="update_scope"):
    return {"message": {"type": "tool-calls", "toolCallList": [{"id": "tcG", "function": {"name": name, "arguments": {
        "said": "I want a walk-in shower and a double vanity", "answers": {}, "camera_on": False}}}]}}


def quotes(lid):
    return list(_db.quotes.find({"lead_id": lid}, {"_id": 0}))


@pytest.mark.parametrize("name,status", [("Ana Pereira", "pending_deposit"),
                                         ("Chris Nolan", "deposit_received"),
                                         ("Marcus Lee", "contract_sent")])
def test_tools_blocked_when_not_in_call(s, name, status):
    l = lead(s, name)
    assert l["status"] == status
    before = quotes(l["id"])
    r = requests.post(f"{API}/portal/{l['portal_token']}/agent/tools", json=body())
    assert r.status_code == 200
    assert r.json() == {"results": [{"toolCallId": "tcG", "error": NO_CALL}]}
    assert quotes(l["id"]) == before
    assert lead(s, name)["status"] == status


def test_ana_quote_unchanged(s):
    l = lead(s, "Ana Pereira")
    q = quotes(l["id"])
    print("ANA quotes:", [(x.get("version"), x.get("total"), x.get("low"), x.get("high")) for x in q])
    assert len(q) == 1 and q[0].get("version") == 1 and q[0].get("total") == 38900


def test_maya_in_call_tools_work(s):
    l = lead(s, "Maya Rios")
    assert l["status"] == "walkthru_initiated"
    n = len(quotes(l["id"]))
    r = requests.post(f"{API}/portal/{l['portal_token']}/agent/tools", json=body())
    res = r.json()["results"][0]
    assert "result" in res, res
    out = json.loads(res["result"])
    assert out.get("say") or out.get("question") or out.get("version"), out
    assert len(quotes(l["id"])) >= n


def test_vapi_tools_still_locked(s):
    r = requests.post(f"{API}/vapi/tools", json=body())
    assert r.json()["results"][0]["error"] == "Unauthorized"
