# Iteration 18: every call ends with one exact quote; listen rules; mapping; backstop; no ranges. TEST_ leads only, cleaned up.
import json
import os
import re
import uuid
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
_db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
SAFE_PHONE = "(408) 555-0199"
COLLS = ("itemizer_sessions", "itemizer_insights", "itemizer_goals", "itemizer_tips", "quotes", "sms_log", "call_sessions", "followups", "pricing_states")
PKG = "Bathroom remodel, standard finish, medium size (assumed)"


@pytest.fixture(scope="module")
def s(owner_token):
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {owner_token}", "Origin": BASE})
    return sess


@pytest.fixture(scope="module")
def made():
    ids = []
    yield ids
    for lid in ids:
        _db.leads.delete_one({"id": lid})
        for c in COLLS:
            _db[c].delete_many({"lead_id": lid})
    _db.kb_tasks.delete_many({"from_custom.lead_id": {"$in": ids}})


def new_lead(s, made, ask="Bathroom remodel"):
    r = s.post(f"{API}/leads", json={"name": f"TEST_It18 {uuid.uuid4().hex[:4]}", "phone": SAFE_PHONE, "source": "website", "ask": ask})
    assert r.status_code == 200, r.text
    made.append(r.json()["lead"]["id"])
    lead = _db.leads.find_one({"id": made[-1]}, {"_id": 0})
    if not lead.get("portal_token"):
        s.post(f"{API}/leads/{lead['id']}/start-agent")
        lead = _db.leads.find_one({"id": made[-1]}, {"_id": 0})
    return lead


def turn(s, lead, said="", answers=None, wants_price=False, camera_on=False, skipped=None):
    r = s.post(f"{API}/itemizer/{lead['id']}/turn", json={"said": said, "answers": answers or {}, "wants_price": wants_price,
                                                          "camera_on": camera_on, "skipped": skipped or []})
    assert r.status_code == 200, r.text
    return r.json()


def labels(out):
    return [i["label"] for i in out.get("lines") or []]


def tool(tok, args, name="update_scope"):
    msg = {"message": {"type": "tool-calls", "toolCallList": [{"id": "tc1", "function": {"name": name, "arguments": json.dumps(args)}}]}}
    r = requests.post(f"{API}/portal/{tok}/agent/tools", json=msg)
    assert r.status_code == 200, r.text
    res = r.json()["results"][0]
    assert "error" not in res, res
    return json.loads(res["result"])


def no_range(obj):
    txt = json.dumps(obj)
    assert '"low"' not in txt and '"high"' not in txt and '"range_pct"' not in txt, txt[:400]
    assert not re.search(r"\$[\d,]+\s*(to|-|–)\s*\$[\d,]+", txt), txt[:400]


# R1: no work and no price wanted -> ask for the work, no package
def test_r1_no_work_asks_what_work(s, made):
    lead = new_lead(s, made)
    out = turn(s, lead, "Hi, good afternoon.")
    assert out["status"] == "needs_info" and "What work would you like done?" in out["next_text"], out
    assert PKG not in out.get("new_items", [])


# Empty scope + wants_price -> standard package > $0
def test_empty_scope_wants_price(s, made):
    lead = new_lead(s, made)
    out = turn(s, lead, "", wants_price=True)
    assert out["status"] == "ok" and out["total"] > 0 and PKG in labels(out), out
    no_range(out)
    # R2: package removed once real priced work exists
    turn(s, lead, "I want to replace the toilet")
    out = turn(s, lead, "", wants_price=True)
    assert out["status"] == "ok" and PKG not in labels(out), labels(out)


# R3: LED mirror alone -> LED mirror + hardwired line + electrical permit, no exhaust fan
def test_r3_led_mirror(s, made):
    lead = new_lead(s, made)
    turn(s, lead, "I'd like to replace the mirror with an LED lit mirror.")
    out = turn(s, lead, "", wants_price=True)
    lb = labels(out)
    assert "Lighted (LED) mirror" in lb and "Hardwired electrical line for the mirror" in lb, lb
    assert any(x.startswith("Permit") and "electrical" in x for x in lb), lb
    assert not any("xhaust" in x for x in lb), lb


