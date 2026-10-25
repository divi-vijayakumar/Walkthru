import os
from typing import List, Literal, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from core.db import db, iso, get_contractor
from core.quotes import latest_quote
from core import flow
from vapi.routes import read_message, run_tool_calls, parse_transcript
from itemizer.engine import claim_insights

router = APIRouter(prefix="/api/portal")


class Caption(BaseModel):
    role: Literal["assistant", "user"]
    text: str = Field(min_length=1, max_length=2000)


class Camera(BaseModel):
    on: bool


class TranscriptLine(BaseModel):
    role: str
    text: str


class EndCall(BaseModel):
    transcript: Optional[List[TranscriptLine]] = None


class Signature(BaseModel):
    name: str = Field(max_length=120)


def voice_config():
    pk, aid = os.environ.get("VAPI_PUBLIC_KEY"), os.environ.get("VAPI_ASSISTANT_ID")
    if os.environ.get("VOICE_MODE") == "vapi" and pk and aid:
        return {"mode": "vapi", "public_key": pk, "assistant_id": aid}
    return {"mode": "mock"}


@router.get("/{token}")
async def portal(token: str, live: bool = False):
    lead = await flow.lead_by_token(token)
    contractor = await get_contractor()
    active = {"lead_id": lead["id"], "void": {"$ne": True}}
    session = await flow.active_session(lead["id"])
    return {
        "lead": {"name": lead["name"], "first_name": flow.first_name(lead), "ask": lead["ask"], "phone": lead["phone"],
                 "status": lead["status"], "quote_pending": lead.get("quote_pending", False),
                 "escalated": lead.get("escalated", False)},
        "contractor": {"name": contractor["name"], "agent_name": contractor["agent_name"], "phone": contractor["phone"]},
        "quote": await latest_quote(lead["id"]),
        "contract": await db.contracts.find_one(active, {"_id": 0}, sort=[("created_at", -1)]),
        "payment": await db.payments.find_one(active, {"_id": 0}, sort=[("created_at", -1)]),
        "session": session,
        "insights": await claim_insights(lead["id"]) if live and session else [],
        "voice": voice_config(),
        "payments_test_mode": os.environ.get("STRIPE_MODE") == "test",
    }


@router.post("/{token}/call/start")
async def call_start(token: str):
    return await flow.start_call(await flow.lead_by_token(token))


@router.post("/{token}/call/caption")
async def call_caption(token: str, body: Caption):
    await flow.add_caption(await flow.lead_by_token(token), body.role, body.text)
    return {"ok": True}


@router.post("/{token}/call/camera")
async def call_camera(token: str, body: Camera):
    lead = await flow.lead_by_token(token)
    await db.call_sessions.update_one({"lead_id": lead["id"], "ended_at": None}, {"$set": {"camera_on": body.on}})
    return {"camera_on": body.on}


@router.post("/{token}/agent/tools")
async def agent_tools(token: str, request: Request):
    """Tool calls from the in-browser scripted agent; scoped to this portal link's lead only."""
    lead = await flow.lead_by_token(token)
    return {"results": await run_tool_calls(await read_message(request), lead)}


@router.post("/{token}/agent/end")
async def agent_end(token: str, request: Request):
    msg = await read_message(request)
    return await flow.end_call(await flow.lead_by_token(token), parse_transcript(msg)[:400])


@router.post("/{token}/call/end")
async def call_end(token: str, body: EndCall):
    transcript = [t.model_dump() for t in body.transcript] if body.transcript else None
    return await flow.end_call(await flow.lead_by_token(token), transcript)


@router.post("/{token}/contract/open")
async def contract_open(token: str):
    return await flow.open_contract(await flow.lead_by_token(token))


@router.post("/{token}/contract/sign")
async def contract_sign(token: str, body: Signature):
    result = await flow.sign_contract(await flow.lead_by_token(token), body.name)
    return {"payment": result["payment"]}

