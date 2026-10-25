# Open-ended requests (partition), two-scenario prices, Apex-priced custom work, and the 14:23 call fixes.
# TEST_ leads only (non-allowlisted phone), never /dev/reset, cleans up after itself.
import os
import sys
import json
import uuid
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
from core.service_auth import sign  # noqa: E402

API = f"{os.environ['REACT_APP_BACKEND_URL'].rstrip('/')}/api"
_db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
SAFE_PHONE = "(408) 555-0199"
ANS = {"wall_replacement": "fully open", "wall_length": "12 feet", "wall_floor_finish": "patch the floor to match", "floor_above": "yes",
       "wall_central": "yes", "finish_level": "standard", "tile_replacement": "vinyl plank", "tile_where": "floor", "vanity_plan": "yes",
       "new_vanity_mount": "floating", "new_vanity_sinks": "one", "floor_area": "40", "timeline": "in two months", "water_damage": "no",
       "replacing_vanity": "new", "custom_out": "nothing", "custom_in": "a wooden pergola", "custom_size": "about 12 by 10 feet", "floor_new": "tile"}
OPENING = "I have a half bath. I want to take out the tiles, make the sink area a little better, and change the mirrors."


@pytest.fixture(scope="module")
def s(owner_token):
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {owner_token}", "Origin": os.environ["REACT_APP_BACKEND_URL"].rstrip("/")})
    return sess


@pytest.fixture(scope="module")
def made():
    leads, tasks = [], []
    yield leads, tasks
    for lid in leads:
        _db.leads.delete_one({"id": lid})
        for c in ("itemizer_sessions", "itemizer_insights", "itemizer_goals", "quotes", "sms_log", "call_sessions", "followups", "frames"):
            _db[c].delete_many({"lead_id": lid})
    _db.kb_tasks.delete_many({"task_id": {"$in": tasks}})


def new_lead(s, made, ask):
    r = s.post(f"{API}/leads", json={"name": f"TEST_Open {uuid.uuid4().hex[:4]}", "phone": SAFE_PHONE, "source": "website", "ask": ask})
    assert r.status_code == 200, r.text
    made[0].append(r.json()["lead"]["id"])
    return _db.leads.find_one({"id": r.json()["lead"]["id"]}, {"_id": 0})


def turn(s, lead, said="", answers=None, wants_price=False):
    r = s.post(f"{API}/itemizer/{lead['id']}/turn", json={"said": said, "answers": answers or {}, "wants_price": wants_price})
    assert r.status_code == 200, r.text
    return r.json()


def answer_until_priced(s, lead, out, extra=None):
    asked = [out["fact"]]
    for _ in range(15):
        if out["status"] == "ok":
            break
        out = turn(s, lead, "", {out["fact"]: ANS.get(out["fact"], "no"), **(extra or {})})
        asked.append(out["fact"])
    return out, asked


