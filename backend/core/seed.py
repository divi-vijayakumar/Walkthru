import logging
from datetime import timedelta
from core.db import db, iso, now, portal_link, CONTRACTOR_ID
from core.status import FLOW
from pricing.engine import new_state, price, margin_pct, drivers, r500, DEPOSIT_PCT

logger = logging.getLogger("seed")
SEED_VERSION = 4
COLLECTIONS = ["contractors", "leads", "call_sessions", "quotes", "contracts", "payments", "pricing_states",
               "followups", "frames", "sms_log", "scopes", "messages"]

# name, phone, source, ask, status, seconds-ago per step, quote spec
LEADS = [
    ("Maya Rios", "(408) 555-0142", "thumbtack", "Bathroom remodel", "walkthru_initiated", [380, 260, 134], "maya"),
    ("Dana Kim", "(669) 555-0187", "handy", "Kitchen remodel", "new", [180], None),
    ("Luis Ortega", "(408) 555-0119", "angi", "Bathroom remodel", "invited", [2700, 2580], None),
    ("Priya Shah", "(650) 555-0163", "website", "Bathroom remodel", "walkthru_completed", [5400, 5200, 1100, 420], None),
    ("Tom Becker", "(408) 555-0155", "thumbtack", "Deck repair", "quote_generated", [18000, 17700, 17000, 16700, 16620], "deck"),
    ("Elena Vogt", "(669) 555-0128", "referral", "Bathroom remodel", "quote_generated", [30000, 29800, 28000, 27700, 27600], "elena"),
    ("Marcus Lee", "(408) 555-0174", "thumbtack", "Bathroom remodel", "contract_sent", [45000, 44800, 43000, 42700, 42580, 40000], "marcus"),
    ("Ana Pereira", "(650) 555-0191", "angi", "Kitchen remodel", "pending_deposit", [60000, 59800, 58000, 57700, 57640, 55000, 54000], "ana"),
    ("Chris Nolan", "(408) 555-0136", "handy", "Bathroom remodel", "deposit_received", [80000, 79800, 78000, 77600, 77545, 76000, 75000, 70000], "chris"),
]

BATH_SPECS = {
    "maya": ("medium", "standard", ["walk-in shower", "double vanity"]),
    "marcus": ("medium", "standard", ["walk-in shower", "double vanity"]),
    "chris": ("small", "refresh", ["double vanity"]),
    "elena": ("medium", "refresh", ["frameless glass door"]),
}
CUSTOM_ITEMS = {
    "deck": [("Replace damaged deck boards", 3900), ("Reinforce joists", 1750), ("Clean and stain", 1200)],
    "ana": [("Mid-range kitchen package", 31500), ("Quartz countertops", 4800), ("Under-cabinet lighting", 2600)],
}
SAMPLE_TRANSCRIPT = [
    ("assistant", "Hi {first}, I'm Alex, the estimator for Apex Remodeling. Tell me about your {ask}."),
    ("user", "We want to update the whole space and fix a few things that have worn out."),
    ("assistant", "Thanks, that gives me what I need to price it. Your quote will be ready in a moment."),
]


def ago(seconds):
    return iso(now() - timedelta(seconds=seconds))


def build_quote(lead_id, spec, at, status):
    st, extra = None, {}
    if spec in BATH_SPECS:
        size, finish, changes = BATH_SPECS[spec]
        st, _ = new_state({"project_type": "bathroom_remodel", "room_size": size, "finish_level": finish,
                           "requested_changes": changes})
        items, total = price(st)
        extra = {"margin_pct": margin_pct(st, total), "drivers": drivers(st)}
    else:
        items = [{"key": f"item{i}", "label": label, "amount": amt} for i, (label, amt) in enumerate(CUSTOM_ITEMS[spec])]
        total = sum(i["amount"] for i in items)
    for i in items:
        i["is_new"] = False
    quote = {"id": f"quote-{lead_id}", "lead_id": lead_id, "version": 1, "line_items": items, "total": total,
             "low": r500(total * 0.9), "high": r500(total * 1.1), "deposit_pct": DEPOSIT_PCT,
             "deposit_amount": int(round(total * DEPOSIT_PCT / 100.0)), "status": status, "created_at": at, **extra}
    return quote, st


