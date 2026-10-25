# E2E /dev walkthrough video -> Percia -> Itemizer (real Gemini call, costs credits; run sparingly).
# Set KEEP_E2E_LEAD=1 to keep the TEST_ lead for UI checks (then clean up with cleanup_lead()).
import os
import time
import uuid
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
_db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
VIDEO = "/app/test_assets/bathroom_vanity.mov"


def cleanup_lead(lead_id):
    sids = [c["id"] for c in _db.call_sessions.find({"lead_id": lead_id}, {"id": 1})]
    gids = [g["goal_id"] for g in _db.percia_goals.find({"session_id": {"$in": sids}}, {"goal_id": 1})]
    _db.percia_frames.delete_many({"goal_id": {"$in": gids}})
    _db.percia_goals.delete_many({"session_id": {"$in": sids}})
    _db.media.delete_many({"session_id": {"$in": sids}})
    for c in ("itemizer_sessions", "itemizer_goals", "quotes", "sms_log", "call_sessions", "followups", "pricing_states"):
        _db[c].delete_many({"lead_id": lead_id})
    _db.leads.delete_one({"id": lead_id})


@pytest.fixture(scope="module")
def s(owner_token):
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {owner_token}", "Origin": BASE_URL})
    return sess


@pytest.fixture(scope="module")
def lead(s):
    r = s.post(f"{API}/leads", json={"name": "TEST_E2E Vanity", "phone": "(408) 555-0199", "source": "website", "ask": "Bathroom remodel"})
    assert r.status_code == 200, r.text
    ld = r.json()["lead"]
    if not ld.get("portal_token"):
        s.post(f"{API}/leads/{ld['id']}/start-agent")
        ld = _db.leads.find_one({"id": ld["id"]}, {"_id": 0})
    print(f"\nE2E lead {ld['id']} token {ld['portal_token']}")
    yield ld
    if not os.environ.get("KEEP_E2E_LEAD"):
        cleanup_lead(ld["id"])


def test_dev_video_resolves_vanity(s, lead):
    lid = lead["id"]
    r = s.post(f"{API}/itemizer/{lid}/turn", json={"said": "I want this sink gone", "answers": {}, "camera_on": False})
    assert r.status_code == 200, r.text
    # unauth chunk upload is rejected
    assert requests.post(f"{API}/dev/uploads/abcdefgh12/chunk?index=0", data=b"x").status_code == 401
    up = f"test-{uuid.uuid4().hex[:12]}"
    with open(VIDEO, "rb") as f:
        i = 0
        while chunk := f.read(4 * 1024 * 1024):
            r = s.post(f"{API}/dev/uploads/{up}/chunk?index={i}", data=chunk, headers={"Content-Type": "application/octet-stream"})
            assert r.status_code == 200, r.text
            i += 1
    r = s.post(f"{API}/dev/leads/{lid}/video", json={"upload_id": up, "content_type": "video/quicktime"}, timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["kind"] == "video" and 40000 <= d["duration_ms"] <= 46000, d
    sid = d["session_id"]
    end, st = time.time() + 150, None
    while time.time() < end:
        st = s.get(f"{API}/itemizer/{lid}").json()
        fact = next((f for f in st.get("facts", []) if f["name"] == "vanity_mount"), None)
        if fact and fact.get("state") == "resolved":
            break
        time.sleep(5)
    print(st)
    fact = next(f for f in st["facts"] if f["name"] == "vanity_mount")
    assert fact["state"] == "resolved" and fact["value"] == "floor" and fact["basis"] == "seen", fact
    items = st["items"]
    retile = next((it for it in items if it.get("label") == "Retile under old vanity"), None)
    assert retile, items
    assert retile.get("basis") == "seen" and (retile.get("evidence") or {}).get("frame_url"), retile
    frame = requests.get(retile["evidence"]["frame_url"])
    assert frame.status_code == 200 and frame.headers["content-type"] == "image/jpeg"
    cs = _db.call_sessions.find_one({"id": sid}, {"_id": 0, "chips": 1})
    met = _db.percia_goals.count_documents({"session_id": sid, "result": "met"})
    print("chips", cs.get("chips"), "met goals", met)
    assert cs.get("chips"), cs
