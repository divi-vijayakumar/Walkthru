import uuid
import secrets
from datetime import timedelta
from fastapi import HTTPException
from core.db import db, iso, now, portal_link, get_contractor, CONTRACTOR_ID
from core.status import set_status, touch
from core.sms import send_sms
from core.quotes import latest_quote, save_quote
from pricing.engine import new_state, price, margin_pct, drivers


def first_name(lead):
    return lead["name"].split()[0]


async def get_lead(lead_id: str) -> dict:
    lead = await db.leads.find_one({"id": lead_id, "contractor_id": CONTRACTOR_ID}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "Lead not found")
    return lead


async def lead_by_token(token: str) -> dict:
    lead = await db.leads.find_one({"portal_token": token}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "This link is not valid")
    return lead


async def active_session(lead_id: str, with_transcript: bool = False):
    proj = {"_id": 0} if with_transcript else {"_id": 0, "transcript": 0}
    return await db.call_sessions.find_one({"lead_id": lead_id, "ended_at": None}, proj, sort=[("started_at", -1)])


async def create_lead(name, phone, source, ask):
    contractor = await get_contractor()
    at = iso()
    lead = {
        "id": str(uuid.uuid4()), "contractor_id": CONTRACTOR_ID, "name": name.strip(), "phone": phone.strip(),
        "source": source, "ask": ask.strip(), "status": "new", "status_history": [{"status": "new", "at": at}],
        "portal_token": None, "portal_link": None, "quote_total": None, "quote_low": None, "quote_high": None,
        "quote_version": None, "escalated": False, "quote_pending": False, "quote_pending_due_at": None,
        "followup_queued": False, "created_at": at, "last_activity_at": at,
    }
    await db.leads.insert_one(dict(lead))
    agent = await start_agent(lead) if contractor.get("agent_enabled") else None
    return await get_lead(lead["id"]), agent


async def start_agent(lead):
    contractor = await get_contractor()
    token = lead.get("portal_token") or secrets.token_urlsafe(8)
    link = portal_link(token)
    if lead["status"] == "new":
        await set_status(lead["id"], "invited", {"portal_token": token, "portal_link": link})
    elif lead["status"] == "invited":
        await touch(lead["id"], {"portal_token": token, "portal_link": link})
    else:
        raise HTTPException(400, "The agent is already running for this lead")
    body = (f"Hi {first_name(lead)}, this is {contractor['name']}. We'd love to learn about your {lead['ask'].lower()}. "
            f"Tap to start a quick video call with our estimator and get a quote in minutes: {link}. Reply STOP to opt out.")
    sms = await send_sms(lead, body, "invite")
    return {"status": "invited", "link": link, "sms": sms}


async def start_call(lead):
    if lead["status"] in ("contract_sent", "pending_deposit", "deposit_received", "dropped"):
        raise HTTPException(400, "This project is past the walkthrough stage")
    await db.call_sessions.update_many({"lead_id": lead["id"], "ended_at": None}, {"$set": {"ended_at": iso()}})
    session = {"id": str(uuid.uuid4()), "lead_id": lead["id"], "started_at": iso(), "ended_at": None,
               "transcript": [], "live_caption": "", "live_role": "", "camera_on": False, "chips": []}
    await db.call_sessions.insert_one(dict(session))
    await set_status(lead["id"], "walkthru_initiated",
                     {"followup_queued": False, "quote_pending": False, "quote_pending_due_at": None})
    session.pop("transcript")
    return session


async def add_caption(lead, role, text):
    line = {"role": role, "text": text, "at": iso()}
    await db.call_sessions.update_one(
        {"lead_id": lead["id"], "ended_at": None},
        {"$push": {"transcript": line}, "$set": {"live_caption": text, "live_role": role}})


async def mark_quote_ready(lead):
    contractor = await get_contractor()
    await set_status(lead["id"], "quote_generated", {"quote_pending": False, "quote_pending_due_at": None})
    return await send_sms(lead, f"Your {contractor['name']} quote is ready: {portal_link(lead['portal_token'])}", "quote_ready")


async def end_call(lead, transcript=None, auto_quote=True):
    session = await active_session(lead["id"], with_transcript=True)
    if not session and lead["status"] != "walkthru_initiated":
        return {"ended": False}
    if session:
        upd = {"ended_at": iso(), "live_caption": "", "camera_on": False}
        if transcript and not session.get("transcript"):
            upd["transcript"] = transcript
        await db.call_sessions.update_one({"id": session["id"]}, {"$set": upd})
    await set_status(lead["id"], "walkthru_completed")
    lead = await get_lead(lead["id"])
    quote = await latest_quote(lead["id"])
    if quote and auto_quote:
        await db.quotes.update_many({"lead_id": lead["id"], "status": "live"}, {"$set": {"status": "sent"}})
        await mark_quote_ready(lead)
    elif not quote and not lead.get("followup_queued"):
        await touch(lead["id"], {"quote_pending": True, "quote_pending_due_at": iso(now() + timedelta(minutes=15))})
    return {"ended": True}


