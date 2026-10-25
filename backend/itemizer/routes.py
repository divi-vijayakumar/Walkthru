from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth.routes import require_user
from core.db import db
from core import flow
from itemizer import engine
from itemizer.kb import seed_kb

router = APIRouter(prefix="/api", dependencies=[Depends(require_user)])
KINDS = {"tasks": ("kb_tasks", "task_id"), "facts": ("kb_facts", "fact_id"), "rules": ("kb_rules", "rule_id")}


class TurnIn(BaseModel):
    said: str = ""
    answers: dict = {}
    camera_on: bool = False


class GoalIn(BaseModel):
    fact_id: str
    status: Literal["met", "ambiguous", "not_found"]
    confidence: float = 0
    value: Optional[str] = None
    frame_url: Optional[str] = None
    t_ms: Optional[int] = None
    goal_id: Optional[str] = None


@router.get("/kb")
async def kb():
    return {k: await db[c].find({}, {"_id": 0}).to_list(1000) for k, (c, _) in KINDS.items()}


@router.put("/kb/{kind}/{doc_id}")
async def kb_update(kind: str, doc_id: str, doc: dict):
    if kind not in KINDS:
        raise HTTPException(404, "Unknown table")
    coll, key = KINDS[kind]
    if doc.get(key) != doc_id:
        raise HTTPException(422, f"{key} can't be changed")
    doc.pop("_id", None)
    res = await db[coll].replace_one({key: doc_id}, doc)
    if not res.matched_count:
        raise HTTPException(404, "Not found")
    return doc


@router.post("/kb/reset")
async def kb_reset():
    await seed_kb(force=True)
    return {"reset": True}


@router.get("/itemizer/{lead_id}")
async def session(lead_id: str):
    lead = await flow.get_lead(lead_id)
    return await engine.get_session(lead)


@router.post("/itemizer/{lead_id}/turn")
async def dev_turn(lead_id: str, body: TurnIn):
    out, priced = await engine.turn(await flow.get_lead(lead_id), body.said, body.answers, body.camera_on)
    return {**out, "lines": priced["lines"] if priced else []}


@router.post("/itemizer/{lead_id}/goal-result")
async def goal_result(lead_id: str, body: GoalIn):
    return await engine.on_goal_result(await flow.get_lead(lead_id), body.model_dump())


@router.post("/itemizer/{lead_id}/reset")
async def reset(lead_id: str):
    await flow.get_lead(lead_id)
    await db.itemizer_sessions.delete_one({"lead_id": lead_id})
    return {"reset": True}
