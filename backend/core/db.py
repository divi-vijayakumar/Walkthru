import os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

CONTRACTOR_ID = "apex-remodeling"


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime = None) -> str:
    return (dt or now()).isoformat()


def portal_link(token: str) -> str:
    return f"{os.environ['PUBLIC_APP_URL'].rstrip('/')}/w/{token}"


async def get_contractor() -> dict:
    return await db.contractors.find_one({"id": CONTRACTOR_ID}, {"_id": 0})
