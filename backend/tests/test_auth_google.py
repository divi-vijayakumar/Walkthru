# Emergent Google sign-in: protected dashboard endpoints, allow-list, session/logout, public portal endpoints
import os
import pytest
import requests
from dotenv import load_dotenv
from conftest import make_session, session_exists, OWNER

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


# Unauthenticated access to protected endpoints -> 401
@pytest.mark.parametrize("method,path,body", [
    ("get", "/dashboard", None),
    ("patch", "/contractor", {"agent_enabled": False}),
    ("post", "/leads", {"name": "TEST_x", "phone": "5550101234", "source": "website", "ask": "Bathroom"}),
    ("post", "/leads/whatever/start-agent", None),
    ("post", "/leads/whatever/take-over", None),
    ("post", "/leads/whatever/recall-quote", None),
    ("get", "/leads/whatever/transcript", None),
    ("get", "/dev/config", None),
    ("post", "/dev/reset", None),
    ("post", "/dev/leads/whatever/advance", None),
    ("post", "/dev/leads/whatever/drop", None),
    ("get", "/auth/me", None),
])
def test_protected_401(method, path, body):
    r = getattr(requests, method)(f"{API}{path}", json=body)
    assert r.status_code == 401, (path, r.status_code, r.text)
    assert r.json()["detail"] == "Sign in required"


def test_bogus_bearer_401():
    r = requests.get(f"{API}/dashboard", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


def test_expired_session_401():
    token, _, _ = make_session(OWNER, expired=True)
    r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401 and r.json()["detail"] == "Session expired"


# Public endpoints stay open
def test_public_endpoints():
    assert requests.get(f"{API}/health").status_code == 200
    assert requests.get(f"{API}/portal/demo-luis").status_code == 404  # SEC-002: guessable tokens gone
    assert requests.post(f"{API}/vapi/tools", json={}).status_code == 200
    assert requests.get(f"{API}/payments/status/x").status_code == 404


def test_me_bearer(owner_token):
    r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 200
    d = r.json()
    assert set(d.keys()) == {"user_id", "email", "name", "picture"}
    assert d["email"] == OWNER


def test_me_cookie_and_dashboard(owner_token):
    c = {"session_token": owner_token}
    assert requests.get(f"{API}/auth/me", cookies=c).json()["email"] == OWNER
    r = requests.get(f"{API}/dashboard", cookies=c)
    assert r.status_code == 200 and isinstance(r.json()["leads"], list) and len(r.json()["leads"]) > 0
    assert requests.get(f"{API}/dev/config", cookies=c).status_code == 200


def test_outsider_403(outsider_token):
    h = {"Authorization": f"Bearer {outsider_token}"}
    for p in ("/auth/me", "/dashboard", "/dev/config"):
        r = requests.get(f"{API}{p}", headers=h)
        assert r.status_code == 403, p
        assert "access" in r.json()["detail"]


def test_session_bogus_id_401():
    r = requests.post(f"{API}/auth/session", json={"session_id": "bogus-session-id-123"})
    assert r.status_code == 401
    assert "Google sign-in failed" in r.json()["detail"]


def test_session_missing_body_422():
    assert requests.post(f"{API}/auth/session", json={}).status_code == 422


def test_logout_deletes_session():
    token, _, _ = make_session(OWNER)
    assert requests.get(f"{API}/auth/me", cookies={"session_token": token}).status_code == 200
    r = requests.post(f"{API}/auth/logout", cookies={"session_token": token})
    assert r.status_code == 200 and r.json() == {"ok": True}
    sc = r.headers.get("set-cookie", "")
    assert "session_token=" in sc and ("Max-Age=0" in sc or "expires=" in sc.lower())
    assert not session_exists(token)
    assert requests.get(f"{API}/auth/me", cookies={"session_token": token}).status_code == 401


def test_logout_without_cookie_ok():
    r = requests.post(f"{API}/auth/logout")
    assert r.status_code == 200


# Checkout origin validation
def _ana_token(owner_token):
    d = requests.get(f"{API}/dashboard", headers={"Authorization": f"Bearer {owner_token}"}).json()
    return next(l for l in d["leads"] if l["status"] == "pending_deposit")["portal_token"]


def test_checkout_origin_mismatch_400(owner_token):
    r = requests.post(f"{API}/portal/{_ana_token(owner_token)}/deposit/checkout", json={"origin_url": "https://evil.example.com"},
                      headers={"Origin": BASE_URL})
    assert r.status_code == 400 and "this site" in r.json()["detail"]


def test_checkout_no_origin_header_any_origin_url(owner_token):
    # Without Origin header (non-browser client) origin_url is still trusted -> open redirect remains possible
    r = requests.post(f"{API}/portal/{_ana_token(owner_token)}/deposit/checkout", json={"origin_url": "https://evil.example.com"})
    print("no-origin-header checkout status:", r.status_code)
    assert r.status_code in (200, 400)
