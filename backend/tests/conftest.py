# Shared fixtures: Mongo-backed test sessions for the Emergent Google auth allow-list
import os
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
_db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
OWNER = "divi@velvee.ai"


def make_session(email, expired=False):
    user = _db.users.find_one({"email": email})
    created_user = False
    if not user:
        user = {"user_id": f"test-user-{uuid.uuid4().hex[:10]}", "email": email, "name": "TEST user",
                "picture": "", "created_at": datetime.now(timezone.utc)}
        _db.users.insert_one(dict(user))
        created_user = True
    token = f"test_session_{uuid.uuid4().hex}"
    delta = timedelta(days=-1) if expired else timedelta(days=7)
    _db.user_sessions.insert_one({"user_id": user["user_id"], "session_token": token,
                                  "expires_at": datetime.now(timezone.utc) + delta,
                                  "created_at": datetime.now(timezone.utc)})
    return token, user["user_id"], created_user


def session_exists(token):
    return _db.user_sessions.find_one({"session_token": token}) is not None


@pytest.fixture(scope="session")
def owner_token():
    token, uid, created = make_session(OWNER)
    yield token
    _db.user_sessions.delete_one({"session_token": token})
    if created:
        _db.users.delete_one({"user_id": uid})


@pytest.fixture(scope="session")
def outsider_token():
    email = f"test_outsider_{uuid.uuid4().hex[:6]}@example.com"
    token, uid, _ = make_session(email)
    yield token
    _db.user_sessions.delete_many({"user_id": uid})
    _db.users.delete_many({"email": {"$regex": "^test_outsider_"}})
