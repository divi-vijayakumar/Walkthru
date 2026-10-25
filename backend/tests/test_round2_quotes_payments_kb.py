# Round 2: Quotes list/detail/PDF, portal quote PDF, Payments list + offline record, KB edits, company settings
import os
import copy
import pytest
import requests
import fitz
from conftest import _db

BASE = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0]
API = BASE.rstrip("/") + "/api"
TEST_PHONE = "(408) 555-0199"
LEAD_COLLS = ("call_sessions", "quotes", "pricing_states", "contracts", "payments", "payment_transactions", "followups",
              "sms_log", "itemizer_sessions", "itemizer_goals", "itemizer_insights", "media")


def pdf_text(content):
    with fitz.open(stream=content, filetype="pdf") as d:
        return "\n".join(pg.get_text() for pg in d)


@pytest.fixture(scope="module")
def s(owner_token):
    x = requests.Session()
    x.headers["Authorization"] = f"Bearer {owner_token}"
    return x


@pytest.fixture(scope="module")
def made(s):
    ids = []
    yield ids
    leads = [d["id"] for d in _db.leads.find({"name": {"$regex": "^TEST_"}}, {"id": 1})]
    for c in LEAD_COLLS:
        _db[c].delete_many({"lead_id": {"$in": leads}})
    _db.leads.delete_many({"id": {"$in": leads}})


def new_lead(s, made, name, ask="Bathroom remodel"):
    r = s.post(f"{API}/leads", json={"name": name, "phone": TEST_PHONE, "source": "website", "ask": ask})
    assert r.status_code == 200, r.text
    lead = r.json()["lead"]
    made.append(lead["id"])
    return lead


def advance_to(s, lead_id, target):
    for _ in range(10):
        st = _db.leads.find_one({"id": lead_id})["status"]
        if st == target:
            return
        r = s.post(f"{API}/dev/leads/{lead_id}/advance")
        assert r.status_code == 200, r.text
    raise AssertionError(f"never reached {target}")


# ---------- Quotes ----------
class TestQuotes:
    def test_quotes_requires_auth(self):
        assert requests.get(f"{API}/quotes").status_code == 401
        assert requests.get(f"{API}/quotes/quote-lead-tom/pdf").status_code == 401

    def test_quotes_list_shape(self, s):
        r = s.get(f"{API}/quotes")
        assert r.status_code == 200
        d = r.json()
        assert {"open", "accepted", "count"} <= set(d["totals"])
        assert d["quotes"], "no quotes"
        q = d["quotes"][0]
        for k in ("id", "lead_name", "version", "status", "total", "low", "high", "latest", "sample"):
            assert k in q
        cur = [x for x in d["quotes"] if x["latest"] and x["status"] != "recalled"]
        assert d["totals"]["count"] == len(cur)
        assert d["totals"]["open"] == sum(x["total"] for x in cur if x["status"] in ("live", "sent"))
        assert d["totals"]["accepted"] == sum(x["total"] for x in cur if x["status"] == "accepted")

    def test_quote_detail(self, s):
        r = s.get(f"{API}/quotes/quote-lead-tom")
        assert r.status_code == 200
        d = r.json()
        assert d["lead"]["name"] == "Tom Becker"
        assert isinstance(d["line_items"], list) and d["line_items"]
        assert d["versions"] and d["versions"][0]["id"]
        assert "_id" not in d

    def test_quote_unknown_404(self, s):
        assert s.get(f"{API}/quotes/nope-xyz").status_code == 404
        assert s.get(f"{API}/quotes/nope-xyz/pdf").status_code == 404

    def test_quote_pdf_content(self, s):
        q = s.get(f"{API}/quotes/quote-lead-ana").json()
        r = s.get(f"{API}/quotes/quote-lead-ana/pdf")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        cd = r.headers.get("content-disposition", "")
        assert cd.startswith("attachment") and ".pdf" in cd
        assert r.content[:4] == b"%PDF"
        t = pdf_text(r.content)
        contractor = s.get(f"{API}/dashboard").json()["contractor"]
        assert contractor["name"] in t
        assert contractor["phone"] in t
        assert f"Quote, version {q['version']}" in t
        assert "Ana Pereira" in t and q["lead"]["ask"] in t
        for i in q["line_items"]:
            assert i["label"][:25] in t.replace("\n", " ")
        assert "Estimated total" in t and "Likely range" in t
        assert f"Deposit after signing ({q['deposit_pct']}%)" in t
        assert f"${round(q['total']):,}" in t
        for a in q.get("assumptions") or []:
            assert a[:20] in t.replace("\n", " ")