async def insert_lead(row):
    name, phone, source, ask, status, steps, spec = row
    first = name.split()[0]
    lead_id = f"lead-{first.lower()}"
    token = f"demo-{first.lower()}"
    history = [{"status": FLOW[i], "at": ago(s)} for i, s in enumerate(steps)]
    lead = {"id": lead_id, "contractor_id": CONTRACTOR_ID, "name": name, "phone": phone, "source": source, "ask": ask,
            "status": status, "status_history": history, "portal_token": token,
            "portal_link": portal_link(token) if status != "new" else None,
            "quote_total": None, "quote_low": None, "quote_high": None, "quote_version": None,
            "escalated": False, "quote_pending": False, "quote_pending_due_at": None, "followup_queued": False,
            "created_at": history[0]["at"], "last_activity_at": history[-1]["at"]}
    idx = FLOW.index(status)
    if status == "walkthru_completed":
        lead.update(quote_pending=True, quote_pending_due_at=iso(now() - timedelta(seconds=steps[3]) + timedelta(minutes=15)))
    if spec:
        q_status = "live" if status == "walkthru_initiated" else ("accepted" if idx >= 5 else "sent")
        q_at = ago(60) if status == "walkthru_initiated" else history[4]["at"]
        quote, st = build_quote(lead_id, spec, q_at, q_status)
        await db.quotes.insert_one(quote)
        if st:
            await db.pricing_states.insert_one({"lead_id": lead_id, "state": st})
        lead.update(quote_total=quote["total"], quote_low=quote["low"], quote_high=quote["high"], quote_version=1)
        if idx >= 5:
            signed = history[6]["at"] if idx >= 6 else None
            await db.contracts.insert_one({"id": f"contract-{lead_id}", "lead_id": lead_id, "quote_version": 1,
                                           "signed_name": name if signed else None, "signed_at": signed,
                                           "void": False, "created_at": history[5]["at"]})
        if idx >= 6:
            await db.payments.insert_one({"id": f"pay-{lead_id}", "lead_id": lead_id, "amount": quote["deposit_amount"],
                                          "link": portal_link(token), "status": "paid" if idx == 7 else "pending",
                                          "void": False, "created_at": history[6]["at"],
                                          "paid_at": history[7]["at"] if idx == 7 else None})
    transcript = [{"role": r, "text": t.format(first=first, ask=ask.lower()), "at": history[min(2, len(history) - 1)]["at"]}
                  for r, t in SAMPLE_TRANSCRIPT]
    if status == "walkthru_initiated":
        live = "...a walk-in shower instead of the tub, and I'd love a double vanity if it fits."
        await db.call_sessions.insert_one({
            "id": f"session-{lead_id}", "lead_id": lead_id, "started_at": history[2]["at"], "ended_at": None,
            "transcript": transcript[:1] + [{"role": "user", "text": live, "at": ago(20)}],
            "live_caption": live, "live_role": "user", "camera_on": False, "chips": []})
    elif idx >= 3:
        await db.call_sessions.insert_one({
            "id": f"session-{lead_id}", "lead_id": lead_id, "started_at": history[2]["at"], "ended_at": history[3]["at"],
            "transcript": transcript, "live_caption": "", "live_role": "", "camera_on": False, "chips": []})
    await db.leads.insert_one(lead)


async def reset_seed():
    for c in COLLECTIONS:
        await db[c].delete_many({})
    await db.contractors.insert_one({"id": CONTRACTOR_ID, "name": "Apex Remodeling", "agent_name": "Alex",
                                     "phone": "(408) 555-0100", "agent_enabled": True,
                                     "min_margin_pct": 18, "max_discount_pct": 6})
    for row in LEADS:
        await insert_lead(row)
    await db.meta.update_one({"_id": "seed"}, {"$set": {"version": SEED_VERSION, "at": iso()}}, upsert=True)
    logger.info("Sample data seeded")


async def seed():
    meta = await db.meta.find_one({"_id": "seed"})
    if not meta or meta.get("version") != SEED_VERSION:
        await reset_seed()
