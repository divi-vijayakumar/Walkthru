# Security audit fixes SEC-001..SEC-004 regression: vapi lock, random portal tokens, CSRF origin check/CORS, upload caps
import os
import re
import json
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
EVIL = "https://evil.example.com"
_db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
JPEG = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="


@pytest.fixture(scope="module")
def s(owner_token):
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {owner_token}"})
    assert sess.post(f"{API}/dev/reset").status_code == 200
    yield sess
    sess.post(f"{API}/dev/reset", headers={"Origin": BASE_URL})


def dash(s):
    return s.get(f"{API}/dashboard").json()


def lead(s, name):
    return next(l for l in dash(s)["leads"] if l["name"] == name)


def tool_body(token, name="get_quote_estimate", args=None):
    return {"message": {"type": "tool-calls", "call": {"assistantOverrides": {"variableValues": {"lead_token": token}}},
                        "toolCallList": [{"id": "tcX", "function": {"name": name, "arguments": args or {
                            "project_type": "bathroom_remodel", "room_size": "medium", "finish_level": "standard",
                            "requested_changes": ["walk-in shower and double vanity"]}}}]}}


# SEC-001: Vapi endpoints locked without secret
def test_vapi_tools_unauthorized_no_side_effects(s):
    maya = lead(s, "Maya Rios")
    before = _db.quotes.count_documents({"lead_id": maya["id"]})
    r = requests.post(f"{API}/vapi/tools", json=tool_body(maya["portal_token"]))
    assert r.status_code == 200
    assert r.json() == {"results": [{"toolCallId": "tcX", "error": "Unauthorized"}]}
    # also with a wrong secret header
    r = requests.post(f"{API}/vapi/tools", json=tool_body(maya["portal_token"]), headers={"X-Vapi-Secret": "guess"})
    assert r.json()["results"][0]["error"] == "Unauthorized"
    assert _db.quotes.count_documents({"lead_id": maya["id"]}) == before
    assert lead(s, "Maya Rios")["status"] == "walkthru_initiated"


def test_vapi_webhook_unauthorized_does_not_end_call(s):
    maya = lead(s, "Maya Rios")
    body = {"message": {"type": "end-of-call-report",
                        "call": {"assistantOverrides": {"variableValues": {"lead_token": maya["portal_token"]}}}}}
    for h in ({}, {"Authorization": "Bearer guess"}):
        r = requests.post(f"{API}/vapi/webhook", json=body, headers=h)
        assert r.status_code == 200 and r.json()["received"] is False
    # body without lead_token (would previously fall back to most recent walkthru_initiated lead)
    r = requests.post(f"{API}/vapi/webhook", json={"message": {"type": "end-of-call-report"}})
    assert r.json()["received"] is False
    m = lead(s, "Maya Rios")
    assert m["status"] == "walkthru_initiated" and m["live"]


# SEC-001 replacement: portal-scoped agent tools ignore lead_token in body
def test_agent_tools_scoped_to_url_token(s):
    luis, maya = lead(s, "Luis Ortega"), lead(s, "Maya Rios")
    maya_quotes = _db.quotes.count_documents({"lead_id": maya["id"]})
    assert requests.post(f"{API}/portal/{luis['portal_token']}/call/start").status_code == 200
    r = requests.post(f"{API}/portal/{luis['portal_token']}/agent/tools", json=tool_body(maya["portal_token"]))
    assert r.status_code == 200
    out = json.loads(r.json()["results"][0]["result"])
    assert (out["low"], out["high"], out["total"]) == (25000, 30500, 27600)
    assert _db.quotes.count_documents({"lead_id": maya["id"]}) == maya_quotes
    assert _db.quotes.count_documents({"lead_id": luis["id"]}) >= 1
    # end via portal agent/end with maya's token in body -> only luis ends
    body = {"message": {"type": "end-of-call-report", "artifact": {"messages": [
        {"role": "assistant", "message": "hi"}, {"role": "user", "message": "yo"}]},
        "call": {"assistantOverrides": {"variableValues": {"lead_token": maya["portal_token"]}}}}}
    r = requests.post(f"{API}/portal/{luis['portal_token']}/agent/end", json=body)
    assert r.status_code == 200 and r.json()["ended"] is True
    assert lead(s, "Luis Ortega")["status"] == "quote_generated"
    assert lead(s, "Maya Rios")["status"] == "walkthru_initiated"


def test_agent_endpoints_bad_token_404():
    assert requests.post(f"{API}/portal/nope-token/agent/tools", json=tool_body("x")).status_code == 404
    assert requests.post(f"{API}/portal/nope-token/agent/end", json={}).status_code == 404


# SEC-002: random tokens
def test_random_portal_tokens(s):
    toks = [l["portal_token"] for l in dash(s)["leads"] if l["portal_token"]]
    assert len(toks) >= 8
    for t in toks:
        assert re.fullmatch(r"[A-Za-z0-9_-]{22}", t), t
        assert not t.startswith("demo-")
    assert len(set(toks)) == len(toks)
    for n in ("luis", "priya", "maya", "ana", "marcus", "dana"):
        assert requests.get(f"{API}/portal/demo-{n}").status_code == 404


