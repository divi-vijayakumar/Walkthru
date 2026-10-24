from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal, Any
import uuid
from datetime import datetime, timezone, timedelta

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEMO_CONTRACTOR_ID = "apex-remodeling"
LeadStatus = Literal["new", "in_review", "quoted", "archived"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BaseDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    def to_mongo(self) -> dict:
        return self.model_dump()

    @classmethod
    def from_mongo(cls, doc: Optional[dict]):
        if not doc:
            return None
        doc.pop("_id", None)
        return cls(**doc)


class Contractor(BaseDocument):
    name: str
    rate_card: dict
    min_margin_pct: float
    max_discount_pct: float


class Lead(BaseDocument):
    contractor_id: str
    customer_name: str
    phone: str
    project_type: str
    notes: str = ""
    video_url: str = ""
    status: LeadStatus = "new"
    created_at: str = Field(default_factory=now_iso)


class Scope(BaseDocument):
    lead_id: str
    json: Any = None
    source: str = ""
    created_at: str = Field(default_factory=now_iso)


class Quote(BaseDocument):
    lead_id: str
    version: int = 1
    line_items: list = []
    subtotal: float = 0
    total: float = 0
    low: float = 0
    high: float = 0
    assumptions: list = []
    change_summary: str = ""
    status: str = "draft"
    created_at: str = Field(default_factory=now_iso)


class Message(BaseDocument):
    lead_id: str
    role: Literal["customer", "contractor", "system"]
    content: str
    created_at: str = Field(default_factory=now_iso)


class StatusUpdate(BaseModel):
    status: LeadStatus


class MessageCreate(BaseModel):
    role: Literal["customer", "contractor"] = "contractor"
    content: str = Field(min_length=1, max_length=4000)


class LeadDetail(BaseModel):
    lead: Lead
    scope: Optional[Scope] = None
    quote: Optional[Quote] = None
    messages: List[Message] = []


RATE_CARD = {
    "currency": "USD",
    "project_type": "Bathroom Remodel",
    "labor_hourly_rate": 85,
    "markup_pct": 15,
    "contingency_pct": 10,
    "line_items": {
        "demo": {"label": "Demolition & haul-away", "unit": "sqft", "rate": 6.5, "labor_hours_per_unit": 0.08},
        "tile_install": {"label": "Tile install (floor & wall)", "unit": "sqft", "rate": 14.0, "labor_hours_per_unit": 0.15},
        "plumbing_fixture_swap": {"label": "Plumbing fixture swap", "unit": "each", "rate": 325.0, "labor_hours_per_unit": 2.5},
        "vanity_install": {"label": "Vanity install", "unit": "each", "rate": 650.0, "labor_hours_per_unit": 4.0},
        "painting": {"label": "Interior painting", "unit": "sqft", "rate": 3.25, "labor_hours_per_unit": 0.03},
        "permit_fees": {"label": "Permit fees", "unit": "flat", "rate": 450.0, "labor_hours_per_unit": 0},
    },
    "material_tiers": {
        "economy": {"label": "Economy", "tile_per_sqft": 3.5, "vanity": 450, "fixture_each": 180, "paint_per_gallon": 32},
        "mid": {"label": "Mid-range", "tile_per_sqft": 7.0, "vanity": 1100, "fixture_each": 380, "paint_per_gallon": 55},
        "premium": {"label": "Premium", "tile_per_sqft": 15.0, "vanity": 2600, "fixture_each": 850, "paint_per_gallon": 85},
    },
}


def seed_leads() -> List[Lead]:
    now = datetime.now(timezone.utc)
    return [
        Lead(
            id="lead-bathroom-001", contractor_id=DEMO_CONTRACTOR_ID, customer_name="Sarah Mitchell",
            phone="(555) 214-8830", project_type="Bathroom Remodel", status="new",
            notes="Hall bathroom, roughly 8x10. Wants the old tub/shower combo torn out, new tile floor and shower walls, "
                  "a 48\" vanity, swap the toilet and faucet, and fresh paint. Leaning toward mid-range finishes. "
                  "Hoping to start within 6 weeks.",
            video_url="https://download.samplelib.com/mp4/sample-10s.mp4",
            created_at=(now - timedelta(hours=2)).isoformat(),
        ),
        Lead(
            id="lead-backsplash-002", contractor_id=DEMO_CONTRACTOR_ID, customer_name="Daniel Ortiz",
            phone="(555) 387-1902", project_type="Kitchen Backsplash", status="in_review",
            notes="About 30 sq ft of backsplash behind the counters and range. Wants white subway tile with dark grout. "
                  "Existing drywall is in good shape.",
            video_url="https://download.samplelib.com/mp4/sample-5s.mp4",
            created_at=(now - timedelta(days=1, hours=4)).isoformat(),
        ),
        Lead(
            id="lead-deck-003", contractor_id=DEMO_CONTRACTOR_ID, customer_name="Priya Raman",
            phone="(555) 940-5527", project_type="Deck Repair", status="quoted",
            notes="12x16 back deck. Several soft boards near the stairs, one wobbly railing section. "
                  "Would like it re-stained after repairs.",
            video_url="https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
            created_at=(now - timedelta(days=3, hours=1)).isoformat(),
        ),
    ]


async def seed():
    contractor = Contractor(id=DEMO_CONTRACTOR_ID, name="Apex Remodeling", rate_card=RATE_CARD,
                            min_margin_pct=18, max_discount_pct=6)
    await db.contractors.update_one({"id": contractor.id}, {"$setOnInsert": contractor.to_mongo()}, upsert=True)
    for lead in seed_leads():
        await db.leads.update_one({"id": lead.id}, {"$setOnInsert": lead.to_mongo()}, upsert=True)
    if await db.messages.count_documents({"lead_id": "lead-bathroom-001"}) == 0:
        base = datetime.now(timezone.utc) - timedelta(hours=2)
        for i, (role, content) in enumerate([
            ("customer", "Hi! I just recorded a quick walkthrough of our hall bathroom. Let me know if you need more angles."),
            ("contractor", "Thanks Sarah, got it. We'll review the video and get a scope and ballpark quote back to you shortly."),
        ]):
            msg = Message(lead_id="lead-bathroom-001", role=role, content=content,
                          created_at=(base + timedelta(minutes=5 * (i + 1))).isoformat())
            await db.messages.insert_one(msg.to_mongo())
    logger.info("Seed complete")


async def get_lead_or_404(lead_id: str) -> Lead:
    lead = Lead.from_mongo(await db.leads.find_one({"id": lead_id, "contractor_id": DEMO_CONTRACTOR_ID}))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@api_router.get("/")
async def root():
    return {"app": "Walkthru", "tagline": "Walk through your project. Get your quote."}


@api_router.get("/contractor", response_model=Contractor)
async def get_contractor():
    return Contractor.from_mongo(await db.contractors.find_one({"id": DEMO_CONTRACTOR_ID}))


@api_router.get("/leads", response_model=List[Lead])
async def list_leads():
    docs = await db.leads.find({"contractor_id": DEMO_CONTRACTOR_ID}).sort("created_at", -1).to_list(500)
    return [Lead.from_mongo(d) for d in docs]


@api_router.get("/leads/{lead_id}", response_model=LeadDetail)
async def get_lead(lead_id: str):
    lead = await get_lead_or_404(lead_id)
    scope = await db.scopes.find_one({"lead_id": lead_id}, sort=[("created_at", -1)])
    quote = await db.quotes.find_one({"lead_id": lead_id}, sort=[("version", -1)])
    msgs = await db.messages.find({"lead_id": lead_id}).sort("created_at", 1).to_list(500)
    return LeadDetail(lead=lead, scope=Scope.from_mongo(scope), quote=Quote.from_mongo(quote),
                      messages=[Message.from_mongo(m) for m in msgs])


@api_router.patch("/leads/{lead_id}/status", response_model=Lead)
async def update_status(lead_id: str, body: StatusUpdate):
    await get_lead_or_404(lead_id)
    await db.leads.update_one({"id": lead_id}, {"$set": {"status": body.status}})
    return await get_lead_or_404(lead_id)


@api_router.get("/leads/{lead_id}/messages", response_model=List[Message])
async def list_messages(lead_id: str):
    await get_lead_or_404(lead_id)
    msgs = await db.messages.find({"lead_id": lead_id}).sort("created_at", 1).to_list(500)
    return [Message.from_mongo(m) for m in msgs]


@api_router.post("/leads/{lead_id}/messages", response_model=Message)
async def create_message(lead_id: str, body: MessageCreate):
    await get_lead_or_404(lead_id)
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Message cannot be empty")
    msg = Message(lead_id=lead_id, role=body.role, content=content)
    await db.messages.insert_one(msg.to_mongo())
    return msg


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    await seed()


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