# ---------- Portal PDF ----------
class TestPortalPdf:
    def test_invalid_token_404(self):
        assert requests.get(f"{API}/portal/bad-token-xyz/quote.pdf").status_code == 404

    def test_portal_pdf_latest(self, s):
        leads = s.get(f"{API}/dashboard").json()["leads"]
        tom = next(x for x in leads if x["id"] == "lead-tom")
        r = requests.get(f"{API}/portal/{tom['portal_token']}/quote.pdf")
        assert r.status_code == 200 and r.content[:4] == b"%PDF"
        assert "attachment" in r.headers.get("content-disposition", "")
        assert "Tom Becker" in pdf_text(r.content)

    def test_portal_no_quote_404_and_recalled(self, s, made):
        lead = new_lead(s, made, "TEST_R2 NoQuote")
        advance_to(s, lead["id"], "invited")
        tok = _db.leads.find_one({"id": lead["id"]})["portal_token"]
        assert tok
        assert requests.get(f"{API}/portal/{tok}/quote.pdf").status_code == 404
        advance_to(s, lead["id"], "quote_generated")
        r = requests.get(f"{API}/portal/{tok}/quote.pdf")
        assert r.status_code == 200 and "TEST_R2 NoQuote" in pdf_text(r.content)
        # recall -> portal 404, dashboard PDF shows recalled notice
        assert s.post(f"{API}/leads/{lead['id']}/recall-quote").status_code == 200
        assert requests.get(f"{API}/portal/{tok}/quote.pdf").status_code == 404
        qid = _db.quotes.find_one({"lead_id": lead["id"]})["id"]
        t = pdf_text(s.get(f"{API}/quotes/{qid}/pdf").content)
        assert "recalled" in t.lower()
        rows = s.get(f"{API}/quotes").json()["quotes"]
        row = next(x for x in rows if x["id"] == qid)
        assert row["status"] == "recalled" and row["sample"] is False


# ---------- Company settings ----------
class TestCompanySettings:
    def test_settings_validation_and_pdf(self, s):
        orig = s.get(f"{API}/dashboard").json()["contractor"]
        keys = ("name", "agent_name", "phone", "email", "address", "min_margin_pct", "max_discount_pct")
        raw = _db.contractors.find_one({}, {"_id": 0})
        absent = [k for k in keys if k not in raw]
        body = {k: orig.get(k) if orig.get(k) is not None else "" for k in keys}
        try:
            assert s.put(f"{API}/contractor/settings", json={**body, "min_margin_pct": 61}).status_code == 422
            assert s.put(f"{API}/contractor/settings", json={**body, "max_discount_pct": 31}).status_code == 422
            r = s.put(f"{API}/contractor/settings", json={**body, "email": "TEST_quotes@apex.test", "address": "TEST 1 Main St"})
            assert r.status_code == 200 and r.json()["email"] == "TEST_quotes@apex.test"
            t = pdf_text(s.get(f"{API}/quotes/quote-lead-tom/pdf").content)
            assert "TEST_quotes@apex.test" in t and "TEST 1 Main St" in t
        finally:
            _db.contractors.update_one({"id": orig["id"]}, {"$set": {k: orig.get(k) for k in keys}}) if orig.get("id") else \
                s.put(f"{API}/contractor/settings", json=body)
            if absent:
                _db.contractors.update_one({}, {"$unset": {k: "" for k in absent}})
            now = s.get(f"{API}/dashboard").json()["contractor"]
            assert all(now.get(k) == orig.get(k) for k in keys)


