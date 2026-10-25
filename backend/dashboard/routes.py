import os
import statistics
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from core.db import db, iso, get_contractor, CONTRACTOR_ID
from core.status import FLOW, ALL_STATUSES, set_status
from core.quotes import latest_quote
from core import flow
from core.seed import reset_seed
from auth.routes import require_user

router = APIRouter(prefix="/api", dependencies=[Depends(require_user)])
ORDER = {s: i for i, s in enumerate(ALL_STATUSES)}
Source = Literal["thumbtack", "handy", "angi", "website", "referral"]


class LeadCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=7, max_length=25)
    source: Source = "website"
    ask: str = Field(min_length=2, max_length=60)


class AgentToggle(BaseModel):
    agent_enabled: bool


def ts(value):
    return datetime.fromisoformat(value).timestamp() if value else 0


def time_to_quote(history):
    start = next((h["at"] for h in history if h["status"] == "walkthru_initiated"), None)
    if not start:
        return None
    done = next((h["at"] for h in history if h["status"] == "quote_generated" and ts(h["at"]) >= ts(start)), None)
    return ts(done) - ts(start) if done else None


@router.get("/dashboard")
async def dashboard():
    contractor = await get_contractor()
    leads = await db.leads.find({"contractor_id": CONTRACTOR_ID}, {"_id": 0}).to_list(1000)
    sessions = {s["lead_id"]: s async for s in db.call_sessions.find({"ended_at": None}, {"_id": 0, "transcript": 0})}
    quotes = {}
    async for q in db.quotes.find({"status": {"$ne": "recalled"}}, {"_id": 0, "margin_pct": 0}).sort("version", 1):
        quotes[q["lead_id"]] = q
    for lead in leads:
        lead["live"] = sessions.get(lead["id"]) if lead["status"] == "walkthru_initiated" else None
        q = quotes.get(lead["id"])
        lead["quote"] = {k: q.get(k) for k in ("version", "total", "low", "high", "status", "line_items")} if q else None
    leads.sort(key=lambda lead: (0 if lead["status"] == "walkthru_initiated" else 1, ORDER.get(lead["status"], 99),
                                 -ts(lead["last_activity_at"])))
    gaps = [g for g in (time_to_quote(lead["status_history"]) for lead in leads) if g is not None]
    return {
        "contractor": contractor, "leads": leads, "server_time": iso(),
        "counts": {s: sum(1 for lead in leads if lead["status"] == s) for s in ALL_STATUSES},
        "median_time_to_quote_s": statistics.median(gaps) if gaps else None,
    }


@router.patch("/contractor")
async def update_contractor(body: AgentToggle):
    await db.contractors.update_one({"id": CONTRACTOR_ID}, {"$set": {"agent_enabled": body.agent_enabled}})
    return await get_contractor()


@router.post("/leads")
async def create_lead(body: LeadCreate):
    lead, agent = await flow.create_lead(body.name, body.phone, body.source, body.ask)
    return {"lead": lead, "agent": agent}


@router.post("/leads/{lead_id}/start-agent")
async def start_agent(lead_id: str):
    return await flow.start_agent(await flow.get_lead(lead_id))


@router.post("/leads/{lead_id}/take-over")
async def take_over(lead_id: str):
    lead = await flow.get_lead(lead_id)
    await flow.take_over(lead)
    return {"escalated": True, "phone": lead["phone"], "name": lead["name"]}


@router.post("/leads/{lead_id}/recall-quote")
async def recall_quote(lead_id: str):
    await flow.recall_quote(await flow.get_lead(lead_id))
    return {"recalled": True}


@router.get("/leads/{lead_id}/transcript")
async def transcript(lead_id: str):
    await flow.get_lead(lead_id)
    sessions = await db.call_sessions.find({"lead_id": lead_id}, {"_id": 0}).sort("started_at", -1).to_list(20)
    return {"sessions": sessions}