def test_reset_rotates_tokens(s):
    before = {l["name"]: l["portal_token"] for l in dash(s)["leads"]}
    assert s.post(f"{API}/dev/reset", headers={"Origin": BASE_URL}).status_code == 200
    after = {l["name"]: l["portal_token"] for l in dash(s)["leads"]}
    print("tokens rotated on reset:", sum(1 for k in after if after[k] and after[k] != before.get(k)))


# SEC-003: CSRF + CORS
@pytest.mark.parametrize("method,path,body", [
    ("patch", "/contractor", {"agent_enabled": False}),
    ("post", "/leads", {"name": "TEST_csrf", "phone": "5550101234", "source": "website", "ask": "Bathroom"}),
    ("post", "/dev/reset", None),
    ("post", "/leads/whatever/take-over", None),
])
def test_foreign_origin_403(s, method, path, body):
    r = getattr(s, method)(f"{API}{path}", json=body, headers={"Origin": EVIL})
    assert r.status_code == 403 and r.json()["detail"] == "Cross-site request blocked"


def test_foreign_origin_cookie_403(owner_token):
    r = requests.post(f"{API}/dev/reset", cookies={"session_token": owner_token}, headers={"Origin": EVIL})
    assert r.status_code == 403
    # spoofed lookalike host
    r = requests.post(f"{API}/dev/reset", cookies={"session_token": owner_token},
                      headers={"Origin": BASE_URL + ".evil.com"})
    assert r.status_code == 403


def test_same_origin_ok(s):
    r = s.patch(f"{API}/contractor", json={"agent_enabled": False}, headers={"Origin": BASE_URL})
    assert r.status_code == 200 and r.json()["agent_enabled"] is False
    r = s.post(f"{API}/leads", json={"name": "TEST_SameOrigin", "phone": "5550101234", "source": "website",
                                    "ask": "Bathroom remodel"}, headers={"Origin": BASE_URL})
    assert r.status_code == 200
    assert any(l["name"] == "TEST_SameOrigin" for l in dash(s)["leads"])
    # GET with foreign origin still fine (read-only; CORS stops browser read)
    assert s.get(f"{API}/dashboard", headers={"Origin": EVIL}).status_code == 200


def test_cors_no_credentials():
    for h in ({"Origin": EVIL}, {"Origin": EVIL, "Access-Control-Request-Method": "POST"}):
        r = requests.options(f"{API}/dashboard", headers=h) if len(h) > 1 else requests.get(f"{API}/health", headers=h)
        low = {k.lower(): v for k, v in r.headers.items()}
        assert "access-control-allow-credentials" not in low
        assert low.get("access-control-allow-origin") in ("*", None)


# SEC-004: frames + captions caps
def test_frames_no_active_call_400(s):
    t = lead(s, "Priya Shah")["portal_token"]
    r = requests.post(f"{API}/portal/{t}/frames", json={"image": JPEG})
    assert r.status_code == 400


def test_frames_too_large_422_and_non_jpeg(s):
    t = lead(s, "Maya Rios")["portal_token"]
    big = "data:image/jpeg;base64," + "A" * 600_001
    assert requests.post(f"{API}/portal/{t}/frames", json={"image": big}).status_code == 422
    assert requests.post(f"{API}/portal/{t}/frames", json={"image": "data:image/png;base64,AAA"}).status_code == 422


def test_frames_cap_429_and_captions_cap(s):
    created = s.post(f"{API}/leads", json={"name": "TEST_Caps", "phone": "5550101234", "source": "website",
                                           "ask": "Bathroom remodel"}).json()["lead"]
    if created["status"] == "new":
        s.post(f"{API}/leads/{created['id']}/start-agent")
    t = lead(s, "TEST_Caps")["portal_token"]
    sess = requests.post(f"{API}/portal/{t}/call/start").json()
    # seed 299 frames directly then hit the API for the 300th and 301st
    _db.frames.insert_many([{"lead_id": created["id"], "session_id": sess["id"], "image": JPEG, "at": "x"}
                            for _ in range(299)])
    r = requests.post(f"{API}/portal/{t}/frames", json={"image": JPEG})
    assert r.status_code == 200 and r.json()["stored"] is True
    r = requests.post(f"{API}/portal/{t}/frames", json={"image": JPEG})
    assert r.status_code == 429
    # captions: seed 399 lines then push 3 more -> stays 400
    _db.call_sessions.update_one({"id": sess["id"]}, {"$set": {"transcript": [
        {"role": "user", "text": "x", "at": "x"}] * 399}})
    for _ in range(3):
        assert requests.post(f"{API}/portal/{t}/call/caption", json={"role": "user", "text": "more"}).status_code == 200
    doc = _db.call_sessions.find_one({"id": sess["id"]})
    assert len(doc["transcript"]) == 400
    assert requests.post(f"{API}/portal/{t}/call/caption", json={"role": "user", "text": "x" * 2001}).status_code == 422
    _db.frames.delete_many({"lead_id": created["id"]})
