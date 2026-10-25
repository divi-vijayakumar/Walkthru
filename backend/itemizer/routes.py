from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth.routes import require_user
from core.db import db
from core import flow
from itemizer import engine, camera
from itemizer.kb import seed_kb

router = APIRouter(prefix="/api", dependencies=[Depends(require_user)])
KINDS = {"tasks": ("kb_tasks", "task_id"), "facts": ("kb_facts", "fact_id"), "rules": ("kb_rules", "rule_id")}


LADDER = {"camera", "show", "ask", "measure", "assume"}
NUM = (int, float)


def price_ok(p, facts):
    if not isinstance(p, dict):
        return False
    amount, tiers, when = p.get("amount"), p.get("tiers"), p.get("when", {})
    num = lambda v: isinstance(v, NUM) and not isinstance(v, bool) and v >= 0
    return (num(amount) or (isinstance(tiers, list) and len(tiers) == 3 and all(num(v) for v in tiers))) \
        and num(p.get("mult", 1)) and p.get("qty", next(iter(facts), None)) in facts \
        and isinstance(when, dict) and all(k in facts and isinstance(v, list) for k, v in when.items())


def kb_problem(kind, doc, tasks, facts):
    """Returns what's wrong with an edited KB doc, or None."""
    if kind == "tasks":
        if not isinstance(doc.get("label"), str) or not all(isinstance(doc.get(k), list) for k in ("facts", "price", "triggers", "tags")):
            return "A task needs label, facts, price, triggers and tags"
        if not doc["price"] or not all(price_ok(p, facts) for p in doc["price"]):
            return "Each price needs a number amount or three tier numbers; qty and when must use known facts"
        if any(f not in facts for f in doc["facts"]):
            return "Unknown fact in facts"
    elif kind == "facts":
        if doc.get("scope") not in ("item", "room", "job") or not isinstance(doc.get("label"), str):
            return "A fact needs scope (item, room or job) and label"
        if not isinstance(doc.get("ladder"), list) or not doc["ladder"] or not set(doc["ladder"]) <= LADDER:
            return "Ladder steps must be camera, show, ask, measure or assume"
        if "default" not in doc or not all(isinstance(doc.get(k), str) for k in ("question", "show")) or not isinstance(doc.get("goals"), list):
            return "A fact needs default, question, show and goals"
    elif doc.get("kind") == "rule":
        if doc.get("add") not in tasks or not all(isinstance(doc.get(k), list) for k in ("has", "lacks")) \
                or not all(isinstance(doc.get(k), dict) for k in ("facts", "lt")):
            return "A rule needs add (a task id), has, lacks, facts and lt"
        if not isinstance(doc.get("not", {}), dict):
            return "A rule's not must map facts to lists"
        if any(k not in facts for k in list(doc["facts"]) + list(doc["lt"]) + list(doc.get("not", {}))) or any(t not in tasks for t in doc["has"] + doc["lacks"]):
            return "Rule facts and tasks must already exist"
    elif doc.get("kind") not in ("driver", "measure_method") or not isinstance(doc.get("name"), str):
        return "Kind must be rule, driver or measure_method, with a name"
    return None


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
    box: Optional[list] = None
    label: Optional[str] = None


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
    tasks = {t["task_id"] async for t in db.kb_tasks.find({}, {"task_id": 1})}
    facts = {f["fact_id"] async for f in db.kb_facts.find({}, {"fact_id": 1})}
    problem = kb_problem(kind, doc, tasks, facts)
    if problem:
        raise HTTPException(422, problem)
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
    lead = await flow.get_lead(lead_id)
    out, priced = await engine.turn(lead, body.said, body.answers, body.camera_on)
    camera.after_turn(lead)
    return {**out, "lines": priced["lines"] if priced else []}


@router.post("/itemizer/{lead_id}/goal-result")
async def goal_result(lead_id: str, body: GoalIn):
    out = await engine.on_goal_result(await flow.get_lead(lead_id), body.model_dump())
    if not out["ok"]:
        raise HTTPException(404, out["error"])
    return out


@router.post("/itemizer/{lead_id}/reset")
async def reset(lead_id: str):
    await flow.get_lead(lead_id)
    await db.itemizer_sessions.delete_one({"lead_id": lead_id})
    return {"reset": True}
