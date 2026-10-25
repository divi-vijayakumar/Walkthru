# 15:34 call (Vapi 01a173b2): every call ends with an exact quote. TEST_ leads only, cleaned up afterwards.
import os
import uuid
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
API = f"{os.environ['REACT_APP_BACKEND_URL'].rstrip('/')}/api"
_db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
SAFE_PHONE = "(408) 555-0199"


@pytest.fixture(scope="module")
def s(owner_token):
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {owner_token}", "Origin": os.environ["REACT_APP_BACKEND_URL"].rstrip("/")})
    return sess


@pytest.fixture(scope="module")
def made():
    ids = []
    yield ids
    for lid in ids:
        _db.leads.delete_one({"id": lid})
        for c in ("itemizer_sessions", "itemizer_insights", "itemizer_goals", "itemizer_tips", "quotes", "sms_log", "call_sessions", "followups"):
            _db[c].delete_many({"lead_id": lid})


def new_lead(s, made, ask="Bathroom remodel"):
    r = s.post(f"{API}/leads", json={"name": f"TEST_Exact {uuid.uuid4().hex[:4]}", "phone": SAFE_PHONE, "source": "website", "ask": ask})
    assert r.status_code == 200, r.text
    made.append(r.json()["lead"]["id"])
    if not r.json()["lead"].get("portal_token"):
        s.post(f"{API}/leads/{made[-1]}/start-agent")
    return _db.leads.find_one({"id": made[-1]}, {"_id": 0})


def turn(s, lead, said="", answers=None, wants_price=False, camera_on=False, skipped=None):
    r = s.post(f"{API}/itemizer/{lead['id']}/turn", json={"said": said, "answers": answers or {}, "wants_price": wants_price,
                                                          "camera_on": camera_on, "skipped": skipped or []})
    assert r.status_code == 200, r.text
    return r.json()


def test_replay_1534_call(s, made):
    lead = new_lead(s, made)
    outs = [turn(s, lead, "I want to change the tiling on the shower panels.", camera_on=True),
            turn(s, lead, "Retiling the shower, adding a larger niche, wallpapering the wall, replacing the mirror with LED-lit mirror.", camera_on=True),
            turn(s, lead, "We'll go with the standard finish.", {"finish_level": "standard"}),
            turn(s, lead, "No size change.", {"shower_size": "same"}),
            turn(s, lead, "I'd like the mirror replaced with the LED.", {"replace_mirror": "yes"}),
            turn(s, lead, "Just give me the quote.", wants_price=True)]
    f = outs[-1]
    assert f["status"] == "ok" and f["total"] > 0, f
    assert "low" not in f and "high" not in f
    labels = [i["label"] for i in f["lines"]]
    for want in ("Shower wall retile", "Shower niche", "Accent wallpaper", "Lighted (LED) mirror", "Hardwired electrical line for the mirror"):
        assert want in labels, labels
    assert any(lb.startswith("Permit") and "electrical" in lb for lb in labels), labels
    assert not any("No size change" in lb for lb in labels) and "Walk-in shower" not in labels
    assert sum("mirror replaced" in o["next_text"] for o in outs) <= 1
    assert any("assumed, to confirm at the site visit" in a for a in f["assumptions"])
    questions = [o["next_text"] for o in outs[:-1] if o["next_text"]]
    assert len(questions) == len(set(questions)), [(o["fact"], o["next_text"][:70]) for o in outs]


def test_premium_tile_answer_sets_shower_tile(s, made):
    lead = new_lead(s, made)
    turn(s, lead, "I want to retile the shower")
    turn(s, lead, "", {"custom_in": "premium tile", "finish_level": "standard"})
    f = turn(s, lead, "", wants_price=True)
    tile = next(i for i in f["lines"] if i["label"] == "Shower wall retile")
    assert tile["amount"] == 80 * (6 + 14 + 25), tile


def test_done_words_and_skipped(s, made):
    lead = new_lead(s, made)
    out = turn(s, lead, "I want a new vanity")
    assert out["status"] == "needs_info"
    out = turn(s, lead, "", skipped=[out["fact"]])
    out = turn(s, lead, "Nope, that's it, nothing else.")
    assert out["status"] == "ok" and out["total"] > 0


def test_empty_scope_prices_standard_package(s, made):
    lead = new_lead(s, made)
    out = turn(s, lead, "", wants_price=True)
    assert out["status"] == "ok" and out["total"] > 0
    assert "Bathroom remodel, standard finish, medium size (assumed)" in [i["label"] for i in out["lines"]]


def test_hang_up_saves_and_sends_one_quote(s, made):
    lead = new_lead(s, made)
    tok = lead["portal_token"]
    assert requests.post(f"{API}/portal/{tok}/call/start").status_code == 200
    turn(s, lead, "I want to retile the shower and add a niche")
    assert _db.quotes.count_documents({"lead_id": lead["id"]}) == 0
    report = {"message": {"type": "end-of-call-report", "endedReason": "customer-ended-call",
                          "call": {"id": f"TEST_{uuid.uuid4().hex}", "assistantOverrides": {"variableValues": {"lead_token": tok}}}}}
    hdr = {"X-Vapi-Secret": os.environ["VAPI_SERVER_SECRET"]}
    for _ in range(2):  # a repeated report must not send the same version twice
        assert requests.post(f"{API}/vapi/webhook", json=report, headers=hdr).status_code == 200
    q = _db.quotes.find_one({"lead_id": lead["id"]}, sort=[("version", -1)])
    assert q and q["total"] > 0
    sent = [m for m in _db.sms_log.find({"lead_id": lead["id"]}) if m.get("kind") == "quote_ready"]
    assert len(sent) == 1 and f"${q['total']:,}" in sent[0]["body"], sent
