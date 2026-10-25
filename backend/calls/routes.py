"""Calls (Sessions page), recordings, and in-person visit scheduling."""
import time
import hmac
import logging
import httpx
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from auth.routes import require_user
from core.db import db, iso, get_contractor
from core import storage, flow
from core.sms import send_sms
from core.status import touch
from core.service_auth import sign, app_url
import os

logger = logging.getLogger("calls")
router = APIRouter(prefix="/api", dependencies=[Depends(require_user)])
public_router = APIRouter(prefix="/api")
REC_TTL_S = 900


def is_sample(lead_id):
    return str(lead_id).startswith("lead-")


def secs(a, b):
    from datetime import datetime
    return int((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds()) if a and b else None


async def outcome(s, lead):
    if s.get("taken_over"):
        return "Taken over by contractor"
    if await db.followups.find_one({"lead_id": s["lead_id"], "site_visit_requested": True, "at": {"$gte": s["started_at"]}}):
        return "Visit requested"
    end = s.get("ended_at") or iso()
    if await db.quotes.find_one({"lead_id": s["lead_id"], "created_at": {"$gte": s["started_at"], "$lte": end}}):
        return "Quote given"
    if lead.get("status") == "dropped":
        return "Declined"
    if lead.get("escalated"):
        return "Needs a person"
    if lead.get("quote_pending") or lead.get("followup_queued"):
        return "Quote pending"
    return "In progress" if not s.get("ended_at") else "Ended"


async def summary(s, leads):
    lead = leads.get(s["lead_id"]) or {}
    q = await db.quotes.find_one({"lead_id": s["lead_id"], "created_at": {"$gte": s["started_at"], "$lte": s.get("ended_at") or iso()}},
                                 {"_id": 0, "total": 1, "version": 1}, sort=[("version", -1)])
    return {"id": s["id"], "lead_id": s["lead_id"], "lead_name": lead.get("name"), "sample": is_sample(s["lead_id"]),
            "started_at": s["started_at"], "ended_at": s.get("ended_at"), "duration_s": secs(s["started_at"], s.get("ended_at")),
            "outcome": await outcome(s, lead), "quote_total": q["total"] if q else None, "has_recording": bool(s.get("recording_path") or s.get("recording_url"))}


@router.get("/calls")
async def calls():
    leads = {lead["id"]: lead async for lead in db.leads.find({}, {"_id": 0})}
    rows = [await summary(s, leads) async for s in db.call_sessions.find({"lead_id": {"$in": list(leads)}}, {"_id": 0, "transcript": 0}).sort("started_at", -1).limit(300)]
    return {"calls": rows}


def rec_sig(call_id, exp):
    return sign(os.environ["MEDIA_SIGNING_KEY"], f"rec.{call_id}.{exp}".encode())


@router.get("/calls/{call_id}")
async def call_detail(call_id: str):
    s = await db.call_sessions.find_one({"id": call_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Call not found")
    lead = await db.leads.find_one({"id": s["lead_id"]}, {"_id": 0}) or {}
    exp = int(time.time()) + REC_TTL_S
    rec = f"{app_url()}/api/call-recordings/{call_id}?exp={exp}&sig={rec_sig(call_id, exp)}" if s.get("recording_path") else s.get("recording_url")
    findings = []
    async for g in db.itemizer_goals.find({"call_session_id": call_id, "status": "done"}, {"_id": 0}).sort("created_at", 1):
        res = g.get("result") or {}
        if res.get("result") in ("met", "ambiguous"):
            hit = (res.get("hits") or [{}])[0]
            findings.append({"fact_id": g["fact_id"], "explanation": res.get("explanation"), "label": hit.get("label"),
                             "frame_url": hit.get("frame_url"), "box": hit.get("box"), "result": res.get("result")})
    quotes = await db.quotes.find({"lead_id": s["lead_id"], "created_at": {"$gte": s["started_at"], "$lte": s.get("ended_at") or iso()}},
                                  {"_id": 0, "version": 1, "total": 1, "low": 1, "high": 1, "status": 1, "created_at": 1}).sort("version", 1).to_list(50)
    leads = {lead.get("id"): lead}
    return {**await summary(s, leads), "lead_phone": lead.get("phone"), "transcript": s.get("transcript") or [],
            "recording": rec, "summary": s.get("summary"), "findings": findings, "quotes": quotes}


@public_router.get("/call-recordings/{call_id}")
async def recording(call_id: str, exp: int, sig: str):
    if exp < time.time() or not hmac.compare_digest(sig, rec_sig(call_id, exp)):
        raise HTTPException(403, "Link expired or invalid")
    s = await db.call_sessions.find_one({"id": call_id}, {"_id": 0, "recording_path": 1})
    if not s or not s.get("recording_path"):
        raise HTTPException(404, "No recording")
    data, ctype = await storage.get(s["recording_path"])
    return Response(data, media_type=ctype if ctype.startswith("audio") else "audio/wav")


async def copy_recording(call_id, url):
    """Vapi's link can expire, so keep our own copy."""
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
        ctype = r.headers.get("content-type", "audio/wav").split(";")[0]
        path = await storage.put(f"recordings/{call_id}.{'mp3' if 'mpeg' in ctype else 'wav'}", r.content, ctype)
        await db.call_sessions.update_one({"id": call_id}, {"$set": {"recording_path": path}})
    except Exception as e:
        logger.warning("recording copy failed for %s: %s", call_id, e)


class VisitIn(BaseModel):
    when: str = Field(min_length=3, max_length=80)


@router.post("/leads/{lead_id}/visit")
async def schedule_visit(lead_id: str, body: VisitIn):
    lead = await flow.get_lead(lead_id)
    contractor = await get_contractor()
    msg = f"Your visit with {contractor.get('owner_first_name') or 'George'} from {contractor['name']} is set for {body.when}. Reply here if you need to change it."
    sms = await send_sms(lead, msg, "visit_scheduled")
    await touch(lead_id, {"visit_scheduled_for": body.when, "visit_scheduled_at": iso()})
    return {"scheduled": True, "sms": sms}


class Followup(BaseModel):
    site_visit_requested: Optional[bool] = False
    preferred_visit_times: Optional[str] = ""
