# Stripe deposit checkout: checkout session creation, status polling, webhook signature, removed simulated endpoint
import os
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def s(owner_token):
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {owner_token}"})
    sess.post(f"{API}/dev/reset")
    yield sess
    sess.post(f"{API}/dev/reset")


def test_portal_ana_pending_deposit(s):
    p = s.get(f"{API}/portal/demo-ana").json()
    assert p["lead"]["status"] == "pending_deposit"
    assert p["payment"]["amount"] == 1945
    assert p.get("payments_test_mode") is True


def test_checkout_ana(s):
    r = s.post(f"{API}/portal/demo-ana/deposit/checkout", json={"origin_url": BASE_URL})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["checkout_url"].startswith("https://checkout.stripe.com")
    assert d["session_id"].startswith("cs_test_")
    st = s.get(f"{API}/payments/status/{d['session_id']}")
    assert st.status_code == 200
    j = st.json()
    assert set(j.keys()) == {"session_id", "status", "payment_status"}
    assert j["session_id"] == d["session_id"] and j["status"] == "initiated" and j["payment_status"] == "pending"
    # lead still pending (unpaid)
    assert s.get(f"{API}/portal/demo-ana").json()["lead"]["status"] == "pending_deposit"


def test_checkout_not_pending(s):
    r = s.post(f"{API}/portal/demo-marcus/deposit/checkout", json={"origin_url": BASE_URL})
    assert r.status_code == 400
    assert "deposit" in r.json()["detail"].lower()


def test_checkout_bad_token(s):
    assert s.post(f"{API}/portal/nope-xyz/deposit/checkout", json={"origin_url": BASE_URL}).status_code == 404


def test_checkout_missing_origin(s):
    assert s.post(f"{API}/portal/demo-ana/deposit/checkout", json={}).status_code == 422


def test_status_unknown(s):
    assert s.get(f"{API}/payments/status/cs_test_doesnotexist").status_code == 404


def test_simulated_pay_removed(s):
    assert s.post(f"{API}/portal/demo-ana/deposit/pay").status_code in (404, 405)


def test_webhook_bad_signature(s):
    r = s.post(f"{API}/stripe/webhook", data=b'{"type":"checkout.session.completed"}',
               headers={"stripe-signature": "t=1,v1=bad", "Content-Type": "application/json"})
    assert r.status_code == 400
    r = s.post(f"{API}/stripe/webhook", data=b'{}')
    assert r.status_code == 400


def test_dev_advance_from_pending_deposit(s):
    lead = next(l for l in s.get(f"{API}/dashboard").json()["leads"] if l["portal_token"] == "demo-ana")
    r = s.post(f"{API}/dev/leads/{lead['id']}/advance")
    assert r.status_code == 200 and r.json()["lead_status"] == "deposit_received"
    assert s.post(f"{API}/portal/demo-ana/deposit/checkout", json={"origin_url": BASE_URL}).status_code == 400
