import os
import asyncio
import logging
import stripe
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from core.db import db, iso
from core.quotes import latest_quote
from core import flow

router = APIRouter(prefix="/api")
logger = logging.getLogger("payments")
stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
TAX_MODE = "calc_only"  # home-improvement deposit (not a digital good): Stripe calculates tax, contractor files


class CheckoutRequest(BaseModel):
    origin_url: str


def create_session(kwargs):
    if TAX_MODE == "calc_only":
        try:
            return stripe.checkout.Session.create(**kwargs, automatic_tax={"enabled": True},
                                                  billing_address_collection="required")
        except stripe.error.InvalidRequestError as e:
            # Stripe Tax isn't set up on the account yet (no business address): take the deposit without tax.
            logger.warning("automatic tax unavailable, creating session without it: %s", e.user_message)
    return stripe.checkout.Session.create(**kwargs)


async def finalize(session_id: str, payment_intent=None):
    res = await db.payment_transactions.update_one(
        {"session_id": session_id, "payment_status": {"$ne": "paid"}},
        {"$set": {"status": "completed", "payment_status": "paid", "stripe_payment_intent_id": payment_intent,
                  "updated_at": iso()}})
    if not res.modified_count:
        return
    tx = await db.payment_transactions.find_one({"session_id": session_id})
    lead = await db.leads.find_one({"id": tx["lead_id"]}, {"_id": 0})
    if lead and lead["status"] == "pending_deposit":
        await flow.pay_deposit(lead, method="stripe", reference=session_id)


@router.post("/portal/{token}/deposit/checkout")
async def deposit_checkout(token: str, body: CheckoutRequest, request: Request):
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    allowed = {f"https://{host}".rstrip("/"), os.environ["PUBLIC_APP_URL"].rstrip("/")}
    if body.origin_url.rstrip("/") not in allowed:
        raise HTTPException(400, "Checkout must start from this site")
    lead = await flow.lead_by_token(token)
    if lead["status"] != "pending_deposit":
        raise HTTPException(400, "No deposit is due")
    payment = await db.payments.find_one({"lead_id": lead["id"], "status": "pending", "void": {"$ne": True}}, {"_id": 0})
    quote = await latest_quote(lead["id"])
    contractor = await db.contractors.find_one({"id": lead["contractor_id"]}, {"_id": 0})
    if not payment or not quote:
        raise HTTPException(400, "No deposit is due")
    origin = body.origin_url.rstrip("/")
    kwargs = dict(
        mode="payment",
        line_items=[{"quantity": 1, "price_data": {
            "currency": "usd", "unit_amount": int(round(float(payment["amount"]) * 100)),
            "product_data": {"name": f"{quote['deposit_pct']}% deposit, {lead['ask']}",
                             "description": f"{contractor['name']} contract, quote v{quote['version']}"}}}],
        success_url=f"{origin}/w/{token}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{origin}/w/{token}?payment=cancelled",
        metadata={"lead_id": lead["id"], "payment_id": payment["id"]},
    )
    session = await asyncio.to_thread(create_session, kwargs)
    await db.payment_transactions.insert_one({
        "session_id": session.id, "lead_id": lead["id"], "payment_id": payment["id"],
        "amount": float(payment["amount"]), "currency": "usd", "status": "initiated", "payment_status": "pending",
        "created_at": iso(), "updated_at": iso()})
    return {"checkout_url": session.url, "session_id": session.id}


@router.get("/payments/status/{session_id}")
async def payment_status(session_id: str):
    record = await db.payment_transactions.find_one({"session_id": session_id})
    if not record:
        raise HTTPException(404, "Transaction not found")
    if record.get("payment_status") != "paid":
        try:
            s = await asyncio.to_thread(stripe.checkout.Session.retrieve, session_id)
            if s.payment_status == "paid":
                await finalize(session_id, s.payment_intent)
                record = await db.payment_transactions.find_one({"session_id": session_id})
            elif s.status == "expired":
                await db.payment_transactions.update_one({"session_id": session_id},
                                                         {"$set": {"status": "expired", "payment_status": "expired"}})
                record = await db.payment_transactions.find_one({"session_id": session_id})
        except stripe.error.StripeError:
            pass
    return {"session_id": record["session_id"], "status": record["status"], "payment_status": record["payment_status"]}


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, request.headers.get("stripe-signature", ""),
                                               os.environ.get("STRIPE_WEBHOOK_SECRET", ""))
    except (stripe.error.SignatureVerificationError, ValueError):
        raise HTTPException(400, "Invalid signature")
    obj, t = event["data"]["object"], event["type"]
    if t in ("checkout.session.completed", "checkout.session.async_payment_succeeded") and obj.get("payment_status") == "paid":
        await finalize(obj["id"], obj.get("payment_intent"))
    elif t == "checkout.session.async_payment_failed":
        await db.payment_transactions.update_one({"session_id": obj["id"]},
                                                 {"$set": {"status": "failed", "payment_status": "failed", "updated_at": iso()}})
    elif t == "checkout.session.expired":
        await db.payment_transactions.update_one({"session_id": obj["id"], "payment_status": {"$ne": "paid"}},
                                                 {"$set": {"status": "expired", "payment_status": "expired", "updated_at": iso()}})
    elif t == "charge.refunded":
        await db.payment_transactions.update_one({"stripe_payment_intent_id": obj.get("payment_intent")},
                                                 {"$set": {"status": "refunded", "payment_status": "refunded", "updated_at": iso()}})
    return {"status": "ok"}
