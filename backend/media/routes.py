import os
import re
import time
import hmac
import shutil
from typing import Literal, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from auth.routes import require_user
from core.db import db, iso
from core.service_auth import service_key, require_service_key
from core import storage, flow
from media.store import store_clip, public, url_sig

router = APIRouter(prefix="/api")
dev_router = APIRouter(prefix="/api/dev", dependencies=[Depends(require_user)])
MAX_CLIP_BYTES = 40 * 1024 * 1024
MAX_VIDEO_BYTES = 400 * 1024 * 1024
CHUNK_DIR = "/tmp/walkthru_uploads"
UPLOAD_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


async def portal_session(request: Request, session_id: str):
    """The uploader is either a service (X-Walkthru-Key) or the homeowner's portal link with a live call."""
    session = await db.call_sessions.find_one({"id": session_id}, {"_id": 0, "transcript": 0})
    if not session:
        raise HTTPException(404, "Unknown session")
    if service_key(request):
        return session
    lead = await db.leads.find_one({"portal_token": request.headers.get("x-portal-token") or "-"}, {"_id": 0, "id": 1})
    if not lead or lead["id"] != session["lead_id"]:
        raise HTTPException(401, "Not allowed to upload to this session")
    if session.get("ended_at"):
        raise HTTPException(400, "This call has ended")
    return session


@router.post("/media")
async def upload(request: Request, session_id: str = Form(...), kind: Literal["video"] = Form(...), seq: int = Form(..., ge=0),
                 t_start_ms: int = Form(..., ge=0), duration_ms: Optional[int] = Form(None), file: UploadFile = File(...)):
    session = await portal_session(request, session_id)
    data = await file.read()
    if not data or len(data) > MAX_CLIP_BYTES:
        raise HTTPException(413, "Clip is empty or too large")
    doc, created = await store_clip(session, kind, seq, t_start_ms, data, file.content_type, duration_ms)
    return {**public(doc), "created": created}


@router.get("/media/{media_id}", dependencies=[Depends(require_service_key)])
async def get_media(media_id: str):
    doc = await db.media.find_one({"media_id": media_id, "is_deleted": False}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Media not found")
    return public(doc)


@router.get("/media/{media_id}/file")
async def media_file(media_id: str, exp: int, sig: str):
    if exp < time.time() or not hmac.compare_digest(sig, url_sig(media_id, exp)):
        raise HTTPException(403, "Link expired or invalid")
    doc = await db.media.find_one({"media_id": media_id, "is_deleted": False}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Media not found")
    data, _ = await storage.get(doc["storage_path"])
    return Response(data, media_type=doc["content_type"])


@router.get("/sessions/{session_id}/media", dependencies=[Depends(require_service_key)])
async def session_media(session_id: str, kind: Literal["video"] = "video", from_ms: Optional[int] = None, to_ms: Optional[int] = None):
    q = {"session_id": session_id, "kind": kind, "is_deleted": False}
    if to_ms is not None:
        q["t_start_ms"] = {"$lte": to_ms}
    docs = await db.media.find(q, {"_id": 0}).sort("t_start_ms", 1).to_list(500)
    if from_ms is not None:
        docs = [d for d in docs if d["t_start_ms"] + d["duration_ms"] >= from_ms]
    return {"session_id": session_id, "media": [public(d) for d in docs]}


# /dev: upload a whole walkthrough video in chunks, stored as one clip through the same path
@dev_router.post("/uploads/{upload_id}/chunk")
async def upload_chunk(upload_id: str, index: int, request: Request):
    if not UPLOAD_ID.match(upload_id) or not 0 <= index < 200:
        raise HTTPException(422, "Bad upload id or chunk index")
    data = await request.body()
    if not data or len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "Chunk is empty or larger than 8 MB")
    os.makedirs(f"{CHUNK_DIR}/{upload_id}", exist_ok=True)
    with open(f"{CHUNK_DIR}/{upload_id}/{index:04d}", "wb") as f:
        f.write(data)
    return {"received": index}


class VideoDone(BaseModel):
    upload_id: str
    content_type: str = "video/mp4"


async def dev_session(lead):
    session = await flow.active_session(lead["id"]) or await db.call_sessions.find_one(
        {"lead_id": lead["id"]}, {"_id": 0, "transcript": 0}, sort=[("started_at", -1)])
    if session:
        return session
    session = {"id": f"dev-{lead['id']}", "lead_id": lead["id"], "started_at": iso(), "ended_at": iso(), "transcript": [],
               "live_caption": "", "live_role": "", "camera_on": False, "chips": [], "source": "dev_upload"}
    await db.call_sessions.insert_one(dict(session))
    return session


@dev_router.post("/leads/{lead_id}/video")
async def dev_video(lead_id: str, body: VideoDone):
    lead = await flow.get_lead(lead_id)
    folder = f"{CHUNK_DIR}/{body.upload_id}"
    if not UPLOAD_ID.match(body.upload_id) or not os.path.isdir(folder):
        raise HTTPException(404, "Upload not found")
    parts = sorted(os.listdir(folder))
    data = b"".join(open(f"{folder}/{p}", "rb").read() for p in parts)
    shutil.rmtree(folder, ignore_errors=True)
    if not data or len(data) > MAX_VIDEO_BYTES:
        raise HTTPException(413, "Video is empty or larger than 400 MB")
    session = await dev_session(lead)
    last = await db.media.find_one({"session_id": session["id"]}, {"_id": 0}, sort=[("t_start_ms", -1)])
    start = last["t_start_ms"] + last["duration_ms"] if last else 0
    doc, _ = await store_clip(session, "video", start, start, data, body.content_type)
    return {**public(doc), "session_id": session["id"]}
