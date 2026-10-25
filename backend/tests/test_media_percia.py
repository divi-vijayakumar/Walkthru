# Media store + Percia (vision goals) + Itemizer callback tests. Only TEST_ leads with (408) 555-0199; cleans up after itself.
import os
import json
import hmac
import time
import uuid
import hashlib
import threading
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
import pytest
import requests
import imageio_ffmpeg
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
KEY = os.environ["PERCIA_KEY"]
SK = {"X-Walkthru-Key": KEY}
_db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
SAFE_PHONE = "(408) 555-0199"
GOAL_FIELDS = {"goal_id", "status", "result", "explanation", "value", "unit", "hits"}
HIT_FIELDS = {"t_ms", "frame_url", "box", "label", "confidence"}


def make_webm(path, seconds=3):
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size=320x240:rate=10",
                    "-c:v", "libvpx", "-b:v", "200k", path], check=True)
    return open(path, "rb").read()


@pytest.fixture(scope="module")
def clip():
    return make_webm(f"/tmp/test_clip_{uuid.uuid4().hex[:6]}.webm")


@pytest.fixture(scope="module")
def s(owner_token):
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {owner_token}", "Origin": BASE_URL})
    return sess


@pytest.fixture(scope="module")
def lead(s):
    r = s.post(f"{API}/leads", json={"name": "TEST_Media Percia", "phone": SAFE_PHONE, "source": "website", "ask": "Bathroom remodel"})
    assert r.status_code == 200, r.text
    ld = r.json()["lead"]
    if not ld.get("portal_token"):
        s.post(f"{API}/leads/{ld['id']}/start-agent")
        ld = _db.leads.find_one({"id": ld["id"]}, {"_id": 0})
    goal_ids = []
    yield {"lead": ld, "goal_ids": goal_ids}
    sids = [c["id"] for c in _db.call_sessions.find({"lead_id": ld["id"]}, {"id": 1})]
    _db.percia_goals.delete_many({"$or": [{"session_id": {"$in": sids}}, {"goal_id": {"$in": goal_ids}}]})
    _db.percia_frames.delete_many({"goal_id": {"$in": goal_ids}})
    _db.media.delete_many({"session_id": {"$in": sids}})
    for c in ("itemizer_sessions", "itemizer_goals", "quotes", "sms_log", "call_sessions", "followups", "pricing_states"):
        _db[c].delete_many({"lead_id": ld["id"]})
    _db.leads.delete_one({"id": ld["id"]})


@pytest.fixture(scope="module")
def session(lead):
    r = requests.post(f"{API}/portal/{lead['lead']['portal_token']}/call/start")
    assert r.status_code == 200, r.text
    return r.json()


def upload(clip, session_id, seq, t_start, headers, duration_ms=None):
    data = {"session_id": session_id, "kind": "video", "seq": str(seq), "t_start_ms": str(t_start)}
    if duration_ms is not None:
        data["duration_ms"] = str(duration_ms)
    return requests.post(f"{API}/media", data=data, files={"file": ("clip.webm", clip, "video/webm")}, headers=headers)


