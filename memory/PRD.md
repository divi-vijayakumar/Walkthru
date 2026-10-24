# Walkthru — PRD

## Original problem statement
Build a web app called "Walkthru" with a React frontend and FastAPI backend with MongoDB. Tagline: "Walk through your project. Get your quote." This is a HACKATHON DEMO: prioritize a working, polished demo flow over production quality. No auth: hardcode a demo contractor.

Branding: use "Walkthru" in the sidebar header and page titles, with a simple wordmark (no logo image needed). Use a clean, modern, minimal design with one confident accent color.

Data models: contractors (name, rate_card JSON, min_margin_pct, max_discount_pct), leads (contractor_id, customer_name, phone, project_type, notes, video_url, status), scopes (lead_id, json, source), quotes (lead_id, version, line_items, subtotal, total, low, high, assumptions, change_summary, status), messages (lead_id, role, content, created_at).

Seed on startup: 1 contractor "Apex Remodeling" with a realistic rate card for bathroom remodels (demo, tile install per sqft, plumbing fixture swap, vanity install, painting, permit fees, labor hourly rate, material tiers economy/mid/premium, 15% markup, 10% contingency), min_margin_pct 18, max_discount_pct 6. Seed 3 leads: a bathroom remodel (hero lead, status "new"), a kitchen backsplash, and a deck repair. Use placeholder video URLs.

Frontend: a clean dashboard (sidebar + lead table with status badges) and a lead detail page with video player, notes, and empty panels for "Extracted Scope" and "Quote".

Done when: I can open the dashboard, see 3 leads, click into one and see its details.

User choices: construction orange accent; public sample MP4 clips that play; add status changer + message thread panel.

## Architecture
- Backend: FastAPI single file `/app/backend/server.py`, Motor/MongoDB, string ids, idempotent seed on startup (upsert by fixed ids).
- Endpoints: GET /api/contractor, GET /api/leads, GET /api/leads/{id} (lead+latest scope+latest quote+messages), PATCH /api/leads/{id}/status, GET/POST /api/leads/{id}/messages.
- Frontend: React Router (`/`, `/leads/:leadId`), dark theme, orange #F97316 accent, Outfit / Plus Jakarta Sans / JetBrains Mono.

## User personas
- Contractor (Apex Remodeling demo) reviewing customer video walkthroughs and quoting.

## Core requirements (static)
- Dashboard with sidebar + leads table + status badges
- Lead detail: video, notes, status, messages, empty Extracted Scope + Quote panels

## Implemented
- 2026-10-24: MVP: seed data, all endpoints, dashboard, lead detail, status changer, messages. Tested: backend 13/13, frontend flows pass. Video playback not verifiable in test browser (no H.264), URLs return video/mp4.

## Backlog
- P0: AI scope extraction from video into scopes collection
- P0: Quote generation from scope + rate card (markup, contingency, margin/discount guardrails), versioning
- P1: Customer-facing intake page for uploading walkthrough video
- P2: Rate card editor, quote PDF/share link

## Next tasks
- Scope extraction + quote generation for hero bathroom lead
