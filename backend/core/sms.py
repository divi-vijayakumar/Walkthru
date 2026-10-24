import os
import re
import asyncio
import logging
from core.db import db, iso

logger = logging.getLogger("sms")


def normalize(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10:
        return "+1" + digits
    return "+" + digits if digits else ""


async def send_sms(lead: dict, body: str, kind: str) -> dict:
    """Send a real SMS/WhatsApp only to allow-listed numbers when Twilio is configured; otherwise simulate."""
    to = normalize(lead.get("phone"))
    allow = {normalize(x) for x in os.environ.get("SMS_ALLOWLIST", "").split(",") if x.strip()}
    channel = os.environ.get("MESSAGE_CHANNEL", "sms")
    sender_key = "TWILIO_WHATSAPP_FROM" if channel == "whatsapp" else "TWILIO_FROM"
    sid, token, sender = (os.environ.get(k) for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", sender_key))
    result = {"to": to, "body": body, "kind": kind, "channel": channel, "sent": False, "simulated": True,
              "reason": "", "error": ""}
    if not (sid and token and sender):
        result["reason"] = "Twilio not configured"
    elif to not in allow:
        result["reason"] = "Number not on SMS allowlist"
    else:
        try:
            from twilio.rest import Client
            dest, src = (to, sender) if channel != "whatsapp" else (f"whatsapp:{to}", f"whatsapp:{normalize(sender)}")
            msg = await asyncio.to_thread(lambda: Client(sid, token).messages.create(to=dest, from_=src, body=body))
            result.update(sent=True, simulated=False, sid=msg.sid)
        except Exception as e:  # report, never crash the flow
            result.update(simulated=False, error=str(e)[:300])
    logger.info("%s %s to %s simulated=%s: %s", channel, kind, to, result["simulated"], body)
    await db.sms_log.insert_one({**result, "lead_id": lead["id"], "at": iso()})
    result.pop("_id", None)
    return result
