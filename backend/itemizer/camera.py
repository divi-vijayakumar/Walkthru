"""Itemizer <-> Percia: send camera goals for open facts, take goal.completed (callback or poll) into on_goal_result."""
import os
import json
import uuid
import hmac
import asyncio
import logging
from datetime import timedelta
import httpx
from fastapi import APIRouter, HTTPException, Request
from core.db import db, iso, now
from core import events
from core.service_auth import sign, app_url
from itemizer import engine

logger = logging.getLogger("itemizer.camera")
callback_router = APIRouter(prefix="/api/itemizer")
CLIPS_PER_GOAL = 1
POLL_AFTER_S, GIVE_UP_S = 15, 600


def percia_url():
    return (os.environ.get("PERCIA_URL") or app_url()).rstrip("/")


def media_url():
    return (os.environ.get("MEDIA_URL") or app_url()).rstrip("/")


def headers():
    return {"X-Walkthru-Key": os.environ["PERCIA_KEY"]}


def max_goals():
    return int(os.environ.get("PERCIA_MAX_GOALS_PER_CALL") or 40)


SURVEY_QUERY = ("List what is visible: sink type (pedestal, wall-mounted, vanity cabinet), toilet, tub or shower, mirror type, floor material and "
                "tile size, wall finish (tile, paint, wallpaper), lights, and any water damage. Estimate the floor area. Give one hit per thing "
                "you can see (up to 9), each label as 'key: answer' with key one of sink, toilet, tub_shower, mirror, floor, tile_size, walls, "
                "lights, water_damage (e.g. 'sink: pedestal', 'mirror: framed', 'floor: tile', 'tile_size: 12 in', 'walls: paint', "
                "'water_damage: no'). Put the floor area in value, in sq ft.")


def unit_of(d):
    label = d["label"]
    return label[label.find("(") + 1: label.find(")")] if "(" in label else "count"


def goal_query(d):
    q = (d.get("goals") or [""])[0]
    if "reply with" in q.lower():
        return q
    if d.get("options"):
        return f"{q} Start each hit label with the answer, one of: {', '.join(d['options'])}, then a colon and a few words (e.g. '{d['options'][0]}: ...')."
    if d.get("numeric"):
        return f"{q} Put the answer in value as a number, in {unit_of(d)}."
    return q


def at_camera(f, kbf):
    if f["state"] in ("open", "asked", "assumed") and f.get("camera_pending") and kbf.get(f["name"], {}).get("goals"):
        return True
    ch = f["ladder"][f["idx"]] if f["idx"] < len(f["ladder"]) else "assume"
    return ch in ("camera", "show") and (f["state"] in ("open", "asked", "waiting_on_camera") or (f["state"] == "assumed" and f.get("camera_pending"))) \
        and (kbf.get(f["name"], {}).get("goals"))


async def send_goals(call_session_id):
    """On each stored clip and after update_scope: one camera survey until it has answers, frames for Apex-priced work,
    and a goal per open camera fact. Never raises; a slow or failed Percia never blocks the call."""
    try:
        cs = await db.call_sessions.find_one({"id": call_session_id}, {"_id": 0, "lead_id": 1})
        if not cs:
            return
        lead_id = cs["lead_id"]
        s = await db.itemizer_sessions.find_one({"lead_id": lead_id}, {"_id": 0}) or {}
        kbf = {f["fact_id"]: f async for f in db.kb_facts.find({}, {"_id": 0})}
        facts = [f for f in s.get("facts", []) if at_camera(f, kbf)]
        customs = [i for i in s.get("items", []) if i.get("custom") and i["status"] != "removed" and not i.get("frames")]
        if not (facts or customs or not s.get("survey_done")):
            return
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(f"{media_url()}/api/sessions/{call_session_id}/media", params={"kind": "video"}, headers=headers())
            r.raise_for_status()
            clips = r.json()["media"][-CLIPS_PER_GOAL:]
            if not clips:
                return
            newest = clips[-1]["media_id"]
            budget = max_goals() - await db.itemizer_goals.count_documents({"call_session_id": call_session_id})
            fresh = {"$or": [{"status": "sent"}, {"newest_media_id": newest}]}
            todo = []
            if not s.get("survey_done") and not await db.itemizer_goals.find_one({"lead_id": lead_id, "kind": "survey", **fresh}):
                todo.append(({"kind": "survey"}, SURVEY_QUERY))
            for it in customs:
                if not await db.itemizer_goals.find_one({"lead_id": lead_id, "kind": "custom", "item_id": it["item_id"], **fresh}):
                    todo.append(({"kind": "custom", "item_id": it["item_id"]},
                                 f"Find the frames that best show this: {it['said']}. Label each hit with a few words about what it shows."))
            for f in facts:
                if not await db.itemizer_goals.find_one({"fact_id": f["fact_id"], "lead_id": lead_id, **fresh}):
                    d = kbf[f["name"]]
                    todo.append(({"fact_id": f["fact_id"], "options": d.get("options") or [], "numeric": bool(d.get("numeric"))}, goal_query(d)))
            await asyncio.gather(*(post_goal(client, cs, call_session_id, meta, q, clips, newest) for meta, q in todo[:max(budget, 0)]))
    except Exception as e:
        logger.warning("send_goals failed: %s", e)


