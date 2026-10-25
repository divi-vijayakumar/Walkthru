import uuid
from core.db import db, iso
from core.status import touch
from pricing.engine import DEPOSIT_PCT

PUBLIC_FIELDS = {"_id": 0, "margin_pct": 0, "low": 0, "high": 0, "range_pct": 0}


async def latest_quote(lead_id: str, active_only: bool = True, internal: bool = False):
    query = {"lead_id": lead_id}
    if active_only:
        query["status"] = {"$ne": "recalled"}
    proj = {"_id": 0} if internal else PUBLIC_FIELDS
    return await db.quotes.find_one(query, proj, sort=[("version", -1)])


async def save_quote(lead: dict, items: list, total: int, status: str, extra: dict = None) -> dict:
    prev = await db.quotes.find_one({"lead_id": lead["id"]}, {"_id": 0}, sort=[("version", -1)])
    prev_keys = {(i["key"], i["amount"]) for i in prev["line_items"]} if prev else set()
    for i in items:
        i["is_new"] = bool(prev) and (i["key"], i["amount"]) not in prev_keys
    quote = {
        "id": str(uuid.uuid4()), "lead_id": lead["id"], "version": (prev["version"] if prev else 0) + 1,
        "line_items": items, "total": total,
        "deposit_pct": DEPOSIT_PCT, "deposit_amount": int(round(total * DEPOSIT_PCT / 100.0)),
        "status": status, "created_at": iso(), **(extra or {}),
    }
    await db.quotes.insert_one(dict(quote))
    await touch(lead["id"], {"quote_total": total,
                             "quote_version": quote["version"], "quote_pending": False, "quote_pending_due_at": None})
    quote.pop("margin_pct", None)
    return quote
