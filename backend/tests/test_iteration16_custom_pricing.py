# Iteration 16: dashboard pricing of 'To be priced by Apex' lines (validation, rate-card reuse, no SMS), if_not in PDF,
# and P0 gating when the contractor prices a custom line. Only TEST_ leads with (408) 555-0199; never calls /dev/reset or /kb/reset.
import os
import pytest
import requests
import fitz
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
_db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
SAFE_PHONE = "(408) 555-0199"
CUSTOM = {"custom_out": "nothing", "custom_in": "a small sauna", "custom_size": "5 by 6 feet", "finish_level": "standard"}


@pytest.fixture(scope="module")
def s(owner_token):
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {owner_token}", "Origin": BASE_URL})
    return sess


@pytest.fixture(scope="module")
def L(s):
    made = {}

    def make(key, ask="Living room remodel"):
        r = s.post(f"{API}/leads", json={"name": f"TEST_It16 {key}", "phone": SAFE_PHONE, "source": "website", "ask": ask})
        assert r.status_code == 200, r.text
        lead = r.json()["lead"]
        if not lead.get("portal_token"):
            s.post(f"{API}/leads/{lead['id']}/start-agent")
        made[key] = _db.leads.find_one({"id": lead["id"]}, {"_id": 0})
        return made[key]
    yield make
    for lead in made.values():
        for c in ("itemizer_sessions", "itemizer_insights", "itemizer_goals", "itemizer_tips", "quotes", "sms_log", "call_sessions", "followups", "pricing_states"):
            _db[c].delete_many({"lead_id": lead["id"]})
        _db.leads.delete_one({"id": lead["id"]})
    _db.kb_tasks.delete_many({"task_id": {"$regex": "^custom_test_it16"}})


def turn(s, lid, said="", answers=None, wants_price=False):
    r = s.post(f"{API}/itemizer/{lid}/turn", json={"said": said, "answers": answers or {}, "wants_price": wants_price})
    assert r.status_code == 200, r.text
    return r.json()


def drive(s, lid, r, vals, n=15):
    for _ in range(n):
        if r["status"] == "ok" or r["fact"] in ("scope", ""):
            break
        r = turn(s, lid, "", {r["fact"]: vals.get(r["fact"], "not sure")})
    return r


def custom_items(s, lid):
    r = s.get(f"{API}/itemizer/{lid}/custom")
    assert r.status_code == 200, r.text
    return r.json()["items"]


# Custom pricing: auth + validation
def test_price_custom_validation(s, L):
    lid = L("val")["id"]
    turn(s, lid, "I want to put in a small koi pond in the corner")
    items = custom_items(s, lid)
    assert len(items) == 1 and items[0]["label"].startswith("To be priced by Apex:")
    iid = items[0]["item_id"]
    url = f"{API}/itemizer/{lid}/items/{iid}/price"
    assert requests.post(url, json={"label": "X sauna", "tiers": [1, 2, 3], "match": "sauna"}).status_code == 401
    assert requests.get(f"{API}/itemizer/{lid}/custom").status_code == 401
    for body in ({"label": "TEST_It16 sauna", "tiers": [-1, 2, 3], "match": "sauna"},
                 {"label": "TEST_It16 sauna", "tiers": [0, 0, 0], "match": "sauna"},
                 {"label": "TEST_It16 sauna", "tiers": [1, 2, 3], "match": "ab, c"},
                 {"label": "TEST_It16 sauna", "tiers": [1, 2], "match": "sauna"},
                 {"label": "x", "tiers": [1, 2, 3], "match": "sauna"}):
        assert s.post(url, json=body).status_code == 422, body
    assert s.post(f"{API}/itemizer/{lid}/items/nope/price", json={"label": "TEST_It16 sauna", "tiers": [1, 2, 3], "match": "sauna"}).status_code == 404


