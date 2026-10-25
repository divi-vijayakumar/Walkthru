from typing import List, Literal
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, HttpUrl
from core.db import db, iso
from core import storage
from core.service_auth import require_service_key, key_id
from percia import worker

router = APIRouter(prefix="/api/percia")


class MediaRef(BaseModel):
    media_id: str
    url: HttpUrl
    kind: Literal["video"]
    t_start_ms: int = Field(ge=0)


class GoalIn(BaseModel):
    goal_id: str = Field(min_length=1, max_length=100)
    session_id: str = Field(min_length=1, max_length=100)
    query: str = Field(min_length=3, max_length=1000)
    media: List[MediaRef] = Field(min_length=1, max_length=6)
    callback_url: HttpUrl


@router.post("/goals")
async def create_goal(body: GoalIn, key: str = Depends(require_service_key)):
    existing = await db.percia_goals.find_one({"goal_id": body.goal_id}, {"_id": 0})
    if not existing:
        doc = {**body.model_dump(mode="json"), "status": "queued", "result": None, "explanation": None, "value": None,
               "unit": None, "hits": [], "key_id": key_id(key), "created_at": iso(), "updated_at": iso()}
        try:
            await db.percia_goals.insert_one(dict(doc))
        except Exception:
            existing = await db.percia_goals.find_one({"goal_id": body.goal_id}, {"_id": 0})
        else:
            worker.kick(body.session_id)
            existing = doc
    return JSONResponse({"goal_id": body.goal_id, "status": existing["status"]}, status_code=202)


@router.get("/goals/{goal_id}", dependencies=[Depends(require_service_key)])
async def get_goal(goal_id: str):
    g = await db.percia_goals.find_one({"goal_id": goal_id}, {"_id": 0})
    if not g:
        raise HTTPException(404, "Goal not found")
    return worker.public(g)


@router.get("/frames/{frame_id}")
async def frame(frame_id: str):
    f = await db.percia_frames.find_one({"frame_id": frame_id}, {"_id": 0})
    if not f:
        raise HTTPException(404, "Frame not found")
    data, _ = await storage.get(f["storage_path"])
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})
