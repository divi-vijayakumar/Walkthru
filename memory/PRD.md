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
- Itemizer (backend/itemizer/, spec docs/itemizer-design.md) prices calls via Vapi tool update_scope (get_quote_estimate removed). KB in Mongo kb_tasks/kb_facts/kb_rules (rules incl. driver_* and measure_* docs), sessions in itemizer_sessions. LLM (Claude Opus 5.5) only maps words to task ids when no keyword matches; never prices. Range = 10% + 5% per assumed fact (max 25%). New quote version only when lines/total/range/assumptions change; camera goal results after pricing make a new version.
- Media store (backend/media/, collection media, files in Emergent object storage) and Percia (backend/percia/, collections percia_goals, percia_frames) talk only via HTTP APIs + in-process event media.stored. Service auth X-Walkthru-Key vs WALKTHRU_KEYS; Itemizer uses PERCIA_KEY; callbacks HMAC-SHA256 (X-Walkthru-Signature) with the creating key; Itemizer polls GET if a callback fails. judge_goal (percia/judge.py) is the only vision call: Gemini via Emergent key, VISION_MODEL=gemini-3.8-flash. ffmpeg from imageio-ffmpeg. Camera goals for facts at camera/show use the newest 2 clips; answer = hit label prefix ('floor: ...'); camera never overrides a said answer. Old frames collection dropped.
- update_scope ignores the tool's camera_on and uses the active call session's camera_on (set by portal /call/camera); the tool value is used only when there's no active session.
- Dashboard "Simulate" button (POST /api/dev/simulate-dhivya, admin): wipes Dhivya Vijayakumar's lead + calls, quotes, contracts, payments, followups, messages, itemizer data, media, Percia goals/frames, then re-adds her (name/phone/source/ask kept in meta.simulate_lead) so the agent re-invites her. No confirm, by owner's choice.
- Vapi dashboard must be updated by owner with the update_scope tool (docs/vapi-update-scope-tool.md).
- Old tests test_security_fixes.py and test_stripe_deposit.py are skipped because they call /api/dev/reset.
- Margin floor: estimated cost = 75% of list price; discount capped by max_discount_pct and min_margin_pct.
- Sign flow: "Sign contract" opens full contract (contract_sent), "Sign and continue" signs (pending_deposit) and texts deposit link.
- Recall quote -> quotes recalled, contract voided, status walkthru_completed, quote_pending 15 min.
- Chat mode uses the scripted (mock) agent with typed replies.

## Implemented
- 2026-10-24: v1 MVP (superseded).
- 2026-10-24: v2 full rebuild per designs: dashboard, /dev, portal, mock voice, Vapi adapter, tool + webhook endpoints, SMS simulate/allowlist.

- 2026-10-24: Stripe Checkout (claimable test sandbox) for the 5% deposit: /api/portal/{token}/deposit/checkout, /api/payments/status/{id}, /api/stripe/webhook; simulated /deposit/pay removed (dev advance still simulates). Tax mode: Stripe calculates only, falls back to no tax until a business address is set in Stripe.
- 2026-10-24: Emergent Google sign-in gates / and /dev and all contractor APIs; allow-list env OWNER_EMAILS=divi@velvee.ai; portal stays public.
- 2026-10-24: Twilio keys + SMS_ALLOWLIST (1 number) added; credentials verified (trial account, from-number on account). VAPI_PUBLIC_KEY + VAPI_ASSISTANT_ID added; VAPI_SERVER_SECRET added 2026-10-24 and verified (X-Vapi-Secret and Bearer accepted, missing secret rejected). VOICE_MODE switched to vapi 2026-10-24: real Vapi web call connected from the portal (captions arrived); full priced call on a phone not yet confirmed.
- 2026-10-24: Security audit fixes: /api/vapi/* require VAPI_SERVER_SECRET (X-Vapi-Secret/Bearer), mock agent uses token-scoped /api/portal/{token}/agent/tools|end; tool calls only during an active call; random portal tokens; CORS no credentials with wildcard; Origin check blocks cross-site writes on dashboard APIs; frame (300/call, 600k) and caption (400 lines) caps.

- 2026-10-24: Twilio WhatsApp channel (env MESSAGE_CHANNEL=whatsapp, TWILIO_WHATSAPP_FROM sandbox number). Real lead added: Dhivya Vijayakumar (Thumbtack, Bathroom remodel, (646) 238-0338); WhatsApp invite delivered (Twilio status read). Do NOT run /api/dev/reset or bump SEED_VERSION without asking: it wipes real leads.
- 2026-10-25: Itemizer built and tested (iterations 8-9 + 38/38 itemizer tests): all 6 acceptance gates pass; editable KB at /settings (Rate card and settings) with validation; confirm yes/no, step measuring, flooring de-dupe, water-damage assumption.
- 2026-10-25: Media store + Percia + hookup built and tested (iteration 10, 52/52 pytest incl. test_media_percia.py; E2E with owner's real bathroom video passes: vanity_mount floor seen -> Retile under old vanity). Camera icon on seen lines in portal + dashboard drawer; /dev 'Upload walkthrough video' (chunked). Retile rule: remove vanity + floor-standing + no new vanity/floor, or new floating vanity.
- 2026-10-25: Call fixes from real Vapi call (iteration 11 + 57/57 itemizer/call-fix tests + 14/14 media/Percia): max 5 questions per call, only priority-1 facts (auto: answer moves total >= $1,000; kb_facts.priority 1/2 overrides) block the price, facts moving < $300 never asked; wants_price / "quote|price|how much" prices at once; room-aware facts (no stairs/ceiling fans in bathrooms), one task per group (lighting, floor); unmatched work -> "To be priced by Apex: <words>" line with no amount; "new floating small vanity" resolved from what was said; camera-off skips to measure; camera numeric results and 0.5-0.75 results -> confirm; can't-know facts never asked; plain-sentence insights stored in itemizer_insights, delivered exactly once via portal poll (?live=1 -> vapi.send add-message / mock speaks) or update_scope. First portal clip 5 s; first camera finding measured at 21 s.
- 2026-10-25: Round 1 calls-first (iterations 12-14): 7-day week line + clickable filters, no live seeded calls, real leads first, Sessions page + call detail (transcript, signed recording, findings), Vapi end-of-call-report saves transcript/summary/recording, take-over, site-visit request/scheduling. Vapi call id now recorded at start (/api/portal/{token}/call/link + tool-calls/status-update with lead_token) and reports match by call id scoped to the lead.
- 2026-10-25: INCIDENT: a regression test called /api/dev/reset which wiped real leads. Fixed: reset_seed now deletes only sample data (lead id ^lead-) and keeps the contractor. Dhivya + Sathish restored as Invited with their original portal links (restored:true); their earlier calls/quotes/messages could not be recovered.
- P0: Round 2: Quotes page + backend PDF + portal download, Payments page, full Rate card/settings
- P0: Owner updates Vapi assistant tool to update_scope
- P1: Camera insights spoken in the live call (build step 3); live portal clip recording verified on a real phone call
- P1: Percia camera analysis + media store (build step 2), camera insights into live call (step 3)
- P1: Frame analysis to fill "What I'm seeing" chips (frames already stored)
- P1: Sessions / Quotes / Payments / Rate card pages
- P2: Real payments; contractor notifications on escalation