# Custom pricing: rate-card task, new quote version, no SMS, next homeowner gets it priced
def test_price_custom_then_next_homeowner(s, L):
    lead = L("first")
    lid = lead["id"]
    r = drive(s, lid, turn(s, lid, "I want to put in a small koi pond with a fountain"), CUSTOM)
    # iteration 17: custom-only scope still gets an exact number (standard package); the custom line stays "to be priced"
    assert r["status"] == "ok" and r["total"] > 0 and any("koi pond" in x for x in r["to_be_priced"]), r
    iid = custom_items(s, lid)[0]["item_id"]
    sms_before = _db.sms_log.count_documents({"lead_id": lid})
    out = s.post(f"{API}/itemizer/{lid}/items/{iid}/price", json={"label": "TEST_It16 Koi pond", "tiers": [4000, 6000, 9000], "match": "koi pond"})
    assert out.status_code == 200, out.text
    d = out.json()
    assert d["task_id"].startswith("custom_test_it16") and d["quote_id"] and d["total"] == 6000 + 450, d
    q = _db.quotes.find_one({"id": d["quote_id"]}, {"_id": 0})
    assert any(i["label"] == "TEST_It16 Koi pond" and i["amount"] == 6000 for i in q["line_items"])
    assert _db.sms_log.count_documents({"lead_id": lid}) == sms_before  # never messages the homeowner
    assert custom_items(s, lid) == []
    assert s.post(f"{API}/itemizer/{lid}/items/{iid}/price", json={"label": "TEST_It16 again", "tiers": [1, 2, 3], "match": "again"}).status_code == 404
    kb = s.get(f"{API}/kb").json()["tasks"]
    task = next(t for t in kb if t["task_id"] == d["task_id"])
    assert task["label"] == "TEST_It16 Koi pond" and task["price"][0]["tiers"] == [4000, 6000, 9000]
    # next homeowner
    lid2 = L("second")["id"]
    r2 = turn(s, lid2, "we would love a koi pond near the patio door")
    print(r2)
    assert "TEST_It16 Koi pond" in r2["new_items"] and not any(x.startswith("To be priced") for x in r2["new_items"]), r2
    r2 = drive(s, lid2, r2, CUSTOM)
    assert r2["status"] == "ok" and any(ln["label"] == "TEST_It16 Koi pond" and ln["amount"] == 6000 for ln in r2["lines"]), r2


# Pricing a custom line must not save a quote while another job's must-ask (P0) facts are still open
def test_price_custom_respects_open_p0(s, L):
    lid = L("p0")["id"]
    turn(s, lid, "I want to put in a big saltwater aquarium in the corner and knock down this wall")
    r = turn(s, lid, "", {"custom_out": "nothing", "custom_in": "an aquarium", "custom_size": "6 feet long"})
    iid = custom_items(s, lid)[0]["item_id"]
    out = s.post(f"{API}/itemizer/{lid}/items/{iid}/price", json={"label": "TEST_It16 P0 sauna", "tiers": [4000, 6000, 9000], "match": "koi pond zz"})
    assert out.status_code == 200, out.text
    open_p0 = [f["name"] for f in s.get(f"{API}/itemizer/{lid}").json()["facts"] if f.get("p0") and f["state"] != "resolved"]
    print(open_p0, out.json())
    assert open_p0, "expected wall P0 facts to still be open"
    assert out.json()["quote_id"] is None, f"quote saved with must-ask facts open: {open_p0}"


# if_not two-scenario price appears in the quote PDF
def test_if_not_in_pdf(s, L):
    lead = L("wall")
    lid = lead["id"]
    vals = {"wall_replacement": "fully open", "wall_length": "12", "wall_floor_finish": "patch", "finish_level": "standard",
            "floor_above": "yes", "wall_central": "yes"}
    turn(s, lid, "I want to knock down this wall")
    r = drive(s, lid, turn(s, lid, "", vals), vals)  # iteration 17: facts volunteered at once (5-question budget)
    assert r["status"] == "ok" and r["if_not"] and r["if_not"]["diff"] == -6800, r
    assert r["if_not"]["say"] == "If it isn't load-bearing, the price drops by $6,800.", r["if_not"]  # exact diff, no "about"
    assert requests.post(f"{API}/portal/{lead['portal_token']}/call/start").status_code == 200
    body = {"message": {"toolCallList": [{"id": "t1", "function": {"name": "update_scope", "arguments": {"wants_price": True}}}]}}
    assert requests.post(f"{API}/portal/{lead['portal_token']}/agent/tools", json=body).status_code == 200
    q = _db.quotes.find_one({"lead_id": lid}, sort=[("version", -1)])
    assert q["if_not"]["total"] == q["total"] - 6800
    pdf = s.get(f"{API}/quotes/{q['id']}/pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    text = "".join(p.get_text() for p in fitz.open(stream=pdf.content, filetype="pdf")).replace("\n", " ")
    assert "If it isn't load-bearing, the price drops by $6,800." in text, text