# --- Media store
class TestMedia:
    def test_upload_portal_token(self, lead, session, clip):
        r = upload(clip, session["id"], 0, 0, {"X-Portal-Token": lead["lead"]["portal_token"]}, 10000)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["created"] is True and d["kind"] == "video" and d["t_start_ms"] == 0
        assert 2500 <= d["duration_ms"] <= 3500  # measured, not the client hint
        assert f"/api/media/{d['media_id']}/file?exp=" in d["url"]
        lead["m0"] = d["media_id"]

    def test_reupload_same_seq_no_duplicate(self, lead, session, clip):
        r = upload(clip, session["id"], 0, 0, {"X-Portal-Token": lead["lead"]["portal_token"]})
        assert r.status_code == 200
        assert r.json()["media_id"] == lead["m0"] and r.json()["created"] is False
        assert _db.media.count_documents({"session_id": session["id"], "kind": "video", "seq": 0}) == 1

    def test_upload_service_key(self, lead, session, clip):
        r = upload(clip, session["id"], 1, 10000, SK)
        assert r.status_code == 200 and r.json()["created"] is True
        lead["m1"] = r.json()["media_id"]
        r = upload(clip, session["id"], 2, 20000, SK)
        lead["m2"] = r.json()["media_id"]

    def test_upload_auth(self, lead, session, clip):
        assert upload(clip, session["id"], 9, 0, {}).status_code == 401
        assert upload(clip, session["id"], 9, 0, {"X-Portal-Token": "bogus"}).status_code == 401
        assert upload(clip, "no-such-session", 9, 0, SK).status_code == 404
        r = requests.post(f"{API}/media", data={"session_id": session["id"], "kind": "photo", "seq": "9", "t_start_ms": "0"},
                          files={"file": ("a.webm", clip, "video/webm")}, headers=SK)
        assert r.status_code == 422

    def test_get_by_id(self, lead):
        r = requests.get(f"{API}/media/{lead['m0']}", headers=SK)
        assert r.status_code == 200
        d = r.json()
        assert set(d) == {"media_id", "url", "kind", "t_start_ms", "duration_ms"}
        f = requests.get(d["url"])
        assert f.status_code == 200 and f.content[:4] == b"\x1aE\xdf\xa3"  # webm/EBML
        exp = int(d["url"].split("exp=")[1].split("&")[0])
        assert 800 <= exp - time.time() <= 905
        assert requests.get(d["url"][:-4] + "beef").status_code == 403
        assert requests.get(f"{API}/media/{lead['m0']}").status_code == 401
        assert requests.get(f"{API}/media/m_nope", headers=SK).status_code == 404

    def test_range(self, lead, session):
        url = f"{API}/sessions/{session['id']}/media"
        all_ = requests.get(url, params={"kind": "video"}, headers=SK).json()
        assert all_["session_id"] == session["id"] and [m["t_start_ms"] for m in all_["media"]] == [0, 10000, 20000]
        r = requests.get(url, params={"kind": "video", "from_ms": 9000, "to_ms": 15000}, headers=SK).json()
        assert [m["media_id"] for m in r["media"]] == [lead["m1"]]
        r = requests.get(url, params={"kind": "video", "from_ms": 21000}, headers=SK).json()
        assert [m["media_id"] for m in r["media"]] == [lead["m2"]]
        assert requests.get(url).status_code == 401

    def test_old_frames_gone(self, lead):
        r = requests.post(f"{API}/portal/{lead['lead']['portal_token']}/frames", files={"file": ("f.jpg", b"x", "image/jpeg")})
        assert r.status_code in (404, 405)


# --- Percia
class Receiver(BaseHTTPRequestHandler):
    got = []

    def do_POST(self):
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        Receiver.got.append({"raw": raw, "sig": self.headers.get("X-Walkthru-Signature")})
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def receiver():
    srv = HTTPServer(("127.0.0.1", 0), Receiver)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/cb"
    srv.shutdown()


def media_ref(mid):
    d = requests.get(f"{API}/media/{mid}", headers=SK).json()
    return {k: d[k] for k in ("media_id", "url", "kind", "t_start_ms")}


