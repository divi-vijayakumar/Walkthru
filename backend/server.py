import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402
from core.db import client, db  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402
from core.seed import seed  # noqa: E402
from dashboard.routes import router as dashboard_router  # noqa: E402
from portal.routes import router as portal_router  # noqa: E402
from vapi.routes import router as vapi_router  # noqa: E402
from payments.routes import router as payments_router  # noqa: E402
from auth.routes import router as auth_router  # noqa: E402
from itemizer.routes import router as itemizer_router  # noqa: E402
from itemizer.kb import seed_kb  # noqa: E402
from itemizer import camera as itemizer_camera  # noqa: E402
from media.routes import router as media_router, dev_router as media_dev_router  # noqa: E402
from media import store as media_store  # noqa: E402
from percia.routes import router as percia_router  # noqa: E402
from calls.routes import router as calls_router, public_router as calls_public_router  # noqa: E402
from percia import worker as percia_worker  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

app = FastAPI(title="Walkthru")


@app.get("/api/health")
async def health():
    return {"ok": True, "app": "Walkthru"}


app.include_router(dashboard_router)
app.include_router(portal_router)
app.include_router(vapi_router)
app.include_router(payments_router)
app.include_router(auth_router)
app.include_router(itemizer_router)
app.include_router(itemizer_camera.callback_router)
app.include_router(media_router)
app.include_router(media_dev_router)
app.include_router(percia_router)
app.include_router(calls_router)
app.include_router(calls_public_router)

origins = [o.strip() for o in os.environ["CORS_ORIGINS"].split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_credentials="*" not in origins,  # never send credentials to a wildcard/reflected origin
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    await seed()
    await seed_kb()
    await media_store.init()
    await percia_worker.init()
    itemizer_camera.init()
    async for s in db.call_sessions.find({"id": {"$regex": "^session-lead-"}, "$or": [{"ended_at": None}, {"seeded": True}]}, {"_id": 0, "id": 1, "started_at": 1}):
        end = (datetime.fromisoformat(s["started_at"]) + timedelta(minutes=6)).isoformat()
        await db.call_sessions.update_one({"id": s["id"]}, {"$set": {"ended_at": end, "seeded": True}})


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
