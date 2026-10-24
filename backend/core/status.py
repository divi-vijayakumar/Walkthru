from core.db import db, iso

FLOW = [
    "new", "invited", "walkthru_initiated", "walkthru_completed",
    "quote_generated", "contract_sent", "pending_deposit", "deposit_received",
]
ALL_STATUSES = FLOW + ["dropped"]


async def set_status(lead_id: str, status: str, extra: dict = None):
    """The only way a lead's status changes."""
    if status not in ALL_STATUSES:
        raise ValueError(f"Unknown status {status}")
    at = iso()
    await db.leads.update_one(
        {"id": lead_id},
        {"$set": {"status": status, "last_activity_at": at, **(extra or {})},
         "$push": {"status_history": {"status": status, "at": at}}},
    )


async def touch(lead_id: str, fields: dict):
    await db.leads.update_one({"id": lead_id}, {"$set": {**fields, "last_activity_at": iso()}})