async def post_goal(client, cs, call_session_id, meta, query, clips, newest):
    """All goals for a clip go out together so Percia judges them in one pass."""
    goal_id = f"g_{uuid.uuid4().hex}"
    await db.itemizer_goals.insert_one({
        "goal_id": goal_id, "lead_id": cs["lead_id"], "call_session_id": call_session_id, "kind": "fact", "fact_id": None,
        "options": [], "numeric": False, **meta, "newest_media_id": newest, "status": "sent", "created_at": iso()})
    body = {"goal_id": goal_id, "session_id": call_session_id, "query": query, "callback_url": f"{app_url()}/api/itemizer/percia/callback",
            "media": [{k: c[k] for k in ("media_id", "url", "kind", "t_start_ms")} for c in clips]}
    try:
        res = await client.post(f"{percia_url()}/api/percia/goals", json=body, headers=headers())
        ok = res.status_code == 202
    except Exception:
        ok = False
    if not ok:
        logger.warning("percia refused goal %s", goal_id)
        await db.itemizer_goals.update_one({"goal_id": goal_id}, {"$set": {"status": "failed"}})


def after_turn(lead):
    """Fire-and-forget after update_scope: send goals for facts now at camera/show."""
    async def go():
        cs = await db.call_sessions.find_one({"lead_id": lead["id"]}, {"_id": 0, "id": 1}, sort=[("started_at", -1)])
        if cs:
            await send_goals(cs["id"])
    asyncio.create_task(go())


def answer_of(g, data):
    hits = sorted(data.get("hits") or [], key=lambda h: -h.get("confidence", 0))
    best = hits[0] if hits else {}
    if g["numeric"]:
        return data.get("value"), best
    label = (best.get("label") or "").lower()
    head = label.split(":", 1)[0].strip()
    if head in g["options"]:
        return head, best
    text = f"{label} {(data.get('explanation') or '').lower()}"
    found = [o for o in g["options"] if o in text]
    return (found[0] if len(found) == 1 else None), best


def chip(label):
    text = label.split(":", 1)[-1].strip() or label
    return text[:1].upper() + text[1:]


async def handle_result(data):
    """goal.completed -> Itemizer.on_goal_result, once per goal."""
    g = await db.itemizer_goals.find_one_and_update({"goal_id": data.get("goal_id"), "status": "sent"},
                                                    {"$set": {"status": "done", "result": data, "done_at": iso()}})
    if not g:
        return False
    lead = await db.leads.find_one({"id": g["lead_id"]}, {"_id": 0})
    if g.get("kind") == "custom":
        await engine.on_custom_frames(lead, g["item_id"], data)
        return True
    if g.get("kind") == "survey":
        if data.get("status") == "done" and data.get("result") in ("met", "ambiguous"):
            out = await engine.on_survey(lead, data)
            chips = [p[:1].upper() + p[1:] for p in out["phrases"][:3]]
            if chips:
                await db.call_sessions.update_one({"id": g["call_session_id"]}, {"$addToSet": {"chips": {"$each": chips}}})
        return True
    value, best = answer_of(g, data)
    status = data.get("result") if data.get("status") == "done" else "not_found"
    if status in ("met", "ambiguous") and value is None:
        status = "not_found"
    goal = {"fact_id": g["fact_id"], "status": status, "confidence": best.get("confidence", 0.6 if g["numeric"] else 0.8 if status == "met" else 0.5),
            "value": None if value is None else str(int(value) if isinstance(value, float) and value.is_integer() else value),
            "frame_url": best.get("frame_url"), "t_ms": best.get("t_ms"), "goal_id": g["goal_id"], "box": best.get("box"), "label": best.get("label")}
    await engine.on_goal_result(lead, goal)
    if data.get("result") == "met":
        chips = [chip(h["label"]) for h in sorted(data.get("hits") or [], key=lambda h: -h.get("confidence", 0))[:1] if h.get("label")]
        if chips:
            await db.call_sessions.update_one({"id": g["call_session_id"]}, {"$addToSet": {"chips": {"$each": chips}}})
    return True


@callback_router.post("/percia/callback")
async def percia_callback(request: Request):
    raw = await request.body()
    sent = request.headers.get("x-walkthru-signature", "")
    if not hmac.compare_digest(sent, sign(os.environ["PERCIA_KEY"], raw)):
        raise HTTPException(401, "Bad signature")
    body = json.loads(raw)
    if body.get("event") == "goal.completed":
        await handle_result(body.get("data") or {})
    return {"ok": True}


async def poll_once():
    cutoff, give_up = iso(now() - timedelta(seconds=POLL_AFTER_S)), iso(now() - timedelta(seconds=GIVE_UP_S))
    async with httpx.AsyncClient(timeout=8) as client:
        async for g in db.itemizer_goals.find({"status": "sent", "created_at": {"$lt": cutoff}}, {"_id": 0}).limit(50):
            try:
                r = await client.get(f"{percia_url()}/api/percia/goals/{g['goal_id']}", headers=headers())
                data = r.json() if r.status_code == 200 else None
            except Exception:
                data = None
            if data and data.get("status") in ("done", "failed"):
                await handle_result(data)
            elif g["created_at"] < give_up:
                await handle_result({"goal_id": g["goal_id"], "status": "failed", "result": None, "hits": []})


async def poll_loop():
    while True:
        await asyncio.sleep(10)
        try:
            await poll_once()
        except Exception as e:
            logger.warning("poll failed: %s", e)


async def on_media_stored(ev):
    await send_goals(ev["session_id"])


def init():
    events.subscribe("media.stored", on_media_stored)
    asyncio.create_task(poll_loop())