def test_partition_living_room_floor_above(s, made):
    lead = new_lead(s, made, "Living room remodel")
    out = turn(s, lead, "I want to remove this partition", {"wall_outlets": "yes"})
    assert out["status"] == "needs_info" and out["fact"] == "wall_replacement"
    assert "in its place" in out["next_text"]
    out, asked = answer_until_priced(s, lead, out)
    assert out["status"] == "ok" and asked.index("wall_length") < asked.index("finish_level")
    labels = {i["label"]: i["amount"] for i in turn(s, lead, "", {}, True)["lines"]}
    for want in ("Engineer and beam allowance", "Relocate outlets", "Patch floor where the wall stood", "Patch and paint ceiling", "Demolition and haul-away"):
        assert want in labels, labels
    assert labels["Patch floor where the wall stood"] == 540 and any(k.startswith("Permit") and "structural" in k for k in labels)
    assert out["if_not"]["total"] == out["total"] - 6800 and "drops by about $6,800" in out["if_not"]["say"]
    assert requests.post(f"{API}/portal/{lead['portal_token']}/call/start").status_code == 200
    body = {"message": {"toolCallList": [{"id": "t1", "function": {"name": "update_scope", "arguments": {"wants_price": True}}}]}}
    res = requests.post(f"{API}/portal/{lead['portal_token']}/agent/tools", json=body).json()["results"][0]
    assert json.loads(res["result"])["if_not"]["total"] == out["if_not"]["total"]
    q = _db.quotes.find_one({"lead_id": lead["id"]}, sort=[("version", -1)])
    assert q["if_not"]["total"] == out["if_not"]["total"]
    pdf = s.get(f"{API}/quotes/{q['id']}/pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def test_bathroom_partition_asks_which_kind(s, made):
    lead = new_lead(s, made, "Bathroom remodel")
    out = turn(s, lead, "I want to remove the partition")
    assert out["fact"] == "partition_kind" and out["next_text"] == "Is it a full wall, a shorter divider, or the glass by the shower?"
    out = turn(s, lead, "", {"partition_kind": "the glass by the shower"})
    assert "Remove glass shower panel" in out["new_items"] and "Wall removal" not in out["new_items"]


def test_empty_scope_never_priced(s, made):
    lead = new_lead(s, made, "Bathroom refresh")
    out = turn(s, lead, "", {}, True)
    assert out["status"] == "needs_info" and out["next_action"] == "ask" and "total" not in out
    assert _db.quotes.count_documents({"lead_id": lead["id"]}) == 0


def test_wants_price_with_p0_open_explains(s, made):
    lead = new_lead(s, made, "Bathroom refresh")
    out = turn(s, lead, "Remove the floor tile. How much?")
    assert out["status"] == "needs_info"
    assert out["next_text"].startswith("Just so the number means something: what would you like instead")


def test_half_bath_opening(s, made):
    lead = new_lead(s, made, "Half bath")
    out = turn(s, lead, OPENING)
    assert out["status"] == "needs_info" and "total" not in out
    assert {"Tile work (floor or wall, to confirm)", "Remove vanity", "New vanity", "Replace mirror or medicine cabinet"} <= set(out["new_items"])
    assert out["fact"] == "tile_replacement"
    out, asked = answer_until_priced(s, lead, out)
    assert {"tile_where", "vanity_plan", "floor_area", "finish_level"} <= set(asked)
    assert out["status"] == "ok" and out["total"] > 0
    lines = turn(s, lead, "", {}, True)["lines"]
    assert lines and all(isinstance(i["amount"], int) for i in lines), lines
    assert "Bathroom floor" in [i["label"] for i in lines]


def test_sync_means_sink_and_mirror_trigger(s, made):
    lead = new_lead(s, made, "Powder room")
    out = turn(s, lead, "I want to update the sync area and swap the mirror")
    assert {"Remove vanity", "New vanity", "Replace mirror or medicine cabinet"} <= set(out["new_items"])


def test_custom_work_then_priced_from_dashboard(s, made):
    lead = new_lead(s, made, "Living room remodel")
    out = turn(s, lead, "I want to add a small sauna in the corner")
    assert out["status"] == "needs_info" and out["fact"] in ("custom_out", "custom_in", "custom_size", "finish_level")
    out, _ = answer_until_priced(s, lead, out)
    out = turn(s, lead, "", {}, True)
    assert out["status"] == "needs_info" and "total" not in out
    assert _db.quotes.count_documents({"lead_id": lead["id"]}) == 0
    items = s.get(f"{API}/itemizer/{lead['id']}/custom").json()["items"]
    assert items and items[0]["in"] == "a wooden pergola" and items[0]["size"]
    r = s.post(f"{API}/itemizer/{lead['id']}/items/{items[0]['item_id']}/price",
               json={"label": "TEST_Sauna", "tiers": [3000, 4500, 7000], "match": "sauna"})
    assert r.status_code == 200, r.text
    made[1].append(r.json()["task_id"])
    assert r.json()["total"] > 4500
    assert not any(m.get("kind") == "quote_ready" for m in _db.sms_log.find({"lead_id": lead["id"]}))
    lead2 = new_lead(s, made, "Living room remodel")
    out2 = turn(s, lead2, "Could you put in a sauna?")
    assert "TEST_Sauna" in out2["new_items"]


def test_end_call_without_priced_quote_is_pending(s, made):
    lead = new_lead(s, made, "Bathroom refresh")
    tok = lead["portal_token"]
    assert requests.post(f"{API}/portal/{tok}/call/start").status_code == 200
    turn(s, lead, "", {}, True)
    assert requests.post(f"{API}/portal/{tok}/call/end", json={}).status_code == 200
    after = _db.leads.find_one({"id": lead["id"]})
    assert after["quote_pending"] is True and after.get("quote_pending_due_at")
    assert not any(m.get("kind") == "quote_ready" for m in _db.sms_log.find({"lead_id": lead["id"]}))


def test_camera_survey_fills_facts_and_suggests(s, made):
    lead = new_lead(s, made, "Half bath")
    turn(s, lead, "I want to take out the tiles")
    gid = f"g_{uuid.uuid4().hex}"
    _db.itemizer_goals.insert_one({"goal_id": gid, "lead_id": lead["id"], "call_session_id": "none", "kind": "survey", "fact_id": None,
                                   "options": [], "numeric": False, "status": "sent", "created_at": "2026-01-01T00:00:00+00:00"})
    hits = [{"label": "sink: pedestal", "confidence": 0.9, "frame_url": "https://x/f1", "t_ms": 1},
            {"label": "mirror: framed", "confidence": 0.8, "frame_url": "https://x/f2", "t_ms": 2}]
    raw = json.dumps({"event": "goal.completed", "data": {"goal_id": gid, "status": "done", "result": "met", "value": 32, "hits": hits}}).encode()
    r = requests.post(f"{API}/itemizer/percia/callback", data=raw, headers={"x-walkthru-signature": sign(os.environ["PERCIA_KEY"], raw),
                                                                             "Content-Type": "application/json"})
    assert r.status_code == 200, r.text
    sess = s.get(f"{API}/itemizer/{lead['id']}").json()
    assert sess["survey"]["sink_type"]["value"] == "pedestal" and sess["survey"]["floor_area"]["value"] == 32
    assert any(i["text"] == "I can see a pedestal sink and a framed mirror" for i in sess["insights"])
    out = turn(s, lead, "", {"tile_replacement": "vinyl plank"})
    assert "mirror replaced" in out["next_text"]
    assert "Replace mirror or medicine cabinet" not in [i["label"] for i in sess["items"]]
