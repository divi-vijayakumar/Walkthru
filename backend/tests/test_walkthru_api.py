# Walkthru API regression tests: contractor, leads, lead detail, status, messages
import os
import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
SEED = {"lead-bathroom-001": "new", "lead-backsplash-002": "in_review", "lead-deck-003": "quoted"}


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    yield sess
    for lid, st in SEED.items():
        sess.patch(f"{BASE_URL}/api/leads/{lid}/status", json={"status": st})
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    db.messages.delete_many({"content": {"$regex": "^TEST_"}})


# Contractor
def test_contractor(s):
    r = s.get(f"{BASE_URL}/api/contractor")
    assert r.status_code == 200
    d = r.json()
    assert d["name"] == "Apex Remodeling"
    assert d["min_margin_pct"] == 18 and d["max_discount_pct"] == 6
    assert "line_items" in d["rate_card"]
    assert "_id" not in d


# Leads list
def test_leads_list(s):
    r = s.get(f"{BASE_URL}/api/leads")
    assert r.status_code == 200
    d = r.json()
    assert len(d) == 3
    assert {l["id"]: l["status"] for l in d} == SEED
    assert d[0]["id"] == "lead-bathroom-001"  # newest first
    assert all("_id" not in l for l in d)


# Lead detail
def test_lead_detail_hero(s):
    r = s.get(f"{BASE_URL}/api/leads/lead-bathroom-001")
    assert r.status_code == 200
    d = r.json()
    assert d["lead"]["customer_name"] == "Sarah Mitchell"
    assert d["scope"] is None and d["quote"] is None
    seeded = [m for m in d["messages"] if not m["content"].startswith("TEST_")]
    assert len(seeded) == 2
    assert seeded[0]["role"] == "customer" and seeded[1]["role"] == "contractor"


def test_lead_detail_404(s):
    r = s.get(f"{BASE_URL}/api/leads/does-not-exist")
    assert r.status_code == 404


# Status
@pytest.mark.parametrize("st", ["in_review", "quoted", "archived", "new"])
def test_status_change(s, st):
    r = s.patch(f"{BASE_URL}/api/leads/lead-deck-003/status", json={"status": st})
    assert r.status_code == 200 and r.json()["status"] == st
    assert s.get(f"{BASE_URL}/api/leads/lead-deck-003").json()["lead"]["status"] == st


def test_status_invalid(s):
    r = s.patch(f"{BASE_URL}/api/leads/lead-deck-003/status", json={"status": "bogus"})
    assert r.status_code == 422


def test_status_404(s):
    r = s.patch(f"{BASE_URL}/api/leads/nope/status", json={"status": "new"})
    assert r.status_code == 404


# Messages
def test_post_message(s):
    r = s.post(f"{BASE_URL}/api/leads/lead-backsplash-002/messages", json={"content": "  TEST_hello  "})
    assert r.status_code == 200
    m = r.json()
    assert m["role"] == "contractor" and m["content"] == "TEST_hello"
    msgs = s.get(f"{BASE_URL}/api/leads/lead-backsplash-002/messages").json()
    assert any(x["id"] == m["id"] for x in msgs)


def test_post_message_empty(s):
    for c in ["", "   "]:
        r = s.post(f"{BASE_URL}/api/leads/lead-backsplash-002/messages", json={"content": c})
        assert r.status_code == 422


def test_post_message_bad_role_and_404(s):
    assert s.post(f"{BASE_URL}/api/leads/lead-backsplash-002/messages",
                  json={"content": "TEST_x", "role": "system"}).status_code == 422
    assert s.post(f"{BASE_URL}/api/leads/nope/messages", json={"content": "TEST_x"}).status_code == 404
