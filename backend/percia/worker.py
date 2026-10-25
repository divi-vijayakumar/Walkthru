"""Background runner: sample clips at 1 fps, judge several goals per pass, keep only hit frames, call back."""
import glob
import json
import uuid
import asyncio
import logging
import tempfile
import httpx
import imageio_ffmpeg
from core.db import db, iso
from core import storage
from core.service_auth import walkthru_keys, key_id, sign, app_url
from percia import judge

logger = logging.getLogger("percia")
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
MAX_FRAMES = 24
PUBLIC = ("goal_id", "status", "result", "explanation", "value", "unit", "hits")
_running = set()


def public(g):
    return {k: g.get(k) for k in PUBLIC}


def kick(session_id):
    if session_id not in _running:
        _running.add(session_id)
        asyncio.create_task(_drain(session_id))


async def init():
    await db.percia_goals.create_index("goal_id", unique=True)
    await db.percia_goals.update_many({"status": "running"}, {"$set": {"status": "queued"}})
    for sid in await db.percia_goals.distinct("session_id", {"status": "queued"}):
        kick(sid)


async def _drain(session_id):
    try:
        await asyncio.sleep(0.8)  # let goals sent together share one pass
        while True:
            goals = await db.percia_goals.find({"session_id": session_id, "status": "queued"}, {"_id": 0}).to_list(50)
            if not goals:
                break
            groups = {}
            for g in goals:
                groups.setdefault(tuple(m["media_id"] for m in g["media"]), []).append(g)
            for group in groups.values():
                await _run_group(group)
    finally:
        _running.discard(session_id)
    if await db.percia_goals.count_documents({"session_id": session_id, "status": "queued"}):
        kick(session_id)


async def _sample(media, folder):
    frames = []
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        for n, m in enumerate(media):
            r = await client.get(m["url"])
            r.raise_for_status()
            src = f"{folder}/clip{n}"
            with open(src, "wb") as f:
                f.write(r.content)
            proc = await asyncio.create_subprocess_exec(FFMPEG, "-hide_banner", "-loglevel", "error", "-i", src, "-vf", "fps=1,scale=768:-2",
                                                        "-q:v", "5", f"{folder}/c{n}_%04d.jpg")
            await proc.wait()
            for i, path in enumerate(sorted(glob.glob(f"{folder}/c{n}_*.jpg"))):
                frames.append({"t_ms": m["t_start_ms"] + i * 1000, "path": path})
    if len(frames) > MAX_FRAMES:
        step = len(frames) / MAX_FRAMES
        frames = [frames[int(i * step)] for i in range(MAX_FRAMES)]
    return frames


async def _keep_hits(goal_id, result, frames):
    hits = []
    for h in result["hits"]:
        f = frames[h["frame"]]
        frame_id = f"f_{uuid.uuid4().hex}"
        path = await storage.put(f"percia/{goal_id}/{frame_id}.jpg", open(f["path"], "rb").read(), "image/jpeg")
        await db.percia_frames.insert_one({"frame_id": frame_id, "goal_id": goal_id, "storage_path": path, "t_ms": f["t_ms"], "created_at": iso()})
        hits.append({"t_ms": f["t_ms"], "frame_url": f"{app_url()}/api/percia/frames/{frame_id}", "box": h["box"],
                     "label": h["label"], "confidence": h["confidence"]})
    return hits


async def _run_group(goals):
    ids = [g["goal_id"] for g in goals]
    await db.percia_goals.update_many({"goal_id": {"$in": ids}}, {"$set": {"status": "running", "updated_at": iso()}})
    with tempfile.TemporaryDirectory() as folder:
        try:
            frames = await _sample(goals[0]["media"], folder)
            if not frames:
                raise ValueError("no frames could be read from the clips")
            results = await judge.judge_goal(frames, [{"goal_id": g["goal_id"], "query": g["query"]} for g in goals])
            for g in goals:
                res = results[g["goal_id"]]
                hits = await _keep_hits(g["goal_id"], res, frames)
                await db.percia_goals.update_one({"goal_id": g["goal_id"]}, {"$set": {**res, "hits": hits, "status": "done", "updated_at": iso()}})
        except Exception as e:
            logger.warning("goal pass failed: %s", e)
            await db.percia_goals.update_many({"goal_id": {"$in": ids}, "status": "running"}, {"$set": {
                "status": "failed", "result": None, "explanation": "The camera check couldn't be completed.", "value": None,
                "unit": None, "hits": [], "error": str(e)[:300], "updated_at": iso()}})
    for gid in ids:
        await deliver(await db.percia_goals.find_one({"goal_id": gid}, {"_id": 0}))


async def deliver(g):
    """POST goal.completed to the callback, HMAC-SHA256 signed with the key that created the goal."""
    if not g.get("callback_url"):
        return
    secret = next((k for k in walkthru_keys() if key_id(k) == g["key_id"]), None)
    if not secret:
        return
    body = json.dumps({"event": "goal.completed", "session_id": g["session_id"], "occurred_at": iso(),
                       "idempotency_key": f"{g['goal_id']}:{g['status']}", "data": public(g)}).encode()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(g["callback_url"], content=body, headers={"Content-Type": "application/json", "X-Walkthru-Signature": sign(secret, body)})
        ok = r.status_code < 300
    except Exception as e:
        logger.warning("callback failed for %s: %s", g["goal_id"], e)
        ok = False
    await db.percia_goals.update_one({"goal_id": g["goal_id"]}, {"$set": {"callback_ok": ok, "callback_at": iso()}})