# Demo helper endpoints used by /dev
@router.get("/dev/config")
async def dev_config():
    channel = os.environ.get("MESSAGE_CHANNEL", "sms")
    sender = "TWILIO_WHATSAPP_FROM" if channel == "whatsapp" else "TWILIO_FROM"
    twilio = all(os.environ.get(k) for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", sender))
    vapi = bool(os.environ.get("VAPI_PUBLIC_KEY") and os.environ.get("VAPI_ASSISTANT_ID"))
    allow = [x.strip() for x in os.environ.get("SMS_ALLOWLIST", "").split(",") if x.strip()]
    return {"voice_mode": "vapi" if os.environ.get("VOICE_MODE") == "vapi" and vapi else "mock",
            "twilio_configured": twilio, "allowlist_count": len(allow), "channel": channel,
            "simulate_mode": os.environ.get("SIMULATE_MODE", "none")}


@router.post("/dev/leads/{lead_id}/advance")
async def advance(lead_id: str):
    lead = await flow.get_lead(lead_id)
    if lead["status"] in ("deposit_received", "dropped"):
        raise HTTPException(400, "This lead is at the end of the journey")
    nxt = FLOW[FLOW.index(lead["status"]) + 1]
    result = {}
    if nxt == "invited":
        result = await flow.start_agent(lead)
    elif nxt == "walkthru_initiated":
        contractor = await get_contractor()
        await flow.start_call(lead)
        await flow.add_caption(lead, "assistant", f"Hi {flow.first_name(lead)}, I'm {contractor['agent_name']} from "
                                                  f"{contractor['name']}. Tell me about your {lead['ask'].lower()}.")
    elif nxt == "walkthru_completed":
        await flow.end_call(lead, auto_quote=False)
    elif nxt == "quote_generated":
        if not await latest_quote(lead_id):
            await flow.default_quote(lead)
        await db.quotes.update_many({"lead_id": lead_id, "status": "live"}, {"$set": {"status": "sent"}})
        result = {"sms": await flow.mark_quote_ready(await flow.get_lead(lead_id))}
    elif nxt == "contract_sent":
        await flow.open_contract(lead)
    elif nxt == "pending_deposit":
        result = await flow.sign_contract(lead, lead["name"])
        result.pop("payment", None)
    elif nxt == "deposit_received":
        await flow.pay_deposit(lead)
    lead = await flow.get_lead(lead_id)
    return {"lead_status": lead["status"], **result}


@router.post("/dev/leads/{lead_id}/drop")
async def drop(lead_id: str):
    lead = await flow.get_lead(lead_id)
    await db.call_sessions.update_many({"lead_id": lead_id, "ended_at": None}, {"$set": {"ended_at": iso()}})
    await set_status(lead["id"], "dropped")
    return {"lead_status": "dropped"}


@router.post("/dev/reset")
async def reset():
    await reset_seed()
    return {"reset": True}


SIM_NAME = {"$regex": "^\\s*dhivya\\s+vijayakumar\\s*$", "$options": "i"}
LEAD_DATA = ("call_sessions", "quotes", "pricing_states", "contracts", "payments", "payment_transactions", "followups",
             "sms_log", "itemizer_sessions", "itemizer_goals", "media")


@router.post("/dev/simulate-dhivya")
async def simulate_dhivya():
    """Wipe Dhivya's lead and everything tied to it, then re-add her so the walkthrough starts fresh."""
    lead = await db.leads.find_one({"name": SIM_NAME}, {"_id": 0}, sort=[("created_at", -1)])
    if lead:
        tpl = {k: lead[k] for k in ("name", "phone", "source", "ask")}
        await db.meta.update_one({"_id": "simulate_lead"}, {"$set": tpl}, upsert=True)
    else:
        tpl = await db.meta.find_one({"_id": "simulate_lead"}, {"_id": 0})
        if not tpl:
            raise HTTPException(404, "Dhivya's lead isn't in the system")
    ids = [d["id"] async for d in db.leads.find({"name": SIM_NAME}, {"id": 1})]
    sessions = [d["id"] async for d in db.call_sessions.find({"lead_id": {"$in": ids}}, {"id": 1})]
    goals = [d["goal_id"] async for d in db.percia_goals.find({"session_id": {"$in": sessions}}, {"goal_id": 1})]
    for coll in LEAD_DATA:
        await db[coll].delete_many({"lead_id": {"$in": ids}})
    await db.percia_goals.delete_many({"goal_id": {"$in": goals}})
    await db.percia_frames.delete_many({"goal_id": {"$in": goals}})
    await db.leads.delete_many({"id": {"$in": ids}})
    new, agent = await flow.create_lead(tpl["name"], tpl["phone"], tpl["source"], tpl["ask"])
    return {"lead": new, "agent": agent, "removed": len(ids)}
