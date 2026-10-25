import os
import hmac
import hashlib
from fastapi import HTTPException, Request


def walkthru_keys():
    return [k.strip() for k in os.environ.get("WALKTHRU_KEYS", "").split(",") if k.strip()]


def key_id(key):
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def service_key(request: Request):
    """Returns the matching X-Walkthru-Key or None."""
    sent = request.headers.get("x-walkthru-key", "")
    return next((k for k in walkthru_keys() if sent and hmac.compare_digest(sent.encode(), k.encode())), None)


def require_service_key(request: Request):
    key = service_key(request)
    if not key:
        raise HTTPException(401, "Invalid or missing X-Walkthru-Key")
    return key


def sign(secret, raw: bytes):
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def app_url():
    return os.environ["PUBLIC_APP_URL"].rstrip("/")