def wait_goal(gid, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        g = requests.get(f"{API}/percia/goals/{gid}", headers=SK).json()
        if g["status"] in ("done", "failed"):
            return g
        time.sleep(2)
    return g


class TestPercia:
    def test_goal_done_and_callback(self, lead, session, receiver):
        gid = f"TEST_g_{uuid.uuid4().hex[:8]}"
        lead["goal_ids"].append(gid)
        body = {"goal_id": gid, "session_id": session["id"], "query": "Is there a bathroom vanity visible?",
                "media": [media_ref(lead["m0"])], "callback_url": receiver}
        r = requests.post(f"{API}/percia/goals", json=body, headers=SK)
        assert r.status_code == 202 and r.json()["goal_id"] == gid and r.json()["status"] == "queued"
        r2 = requests.post(f"{API}/percia/goals", json=body, headers=SK)
        assert r2.status_code == 202
        assert _db.percia_goals.count_documents({"goal_id": gid}) == 1
        g = wait_goal(gid)
        assert set(g) == GOAL_FIELDS
        assert g["status"] == "done", g
        assert g["result"] in ("met", "ambiguous", "not_found") and isinstance(g["explanation"], str)
        for h in g["hits"]:
            assert set(h) == HIT_FIELDS and len(h["box"]) == 4
        # only hit frames kept
        assert _db.percia_frames.count_documents({"goal_id": gid}) == len(g["hits"])
        time.sleep(2)
        cbs = [c for c in Receiver.got if json.loads(c["raw"])["data"]["goal_id"] == gid]
        assert cbs, "no callback received"
        c = cbs[0]
        assert c["sig"] == hmac.new(KEY.encode(), c["raw"], hashlib.sha256).hexdigest()
        ev = json.loads(c["raw"])
        assert set(ev) == {"event", "session_id", "occurred_at", "idempotency_key", "data"}
        assert ev["event"] == "goal.completed" and ev["session_id"] == session["id"] and set(ev["data"]) == GOAL_FIELDS

    def test_goal_auth_and_validation(self, lead, session, receiver):
        body = {"goal_id": "TEST_x", "session_id": session["id"], "query": "anything?", "media": [media_ref(lead["m0"])], "callback_url": receiver}
        assert requests.post(f"{API}/percia/goals", json=body).status_code == 401
        assert requests.post(f"{API}/percia/goals", json=body, headers={"X-Walkthru-Key": "nope"}).status_code == 401
        assert requests.get(f"{API}/percia/goals/x").status_code == 401
        assert requests.get(f"{API}/percia/goals/nope", headers=SK).status_code == 404
        assert requests.post(f"{API}/percia/goals", json={**body, "media": []}, headers=SK).status_code == 422

    def test_media_404_gives_failed(self, lead, session, receiver):
        gid = f"TEST_g_{uuid.uuid4().hex[:8]}"
        lead["goal_ids"].append(gid)
        ref = media_ref(lead["m0"])
        ref["url"] = ref["url"][:-4] + "beef"
        r = requests.post(f"{API}/percia/goals", json={"goal_id": gid, "session_id": session["id"], "query": "Is there a sink?",
                                                        "media": [ref], "callback_url": receiver}, headers=SK)
        assert r.status_code == 202
        g = wait_goal(gid, 60)
        assert g["status"] == "failed" and g["result"] is None and g["hits"] == []

    def test_invalid_video_gives_failed(self, lead, session, receiver):
        bad = upload(b"not a video at all" * 100, session["id"], 50, 500000, SK)
        assert bad.status_code == 200, bad.text
        gid = f"TEST_g_{uuid.uuid4().hex[:8]}"
        lead["goal_ids"].append(gid)
        r = requests.post(f"{API}/percia/goals", json={"goal_id": gid, "session_id": session["id"], "query": "Is there a sink?",
                                                        "media": [media_ref(bad.json()["media_id"])], "callback_url": receiver}, headers=SK)
        assert r.status_code == 202
        g = wait_goal(gid, 60)
        assert g["status"] == "failed" and g["result"] is None

    def test_frame_endpoint(self):
        f = _db.percia_frames.find_one({}, {"_id": 0, "frame_id": 1})
        if not f:
            pytest.skip("no stored frames yet")
        r = requests.get(f"{API}/percia/frames/{f['frame_id']}")
        assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content[:2] == b"\xff\xd8"
        assert requests.get(f"{API}/percia/frames/f_nope").status_code == 404


# --- Itemizer callback
class TestCallback:
    def test_bad_signature_401(self):
        raw = json.dumps({"event": "goal.completed", "data": {"goal_id": "g_x"}}).encode()
        assert requests.post(f"{API}/itemizer/percia/callback", data=raw).status_code == 401
        assert requests.post(f"{API}/itemizer/percia/callback", data=raw, headers={"X-Walkthru-Signature": "00" * 32}).status_code == 401

    def test_good_signature_unknown_goal_ok(self):
        raw = json.dumps({"event": "goal.completed", "session_id": "x", "data": {"goal_id": "g_unknown", "status": "done"}}).encode()
        sig = hmac.new(KEY.encode(), raw, hashlib.sha256).hexdigest()
        r = requests.post(f"{API}/itemizer/percia/callback", data=raw, headers={"X-Walkthru-Signature": sig, "Content-Type": "application/json"})
        assert r.status_code == 200 and r.json() == {"ok": True}