# R3: shower wall retile -> no walk-in shower; descriptive clause -> no custom line
def test_r3_shower_retile_and_descriptive(s, made):
    lead = new_lead(s, made)
    turn(s, lead, "The bathroom is pretty old and the grout looks dirty. I want to retile the shower walls.")
    out = turn(s, lead, "", wants_price=True)
    lb = labels(out)
    assert "Shower wall retile" in lb and "Walk-in shower" not in lb, lb
    assert not out.get("to_be_priced"), out.get("to_be_priced")


# Mapping: niche, wallpaper
def test_mapping_niche_wallpaper(s, made):
    lead = new_lead(s, made)
    turn(s, lead, "Add a larger niche in the shower and wallpaper the wall.")
    out = turn(s, lead, "that's it", wants_price=True)
    lb = labels(out)
    assert "Shower niche" in lb and "Accent wallpaper" in lb, lb


# R4: free text on every KB fact never 500s (itemizer turn + Vapi-style tool)
def test_r4_free_text_answers_never_500(s, made):
    kb = s.get(f"{API}/kb").json()
    facts = kb.get("facts") or []
    names = [f.get("fact_id") or f.get("name") for f in facts]
    assert names, kb.keys()
    lead = new_lead(s, made)
    turn(s, lead, "Retile the shower, new vanity, new toilet, LED mirror, new floor tile and a niche")
    bad = {n: "uh kind of a lot I guess, maybe purple" for n in names}
    out = turn(s, lead, "", bad)
    out = turn(s, lead, "", {n: "banana" for n in names}, wants_price=True)
    assert out["status"] == "ok" and out["total"] > 0
    # Vapi tool path via portal mock
    lead2 = new_lead(s, made)
    assert requests.post(f"{API}/portal/{lead2['portal_token']}/call/start").status_code == 200
    tool(lead2["portal_token"], {"said": "Retile the shower and new vanity"})
    r = tool(lead2["portal_token"], {"said": "", "answers": {n: "several big ones" for n in names}})
    assert "status" in r
    r = tool(lead2["portal_token"], {"said": "", "answers": {n: 12 for n in names}, "wants_price": True})
    assert r["status"] == "ok" and r["total"] > 0, r
    no_range(r)


# R5: 'not sure' variants assume immediately, never re-asked; no doubled suffix
@pytest.mark.parametrize("ans", ["not sure", "Not sure.", "I'm not sure", "no idea", "I don't know"])
def test_r5_not_sure_never_reasked(s, made, ans):
    lead = new_lead(s, made)
    out = turn(s, lead, "I want a new vanity")
    assert out["status"] == "needs_info" and out["fact"], out
    fact, asked = out["fact"], [out["next_text"]]
    for _ in range(6):
        out = turn(s, lead, "", {fact: ans} if out["fact"] == fact else {out["fact"]: "standard"} if out["fact"] else {})
        if out["status"] == "ok":
            break
        assert out["fact"] != fact, f"{fact} re-asked after '{ans}': {out['next_text']}"
        asked.append(out["next_text"])
    out = turn(s, lead, "", wants_price=True)
    assert out["status"] == "ok"
    for a in out["assumptions"]:
        assert a.count("site visit") <= 1, a


# wants_price never returns needs_info from any state
def test_wants_price_any_state(s, made):
    lead = new_lead(s, made)
    assert turn(s, lead, "", wants_price=True)["status"] == "ok"
    lead = new_lead(s, made)
    o = turn(s, lead, "I want to redo the whole shower and a new vanity", camera_on=True)
    assert o["status"] == "needs_info"
    o = turn(s, lead, "", {o["fact"]: "hmm"}, wants_price=True, camera_on=True)
    assert o["status"] == "ok" and o["total"] > 0, o
    lead = new_lead(s, made)
    turn(s, lead, "I want to build a koi pond aquarium wall")
    o = turn(s, lead, "", wants_price=True)
    assert o["status"] == "ok" and o["total"] > 0, o


