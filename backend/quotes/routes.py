"""Quotes page and quote PDFs (dashboard + homeowner portal)."""
import re
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from auth.routes import require_user
from core.db import db, get_contractor
from core.quotes import latest_quote
from core.quote_pdf import build_quote_pdf
from core import flow

router = APIRouter(prefix="/api", dependencies=[Depends(require_user)])
public_router = APIRouter(prefix="/api")
LEAD_FIELDS = {"_id": 0, "id": 1, "name": 1, "ask": 1, "status": 1}


async def pdf_response(quote, lead):
    contractor = await get_contractor()
    body = await asyncio.to_thread(build_quote_pdf, quote, lead, contractor)
    name = re.sub(r"[^A-Za-z0-9 ._-]", "", f"{contractor['name']} quote v{quote['version']} - {lead['name']}.pdf")
    return Response(body, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/quotes")
async def quotes():
    leads = {lead["id"]: lead async for lead in db.leads.find({}, LEAD_FIELDS)}
    docs = await db.quotes.find({"lead_id": {"$in": list(leads)}}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    newest = {}
    for q in docs:
        newest[q["lead_id"]] = max(newest.get(q["lead_id"], 0), q["version"])
    rows = [{"id": q["id"], "lead_id": q["lead_id"], "lead_name": leads[q["lead_id"]]["name"], "ask": leads[q["lead_id"]]["ask"],
             "lead_status": leads[q["lead_id"]]["status"], "sample": q["lead_id"].startswith("lead-"), "version": q["version"],
             "status": q["status"], "total": q["total"], "low": q["low"], "high": q["high"], "deposit_amount": q["deposit_amount"],
             "lines": len(q["line_items"]), "created_at": q["created_at"], "latest": q["version"] == newest[q["lead_id"]]}
            for q in docs]
    rows.sort(key=lambda r: r["sample"])
    current = [r for r in rows if r["latest"] and r["status"] != "recalled"]
    return {"quotes": rows, "totals": {
        "open": sum(r["total"] for r in current if r["status"] in ("live", "sent")),
        "accepted": sum(r["total"] for r in current if r["status"] == "accepted"),
        "count": len(current)}}


@router.get("/quotes/{quote_id}")
async def quote_detail(quote_id: str):
    q = await db.quotes.find_one({"id": quote_id}, {"_id": 0})
    if not q:
        raise HTTPException(404, "Quote not found")
    lead = await db.leads.find_one({"id": q["lead_id"]}, LEAD_FIELDS)
    versions = await db.quotes.find({"lead_id": q["lead_id"]}, {"_id": 0, "id": 1, "version": 1, "total": 1, "status": 1,
                                                                 "created_at": 1}).sort("version", -1).to_list(100)
    return {**q, "lead": lead, "versions": versions}


@router.get("/quotes/{quote_id}/pdf")
async def quote_pdf(quote_id: str):
    q = await db.quotes.find_one({"id": quote_id}, {"_id": 0})
    if not q:
        raise HTTPException(404, "Quote not found")
    return await pdf_response(q, await flow.get_lead(q["lead_id"]))


@public_router.get("/portal/{token}/quote.pdf")
async def portal_quote_pdf(token: str):
    lead = await flow.lead_by_token(token)
    q = await latest_quote(lead["id"])
    if not q:
        raise HTTPException(404, "No quote yet")
    return await pdf_response(q, lead)
