import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402
from core.db import client  # noqa: E402
from core.seed import seed  # noqa: E402
from dashboard.routes import router as dashboard_router  # noqa: E402
from portal.routes import router as portal_router  # noqa: E402
from vapi.routes import router as vapi_router  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

app = FastAPI(title="Walkthru")


@app.get("/api/health")
async def health():
    return {"ok": True, "app": "Walkthru"}


app.include_router(dashboard_router)
app.include_router(portal_router)
app.include_router(vapi_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    await seed()


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