# ---------- Payments ----------
class TestPayments:
    def test_payments_requires_auth(self):
        assert requests.get(f"{API}/payments").status_code == 401

    def test_payments_shape(self, s):
        d = s.get(f"{API}/payments").json()
        assert {"due", "paid", "paid_30d", "due_count", "paid_count"} <= set(d["totals"])
        for p in d["payments"]:
            assert p["status"] in ("pending", "paid", "void")
            assert {"method", "amount", "can_record"} <= set(p)
        assert d["totals"]["due"] == sum(p["amount"] for p in d["payments"] if p["status"] == "pending")

    def test_record_offline_flow(self, s, made):
        lead = new_lead(s, made, "TEST_R2 Payer")
        advance_to(s, lead["id"], "pending_deposit")
        before = s.get(f"{API}/payments").json()
        row = next(p for p in before["payments"] if p["lead_id"] == lead["id"])
        assert row["status"] == "pending" and row["can_record"] is True
        assert s.post(f"{API}/payments/{row['id']}/record", json={"method": "bitcoin"}).status_code == 422
        assert s.post(f"{API}/payments/nope/record", json={"method": "cash"}).status_code == 404
        r = s.post(f"{API}/payments/{row['id']}/record", json={"method": "check", "reference": "  TEST_1042 "})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "paid" and r.json()["method"] == "check" and r.json()["reference"] == "TEST_1042"
        assert _db.leads.find_one({"id": lead["id"]})["status"] == "deposit_received"
        after = s.get(f"{API}/payments").json()
        row2 = next(p for p in after["payments"] if p["id"] == row["id"])
        assert row2["status"] == "paid" and row2["can_record"] is False and row2["paid_at"]
        assert after["totals"]["paid"] == pytest.approx(before["totals"]["paid"] + row["amount"])
        assert after["totals"]["due"] == pytest.approx(before["totals"]["due"] - row["amount"])
        assert s.post(f"{API}/payments/{row['id']}/record", json={"method": "cash"}).status_code == 400


# ---------- KB ----------
class TestKb:
    def test_kb_task_edit_restore(self, s):
        kb = s.get(f"{API}/kb").json()
        assert kb["tasks"] and kb["facts"] and kb["rules"]
        t = next(x for x in kb["tasks"] if any("amount" in p and p.get("amount") is not None for p in x["price"]))
        orig = copy.deepcopy(t)
        try:
            new = copy.deepcopy(t)
            new["label"] = "TEST_ label"
            idx = next(i for i, p in enumerate(new["price"]) if p.get("amount") is not None)
            new["price"][idx]["amount"] = 1234
            r = s.put(f"{API}/kb/tasks/{t['task_id']}", json=new)
            assert r.status_code == 200, r.text
            got = next(x for x in s.get(f"{API}/kb").json()["tasks"] if x["task_id"] == t["task_id"])
            assert got["label"] == "TEST_ label" and got["price"][idx]["amount"] == 1234
            bad = copy.deepcopy(new)
            bad["price"][idx]["amount"] = -5
            assert s.put(f"{API}/kb/tasks/{t['task_id']}", json=bad).status_code == 422
            assert s.put(f"{API}/kb/tasks/other-id", json=new).status_code == 422
        finally:
            assert s.put(f"{API}/kb/tasks/{t['task_id']}", json=orig).status_code == 200
        got = next(x for x in s.get(f"{API}/kb").json()["tasks"] if x["task_id"] == t["task_id"])
        assert got == orig

    def test_kb_fact_and_rule_edit_restore(self, s):
        kb = s.get(f"{API}/kb").json()
        f = kb["facts"][0]
        rule = next(x for x in kb["rules"] if x.get("kind") == "rule")
        of, orl = copy.deepcopy(f), copy.deepcopy(rule)
        try:
            assert s.put(f"{API}/kb/facts/{f['fact_id']}", json={**f, "question": "TEST_ q?", "priority": 1}).status_code == 200
            assert s.put(f"{API}/kb/facts/{f['fact_id']}", json={**f, "priority": 5}).status_code == 422
            assert s.put(f"{API}/kb/rules/{rule['rule_id']}", json={**rule, "note": "TEST_ note"}).status_code == 200
            kb2 = s.get(f"{API}/kb").json()
            assert next(x for x in kb2["facts"] if x["fact_id"] == f["fact_id"])["question"] == "TEST_ q?"
            assert next(x for x in kb2["rules"] if x["rule_id"] == rule["rule_id"])["note"] == "TEST_ note"
        finally:
            s.put(f"{API}/kb/facts/{f['fact_id']}", json=of)
            s.put(f"{API}/kb/rules/{rule['rule_id']}", json=orl)
        kb3 = s.get(f"{API}/kb").json()
        assert next(x for x in kb3["facts"] if x["fact_id"] == f["fact_id"]) == of
        assert next(x for x in kb3["rules"] if x["rule_id"] == rule["rule_id"]) == orl