async def default_quote(lead):
    if "bath" in lead["ask"].lower():
        st, _ = new_state({"project_type": "bathroom_remodel", "room_size": "medium", "finish_level": "standard"})
        await db.pricing_states.update_one({"lead_id": lead["id"]}, {"$set": {"state": st}}, upsert=True)
        items, total = price(st)
        return await save_quote(lead, items, total, "sent", {"margin_pct": margin_pct(st, total), "drivers": drivers(st)})
    items = [{"key": "base", "label": f"{lead['ask']} estimate", "amount": 8500}]
    return await save_quote(lead, items, 8500, "sent")


async def open_contract(lead):
    if lead["status"] == "contract_sent":
        return await db.contracts.find_one({"lead_id": lead["id"], "void": {"$ne": True}}, {"_id": 0}, sort=[("created_at", -1)])
    if lead["status"] != "quote_generated":
        raise HTTPException(400, "There is no quote ready to accept")
    quote = await latest_quote(lead["id"])
    if not quote:
        raise HTTPException(400, "There is no quote ready to accept")
    await db.quotes.update_one({"id": quote["id"]}, {"$set": {"status": "accepted"}})
    contract = {"id": str(uuid.uuid4()), "lead_id": lead["id"], "quote_version": quote["version"],
                "signed_name": None, "signed_at": None, "void": False, "created_at": iso()}
    await db.contracts.insert_one(dict(contract))
    await set_status(lead["id"], "contract_sent")
    return contract


async def sign_contract(lead, name):
    name = (name or "").strip()
    if len(name) < 2:
        raise HTTPException(422, "Type your full name to sign")
    if lead["status"] != "contract_sent":
        raise HTTPException(400, "The contract is not ready to sign")
    contractor = await get_contractor()
    quote = await latest_quote(lead["id"])
    await db.contracts.update_one({"lead_id": lead["id"], "signed_at": None, "void": {"$ne": True}},
                                  {"$set": {"signed_name": name, "signed_at": iso()}})
    link = portal_link(lead["portal_token"])
    payment = {"id": str(uuid.uuid4()), "lead_id": lead["id"], "amount": quote["deposit_amount"], "link": link,
               "status": "pending", "void": False, "created_at": iso()}
    await db.payments.insert_one(dict(payment))
    await set_status(lead["id"], "pending_deposit")
    sms = await send_sms(lead, f"Thanks for signing, {first_name(lead)}. Pay your {quote['deposit_pct']}% deposit of "
                               f"${quote['deposit_amount']:,} to {contractor['name']} here: {link}", "deposit_link")
    return {"payment": payment, "sms": sms}


async def pay_deposit(lead):
    if lead["status"] != "pending_deposit":
        raise HTTPException(400, "No deposit is due")
    await db.payments.update_one({"lead_id": lead["id"], "status": "pending", "void": {"$ne": True}},
                                 {"$set": {"status": "paid", "paid_at": iso(), "method": "simulated"}})
    await set_status(lead["id"], "deposit_received")
    return await db.payments.find_one({"lead_id": lead["id"], "status": "paid"}, {"_id": 0}, sort=[("paid_at", -1)])


async def recall_quote(lead):
    if lead["status"] == "deposit_received":
        raise HTTPException(400, "The deposit is already paid, so this quote can't be recalled")
    if not await latest_quote(lead["id"]):
        raise HTTPException(400, "This lead has no quote to recall")
    await db.quotes.update_many({"lead_id": lead["id"]}, {"$set": {"status": "recalled"}})
    await db.contracts.update_many({"lead_id": lead["id"]}, {"$set": {"void": True}})
    await db.payments.update_many({"lead_id": lead["id"], "status": "pending"}, {"$set": {"void": True, "status": "void"}})
    await set_status(lead["id"], "walkthru_completed", {
        "quote_total": None, "quote_low": None, "quote_high": None, "quote_version": None,
        "quote_pending": True, "quote_pending_due_at": iso(now() + timedelta(minutes=15))})


async def take_over(lead):
    await touch(lead["id"], {"escalated": True, "escalated_at": iso()})
    await db.call_sessions.update_one({"lead_id": lead["id"], "ended_at": None}, {"$push": {"transcript": {
        "role": "system", "text": "Contractor took over the call.", "at": iso()}}})