@pytest.mark.parametrize("w", ["that's it", "nothing else", "just give me the quote", "let's conclude", "wrap up", "Let's wrap this up."])
def test_done_words(s, made, w):
    lead = new_lead(s, made)
    turn(s, lead, "I want a new vanity and retile the shower")
    o = turn(s, lead, w)
    assert o["status"] == "ok" and o["total"] > 0, (w, o)


# Skipped list assumed, never re-asked; budget 5 questions per call
def test_skipped_and_budget(s, made):
    lead = new_lead(s, made)
    assert requests.post(f"{API}/portal/{lead['portal_token']}/call/start").status_code == 200
    o = turn(s, lead, "New vanity, retile the shower, new floor tile, new toilet, new tub, LED mirror, niche, new lights")
    skipped, qs = [], []
    for i in range(12):
        if o["status"] == "ok":
            break
        assert o["fact"] not in skipped, (o["fact"], skipped)
        qs.append(o["fact"])
        skipped.append(o["fact"])
        o = turn(s, lead, "", skipped=[o["fact"]])
    assert o["status"] == "ok", (qs, o)
    assert len(qs) <= 5, qs


# Each fact asked at most once: an unparseable answer to a numeric fact must be assumed, not re-asked
def test_unparseable_numeric_answer_not_reasked(s, made):
    lead = new_lead(s, made)
    o = turn(s, lead, "I want to retile the shower walls")
    assert o["fact"] == "shower_wall_area", o
    o2 = turn(s, lead, "", {"shower_wall_area": "pretty big I guess"})
    assert o2["fact"] != "shower_wall_area", f"re-asked: {o2['next_text']}"


# Invalid categorical answers must be validated against options (not stored raw / underpriced)
def test_invalid_categorical_answer_not_underpriced(s, made):
    a, b = new_lead(s, made), new_lead(s, made)
    for lead in (a, b):
        turn(s, lead, "I want a new vanity")
    turn(s, a, "", {"new_vanity_sinks": "purple maybe", "new_vanity_mount": "whatever you think"})
    pa = turn(s, a, "", wants_price=True)
    pb = turn(s, b, "", skipped=["new_vanity_sinks", "new_vanity_mount"], wants_price=True)
    va = next(i["amount"] for i in pa["lines"] if i["label"] == "New vanity")
    vb = next(i["amount"] for i in pb["lines"] if i["label"] == "New vanity")
    assert va == vb, f"garbage answers priced vanity at ${va} vs default ${vb}"


# Answers are not work: 'No size change' / 'no' / 'nothing else' create no items
def test_answers_are_not_work(s, made):
    lead = new_lead(s, made)
    o = turn(s, lead, "I want to retile the shower")
    f = o["fact"] or "shower_size"
    o = turn(s, lead, "No size change.", {f: "no"})
    assert o["new_items"] == [] or all("size" not in x.lower() for x in o["new_items"]), o["new_items"]
    o = turn(s, lead, "no", {"finish_level": "no"})
    o = turn(s, lead, "nothing else")
    assert o["status"] == "ok"
    assert not any("No size" in x or x.lower() in ("no", "nothing else") for x in labels(o)), labels(o)
    assert not o.get("to_be_priced"), o.get("to_be_priced")


