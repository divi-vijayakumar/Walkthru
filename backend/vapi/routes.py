import os
import json
import asyncio
import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from core.db import db, iso, get_contractor
from core.status import touch
from core.quotes import latest_quote, save_quote
from core import flow
from pricing.engine import new_state, adjust_state, price, margin_pct, drivers

router = APIRouter(prefix="/api/vapi")
logger = logging.getLogger("vapi")


def summary(q, say, status="ok"):
    return {"status": status, "say": say, "version": q["version"], "total": q["total"], "low": q["low"],
            "high": q["high"], "drivers": q.get("drivers") or [], "deposit_percent": q["deposit_pct"],
            "deposit_amount": q["deposit_amount"]}


async def resolve_lead(msg):
    call = msg.get("call") or {}
    values = (call.get("assistantOverrides") or {}).get("variableValues") or {}
    token = values.get("lead_token")
    if token:
        return await db.leads.find_one({"portal_token": token}, {"_id": 0})
    return await db.leads.find_one({"status": "walkthru_initiated"}, {"_id": 0}, sort=[("last_activity_at", -1)])


async def persist(lead, st, say):
    items, total = price(st)
    await db.pricing_states.update_one({"lead_id": lead["id"]}, {"$set": {"state": st}}, upsert=True)
    in_call = lead["status"] == "walkthru_initiated"
    q = await save_quote(lead, items, total, "live" if in_call else "sent",
                         {"margin_pct": margin_pct(st, total), "drivers": drivers(st)})
    if not in_call and lead["status"] == "walkthru_completed":
        await flow.mark_quote_ready(await flow.get_lead(lead["id"]))
    return summary(q, say)


async def tool_estimate(lead, args, mode):
    if mode == "pending":
        return {"status": "pending", "say": "Pricing is not available right now."}
    st, say = new_state(args)
    return say if st is None else await persist(lead, st, say)


async def tool_adjust(lead, args, mode):
    if mode == "pending":
        return {"status": "pending", "say": "Pricing is not available right now."}
    doc = await db.pricing_states.find_one({"lead_id": lead["id"]})
    if not doc:
        return {"status": "needs_info", "missing": ["estimate"], "say": "Get an estimate first."}
    contractor = await get_contractor()
    st = doc["state"]
    say, out = adjust_state(st, args, contractor["max_discount_pct"], contractor["min_margin_pct"])
    if say is None:
        q = await latest_quote(lead["id"])
        if out["status"] == "limit_reached" and q:
            return {**summary(q, out["say"], "limit_reached"), "max_discount_percent": out["max_discount_percent"]}
        return out
    return await persist(lead, st, say)


async def tool_followup(lead, args, mode):
    await db.followups.insert_one({"lead_id": lead["id"], "args": args, "at": iso()})
    await touch(lead["id"], {"followup_queued": True})
    return {"status": "ok", "say": "Follow-up queued."}


TOOLS = {"get_quote_estimate": tool_estimate, "request_adjustment": tool_adjust, "queue_quote_followup": tool_followup}


def parse_args(raw):
    if isinstance(raw, str):
        try:
            return json.loads(raw) or {}
        except ValueError:
            return {}
    return raw or {}


@router.post("/tools")
async def tools(request: Request):
    results = []
    try:
        payload = await request.json()
        msg = payload.get("message") or {}
        mode = os.environ.get("SIMULATE_MODE", "none")
        lead = await resolve_lead(msg)
        for tc in msg.get("toolCallList") or []:
            tid = tc.get("id", "")
            fn = tc.get("function") or tc
            try:
                if mode == "slow":
                    await asyncio.sleep(25)
                if mode == "error":
                    results.append({"toolCallId": tid, "error": "pricing service unavailable"})
                    continue
                handler = TOOLS.get(fn.get("name", ""))
                if not handler:
                    results.append({"toolCallId": tid, "error": f"Unknown tool: {fn.get('name')}"})
                    continue
                if not lead:
                    results.append({"toolCallId": tid, "error": "No active lead found for this call"})
                    continue
                out = await handler(lead, parse_args(fn.get("arguments")), mode)
                lead = await flow.get_lead(lead["id"])
                results.append({"toolCallId": tid, "result": json.dumps(out)})
            except Exception as e:
                logger.exception("tool failed")
                results.append({"toolCallId": tid, "error": f"tool failed: {e}"})
    except Exception as e:
        logger.exception("tool payload failed: %s", e)
    return JSONResponse({"results": results}, status_code=200)


def parse_transcript(msg):
    art = msg.get("artifact") or {}
    lines = []
    for m in art.get("messages") or msg.get("messages") or []:
        role = m.get("role")
        if role in ("assistant", "bot", "user"):
            lines.append({"role": "user" if role == "user" else "assistant",
                          "text": m.get("message") or m.get("content") or "", "at": iso()})
    if not lines and isinstance(art.get("transcript"), str):
        for raw in art["transcript"].splitlines():
            if ":" in raw:
                who, text = raw.split(":", 1)
                lines.append({"role": "user" if who.strip().lower() == "user" else "assistant", "text": text.strip(), "at": iso()})
    return lines


@router.post("/webhook")
async def webhook(request: Request):
    try:
        msg = (await request.json()).get("message") or {}
        if msg.get("type") == "end-of-call-report":
            lead = await resolve_lead(msg)
            if lead:
                await flow.end_call(lead, parse_transcript(msg))
    except Exception as e:
        logger.exception("webhook failed: %s", e)
    return JSONResponse({"received": True}, status_code=200)
