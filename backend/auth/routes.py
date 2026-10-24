import os
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
import requests
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from core.db import db

router = APIRouter(prefix="/api/auth")
SESSION_DATA_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
SESSION_DAYS = 7


class SessionIn(BaseModel):
    session_id: str


def allowed_emails():
    return {e.strip().lower() for e in os.environ["OWNER_EMAILS"].split(",") if e.strip()}


def public_user(user):
    return {k: user.get(k) for k in ("user_id", "email", "name", "picture")}


async def session_user(token):
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0}) if token else None
    if not session:
        return None, None
    expires_at = session["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None, "Session expired"
    return await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0}), None


def same_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return True
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    return origin.split("://", 1)[-1].rstrip("/") == host


async def require_user(request: Request) -> dict:
    if request.method not in ("GET", "HEAD", "OPTIONS") and not same_origin(request):
        raise HTTPException(403, "Cross-site request blocked")
    auth = request.headers.get("authorization", "")
    bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else None
    user, problem = await session_user(request.cookies.get("session_token"))
    if not user and bearer:
        user, problem = await session_user(bearer)
    if not user:
        raise HTTPException(401, problem or "Sign in required")
    if user["email"].lower() not in allowed_emails():
        raise HTTPException(403, "This account doesn't have access")
    return user


@router.post("/session")
async def create_session(body: SessionIn, response: Response):
    r = await asyncio.to_thread(requests.get, SESSION_DATA_URL, headers={"X-Session-ID": body.session_id}, timeout=15)
    if r.status_code != 200:
        raise HTTPException(401, "Google sign-in failed. Please try again.")
    data = r.json()
    email = (data.get("email") or "").lower()
    if email not in allowed_emails():
        raise HTTPException(403, f"{email} doesn't have access to this dashboard.")
    now = datetime.now(timezone.utc)
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if user:
        await db.users.update_one({"email": email}, {"$set": {"name": data.get("name"), "picture": data.get("picture")}})
        user.update(name=data.get("name"), picture=data.get("picture"))
    else:
        user = {"user_id": f"user_{uuid.uuid4().hex[:12]}", "email": email, "name": data.get("name"),
                "picture": data.get("picture"), "created_at": now}
        await db.users.insert_one(dict(user))
    token = data["session_token"]
    await db.user_sessions.insert_one({"user_id": user["user_id"], "session_token": token,
                                       "expires_at": now + timedelta(days=SESSION_DAYS), "created_at": now})
    response.set_cookie("session_token", token, max_age=SESSION_DAYS * 86400, httponly=True, secure=True,
                        samesite="none", path="/")
    return public_user(user)


@router.get("/me")
async def me(request: Request):
    return public_user(await require_user(request))


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/", secure=True, samesite="none")
    return {"ok": True}