# Portal agent/end in mock mode backstop: saves a quote and sends exactly one quote_ready
def test_portal_agent_end_backstop(s, made):
    lead = new_lead(s, made)
    tok = lead["portal_token"]
    assert requests.post(f"{API}/portal/{tok}/call/start").status_code == 200
    tool(tok, {"said": "I want to retile the shower and add a niche"})
    assert _db.quotes.count_documents({"lead_id": lead["id"], "total": {"$gt": 0}}) == 0
    for _ in range(2):
        r = requests.post(f"{API}/portal/{tok}/agent/end", json={"message": {"type": "end-of-call-report"}})
        assert r.status_code == 200, r.text
    q = _db.quotes.find_one({"lead_id": lead["id"]}, sort=[("version", -1)])
    assert q and q["total"] > 0
    sent = [m for m in _db.sms_log.find({"lead_id": lead["id"]}) if m.get("kind") == "quote_ready"]
    assert len(sent) == 1, sent
    assert not re.search(r"\$[\d,]+\s*(to|-)\s*\$", sent[0]["body"]), sent[0]["body"]
    # portal payload & PDFs: exact total, no range
    for url, hdr in ((f"{API}/portal/{tok}/quote.pdf", {}), (f"{API}/quotes/{q['id']}/pdf", dict(s.headers))):
        r = requests.get(url, headers=hdr)
        assert r.status_code == 200 and r.content[:4] == b"%PDF", (url, r.status_code)
        import fitz
        text = " ".join(pg.get_text() for pg in fitz.open(stream=r.content, filetype="pdf"))
        assert f"${q['total']:,}" in text, text[:500]
        assert "range" not in text.lower() and not re.search(r"\$[\d,]+\s*(to|-|–)\s*\$", text), text[:800]


# Portal payload exposes no range keys
def test_portal_payload_no_range(s, made):
    lead = new_lead(s, made)
    tok = lead["portal_token"]
    requests.post(f"{API}/portal/{tok}/call/start")
    tool(tok, {"said": "new toilet", "wants_price": True})
    requests.post(f"{API}/portal/{tok}/agent/end", json={"message": {"type": "end-of-call-report"}})
    pq = requests.get(f"{API}/portal/{tok}").json().get("quote") or {}
    assert pq.get("total", 0) > 0
    assert not {"low", "high", "range_pct"} & set(pq), f"portal quote exposes range keys: {sorted(pq)}"


# Webhook with a quote from this call already: repeat report doesn't send twice; if_not exact difference
def test_webhook_existing_quote_once(s, made):
    lead = new_lead(s, made)
    tok = lead["portal_token"]
    assert requests.post(f"{API}/portal/{tok}/call/start").status_code == 200
    tool(tok, {"said": "New vanity and retile the shower"})
    r = tool(tok, {"said": "just give me the quote", "wants_price": True})
    assert r["status"] == "ok" and r["total"] > 0
    for x in r.get("if_not") or []:
        assert re.search(r"\$[\d,]+", json.dumps(x)), x
    report = {"message": {"type": "end-of-call-report", "call": {"id": f"TEST_{uuid.uuid4().hex}", "assistantOverrides": {"variableValues": {"lead_token": tok}}}}}
    hdr = {"X-Vapi-Secret": os.environ["VAPI_SERVER_SECRET"]}
    for _ in range(3):
        assert requests.post(f"{API}/vapi/webhook", json=report, headers=hdr).status_code == 200
    sent = [m for m in _db.sms_log.find({"lead_id": lead["id"]}) if m.get("kind") == "quote_ready"]
    assert len(sent) == 1, sent
    q = _db.quotes.find_one({"lead_id": lead["id"]}, sort=[("version", -1)])
    assert q["total"] == r["total"] and f"${q['total']:,}" in sent[0]["body"]


# R2: a dashboard-priced custom line removes the assumed placeholder package
def test_r2_custom_priced_removes_package(s, made):
    lead = new_lead(s, made)
    turn(s, lead, "I want to build a koi pond aquarium wall")
    o = turn(s, lead, "", wants_price=True)
    assert o["status"] == "ok" and o["total"] > 0
    items = s.get(f"{API}/itemizer/{lead['id']}/custom").json()["items"]
    assert items, "expected a To be priced by Apex line"
    r = s.post(f"{API}/itemizer/{lead['id']}/items/{items[0]['item_id']}/price",
               json={"label": "TEST_Koi wall", "tiers": [3000, 4000, 6000], "match": "zzkoiwalltest"})
    assert r.status_code == 200, r.text
    q = _db.quotes.find_one({"lead_id": lead["id"]}, sort=[("version", -1)])
    lb = [i["label"] for i in q["line_items"]]
    assert "TEST_Koi wall" in lb and PKG not in lb, lb
