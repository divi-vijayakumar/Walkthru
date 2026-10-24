# Walkthru — PRD

## Original problem statement (latest, v2)
Build "Walkthru" as ONE app (React frontend, FastAPI backend, MongoDB). HACKATHON DEMO: a polished, working demo flow beats production quality. Attached: design images for the contractor dashboard and a 3-screen mobile homeowner portal, and mock_tool_server.py (pricing logic to port). Match the designs closely.
Design tokens: Bricolage Grotesque (headings), Manrope (body). Ink #0E1726, ground #F5F6F8, card #FFFFFF, border #E3E7ED, muted #5B6577, accent #C2410C, accent-soft #FDEBDD, teal #0F766E, call bg #0B1220. 44px+ targets, 4.5:1 contrast, no emoji.
Status model (event-driven via set_status only): new, invited, walkthru_initiated, walkthru_completed, quote_generated, contract_sent, pending_deposit, deposit_received (+ dropped, escalated flag, quote_pending flag). Fixed pill colors.
Data: contractors, leads, call_sessions, quotes, contracts, payments. Seed Apex Remodeling + 9 leads, "Sample data" chip.
Part A dashboard (/): sidebar, agentic switch, funnel strip + median time to quote, filterable table, lead drawer (on-call card, journey, take over, transcript, recall quote), 3s polling with toasts, quote-pending countdown, Start agent SMS (Twilio, allowlist, simulate), /dev helper.
Part B portal (/w/{token}): welcome, call screen (camera off by default, frames every 2s, live estimate), quote+contract, sign, simulated deposit, fallback screen; voice_adapter with MOCK (default) and VAPI; /api/vapi/tools (always 200) + /api/vapi/webhook; SMS #2; SIMULATE_MODE.
(v1 original: simple Walkthru dashboard + lead detail; superseded.)

## Architecture
- backend/server.py (entry, /api/health), core/ (db, status.set_status, sms, quotes, flow services, seed), pricing/engine.py (port of mock_tool_server), dashboard/routes.py (+ /api/dev/*), portal/routes.py, vapi/routes.py
- frontend/src/shared, dashboard/, portal/ (voice/ adapters: mockAdapter, vapiAdapter, scripts)
- Env: PUBLIC_APP_URL, VOICE_MODE (mock|vapi), SIMULATE_MODE, optional TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_FROM, SMS_ALLOWLIST, VAPI_PUBLIC_KEY, VAPI_ASSISTANT_ID

## Key decisions
- Quote made during a live call stays "live" (status walkthru_initiated); on call end -> walkthru_completed -> quote_generated + SMS #2.
- get_quote_estimate re-run keeps version counter per lead; pricing state stored per lead (pricing_states).
- Margin floor: estimated cost = 75% of list price; discount capped by max_discount_pct and min_margin_pct.
- Sign flow: "Sign contract" opens full contract (contract_sent), "Sign and continue" signs (pending_deposit) and texts deposit link.
- Recall quote -> quotes recalled, contract voided, status walkthru_completed, quote_pending 15 min.
- Chat mode uses the scripted (mock) agent with typed replies.

## Implemented
- 2026-10-24: v1 MVP (superseded).
- 2026-10-24: v2 full rebuild per designs: dashboard, /dev, portal, mock voice, Vapi adapter, tool + webhook endpoints, SMS simulate/allowlist.

- 2026-10-24: Stripe Checkout (claimable test sandbox) for the 5% deposit: /api/portal/{token}/deposit/checkout, /api/payments/status/{id}, /api/stripe/webhook; simulated /deposit/pay removed (dev advance still simulates). Tax mode: Stripe calculates only, falls back to no tax until a business address is set in Stripe.
- 2026-10-24: Emergent Google sign-in gates / and /dev and all contractor APIs; allow-list env OWNER_EMAILS=divi@velvee.ai; portal stays public.
- 2026-10-24: Twilio keys + SMS_ALLOWLIST (1 number) added; credentials verified (trial account, from-number on account). VAPI_PUBLIC_KEY + VAPI_ASSISTANT_ID added; VAPI_SERVER_SECRET added 2026-10-24 and verified (X-Vapi-Secret and Bearer accepted, missing secret rejected). VOICE_MODE still mock, so voice stays scripted until set to vapi.
- 2026-10-24: Security audit fixes: /api/vapi/* require VAPI_SERVER_SECRET (X-Vapi-Secret/Bearer), mock agent uses token-scoped /api/portal/{token}/agent/tools|end; tool calls only during an active call; random portal tokens; CORS no credentials with wildcard; Origin check blocks cross-site writes on dashboard APIs; frame (300/call, 600k) and caption (400 lines) caps.

## Backlog
- P1: Frame analysis to fill "What I'm seeing" chips (frames already stored)
- P1: Sessions / Quotes / Payments / Rate card pages
- P2: Real payments; contractor notifications on escalation
