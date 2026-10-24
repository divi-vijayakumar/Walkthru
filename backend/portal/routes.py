import os
from typing import List, Literal, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from core.db import db, iso, get_contractor
from core.quotes import latest_quote
from core import flow

router = APIRouter(prefix="/api/portal")


class Caption(BaseModel):
    role: Literal["assistant", "user"]
    text: str = Field(min_length=1, max_length=2000)


class Camera(BaseModel):
    on: bool


class Frame(BaseModel):
    image: str = Field(max_length=1_500_000)


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
async def portal(token: str):
    lead = await flow.lead_by_token(token)
    contractor = await get_contractor()
    active = {"lead_id": lead["id"], "void": {"$ne": True}}
    return {
        "lead": {"name": lead["name"], "first_name": flow.first_name(lead), "ask": lead["ask"], "phone": lead["phone"],
                 "status": lead["status"], "quote_pending": lead.get("quote_pending", False),
                 "escalated": lead.get("escalated", False)},
        "contractor": {"name": contractor["name"], "agent_name": contractor["agent_name"], "phone": contractor["phone"]},
        "quote": await latest_quote(lead["id"]),
        "contract": await db.contracts.find_one(active, {"_id": 0}, sort=[("created_at", -1)]),
        "payment": await db.payments.find_one(active, {"_id": 0}, sort=[("created_at", -1)]),
        "session": await flow.active_session(lead["id"]),
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


@router.post("/{token}/frames")
async def frames(token: str, body: Frame):
    lead = await flow.lead_by_token(token)
    if not body.image.startswith("data:image/jpeg;base64,"):
        raise HTTPException(422, "Frames must be JPEG data URLs")
    session = await flow.active_session(lead["id"])
    await db.frames.insert_one({"lead_id": lead["id"], "session_id": session["id"] if session else None,
                                "image": body.image, "at": iso()})
    return {"stored": True, "chips": (session or {}).get("chips", [])}


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

