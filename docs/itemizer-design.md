# Walkthru Itemizer design

Oct 24, 2026 · @Divi

The Itemizer turns what the homeowner says into priced items, and fills each item's unknowns by asking Percia (camera, async) first and the homeowner (through Alex, live) only for things they can actually answer. This file is the spec and knowledge base for the Itemizer, Percia and Alex. All prices are placeholders.

## How the three parts talk

```text
LIVE (in the call)
  Homeowner's phone  <--voice-->  Alex (Vapi)  --update_scope-->  Itemizer (backend)
                                               <--next_action---
ASYNC (background, 5 to 30 s)
  Homeowner's phone --camera clips--> Media store --clip URLs--> Percia
  Itemizer --goals--> Percia --results--> Itemizer
  Itemizer --insights (via the portal, injected into the live call)--> Alex
```

Alex never waits on the camera. Each time the homeowner describes work, Alex calls update\_scope; the Itemizer sends camera goals to Percia and hands Alex the next thing to ask. Percia's results come back as insights that the portal slips into the live call, and Alex mentions them at the next pause.

## Worked example: "I want this sink gone"

The camera answers the floating-or-floor question while Alex keeps talking about things only the homeowner knows, and the answer adds retiling to the quote.

| # | Who | What happens | Live or async |
| --- | --- | --- | --- |
| 1 | Homeowner | "I want this sink gone." (camera on, pointed at the vanity) | live |
| 2 | Alex → Itemizer | update\_scope with said = "I want this sink gone", room bathroom | live, \~1 s |
| 3 | Itemizer | Matches "sink gone" in a bathroom to item Remove vanity. Opens facts: sinks (camera first), vanity\_mount (camera first), replacing it? (ask) | live |
| 4 | Itemizer → Percia | Sends two goals on the last clips: "How many sinks does the vanity have?" and "Does the vanity sit on the floor, or hang on the wall with open floor beneath?" | async |
| 5 | Itemizer → Alex | next\_action = ask "Are you putting a new vanity there, or leaving the space open?" (camera facts are skipped while Percia works) | live |
| 6 | Homeowner | "A new floating one, a bit wider." Alex sends that answer; Itemizer adds New vanity (floating) | live |
| 7 | Percia → Itemizer | \~10 to 20 s later: one sink (0.91), sits on the floor (0.88), each with a frame | async |
| 8 | Itemizer | Floor-standing vanity out, floating vanity in, no new floor in scope: adds "Retile under old vanity" ($650). Queues an insight | async |
| 9 | Portal → Alex | Injects the insight into the live call: "Camera: single-sink vanity sitting on the floor; tile under it needs patching (+$650)." | async, \~1.5 s |
| 10 | Alex | At the next pause: "I can see the old vanity sits right on the floor, so I've included patching the tile under it." | live |

**If the camera can't tell** (Percia returns not\_found or ambiguous): with the camera on, Alex asks once to show it ("Could you point the camera at the bottom of the vanity for a second?"); with it off, Alex asks in plain words ("Does it sit right on the floor, or hang on the wall with space underneath?"). If neither works, the Itemizer assumes floor, lists it on the quote, and widens the range.

## How a fact gets answered

Every fact in the knowledge base has a ladder: the channels to try, in order. The Itemizer walks it and never asks the homeowner something the camera already answered or that they can't know.

| Channel | Who answers | Speed | Example |
| --- | --- | --- | --- |
| Camera | Percia, on clips already recorded | async, 5 to 30 s | Vanity sits on the floor |
| Show | Alex asks the homeowner to point the camera; Percia answers | async after the request | "Could you show me the range hood for a second?" |
| Ask | The homeowner, in plain words | live | "Is your stove gas or electric?" |
| Measure | Percia counts tiles or uses objects of known size; or the homeowner counts steps or uses a tape | mixed | 9 tiles x 12 in by 7 tiles x 12 in = about 63 sq ft |
| Assume | The knowledge base default, listed on the quote | instant | One layer of old flooring |
| Site visit | Nobody can know until walls or floors are opened | never in the call | Rot under the subfloor: allowance only |

**Ask only what the homeowner can answer.**

| Ask them | Show the camera instead | Neither: assume and flag for the site visit |
| --- | --- | --- |
| What they want, finish level, budget, timeline | Product types that need an expert eye: hood type (chimney, under-cabinet, microwave, downdraft), tub type, cabinet construction, countertop material | What's inside walls (wiring, pipes, rot) |
| Things they use daily: gas or electric stove, does the fan blow outside | Condition: stains, swelling, cracks, mold | Whether a wall is load-bearing (infer from clues, confirm on site) |
| History: leaks, past work, year the house was built | Counts and sizes: tiles, cabinets, outlets, windows | Asbestos or lead (test if age and clues point to it) |
| What's above or below: floor above, basement or crawlspace | Locations: where outlets, vents and shutoffs are | Subfloor condition beyond what's visible |
| Who lives there, will they live in during work | Panel label (amps) when power needs grow |  |

**Plain-words fallback:** if a show request fails, turn the expert question into one they can see and answer. Not "Is it a downdraft?" but "Does the fan sit above the stove, or pop up from the cooktop?"

## Conversation rules for Alex

The call should feel like a friendly contractor walking the room, not a form.

1. Start with what they want, room by room. One question per turn; acknowledge the answer before the next.
2. Never wait in silence for the camera. While Percia works, talk about things only the homeowner knows: plans, preferences, history, timeline.
3. Never ask what the camera or an earlier answer already settled. Confirm only findings Percia marks ambiguous: "I can see two sinks. Is that right?"
4. Camera requests are short, specific and optional: one at a time, at most three a call, and only while the camera is on. If it's off, offer once to turn it on, then fall back to plain questions.
5. Say what you saw, briefly, when it matters: "I can see the vanity sits on the floor." It builds trust and explains the price.
6. When something changes the budget, say why in one sentence: "Moving the sink means new plumbing, so that adds about $1,500."
7. Measurements are a favour, not a requirement: "If it's easy, walk along the longest wall and count your steps." Skip it if they hesitate.
8. Summarize the scope in two sentences before pricing. Speak only numbers from the tool.
9. If a camera finding arrives after the price, the Itemizer makes a new version; mention the change at the next natural pause.

## Knowledge base: kitchen

Each task lists the facts it needs and each fact's ladder (camera, show, ask, measure, assume), the rules that add or change items, and a starter price. **All prices are placeholders** until Apex's rate card replaces them; three values are refresh / standard / premium.

| Task | Facts it needs (ladder) | Rules that add or change items | Starter price |
| --- | --- | --- | --- |
| Cabinets: replace, reface or paint | Which of the three (ask); cabinet length in linear ft (camera counts boxes, using 24 in deep and 34.5 in tall base cabinets for scale, then measure); uppers to the ceiling (camera) | Layout change moves plumbing or gas (see whole-house) | replace $350 / $550 / $900 per linear ft; reface $220; paint $120 |
| Countertops | Current material (camera: laminate, tile, stone, quartz); new material (ask); area (measure: cabinet length x 25.5 in, plus island); undermount sink (ask) | Stone or tile removal costs more than laminate | install $45 / $75 / $120 per sq ft; removal laminate $5, stone or tile $10 per sq ft |
| Backsplash | Existing backsplash (camera); area (measure: counter length x 1.5 ft) | none | $30 / $45 / $75 per sq ft installed |
| Sink and faucet | Bowls (camera); moving the sink (ask) | Moving it adds Move plumbing | $650 / $1,100 / $2,000 |
| Range or cooktop | Fuel now: gas, electric or induction (ask); fuel wanted (ask) | Gas to electric or induction adds a 240 V circuit ($900); electric to gas adds a gas line ($1,200) | install $250 |
| Range hood | Type: chimney, under-cabinet, microwave, downdraft, none (camera, then show "Could you show me the hood above the stove?", then plain ask); vents outside (show the top or ask "Does it blow air outside?") | Adding outside venting $1,200; replacing a downdraft $800 extra | install $450 + hood $300 / $800 / $2,000 |
| Island | Add, remove or change (ask); needs water or power (ask) | Water adds Move plumbing; power adds a circuit ($450) | cabinets by linear ft + countertop by sq ft |
| Dishwasher and appliances | Existing dishwasher (camera); appliances to install (ask) | New dishwasher where there was none: plumbing, power and cabinet change ($900) | $250 per appliance |
| Lighting | Existing fixtures (camera); new recessed lights wanted (ask); attic or floor above (ask) | Floor above with no attic access: +$100 per light | $250 per recessed light; pendant $350 + fixture |
| Flooring | See living rooms; same facts and prices | none | see living rooms |

## Knowledge base: bathroom

Same prices as the runbook's Step 8 pricing sheet, now written as ladders.

| Task | Facts it needs (ladder) | Rules that add or change items | Starter price |
| --- | --- | --- | --- |
| Remove vanity | Sinks: one or two (camera, then ask); mount: floor or floating (camera, then show the bottom of the vanity, then ask, then assume floor) | Floor-standing and no new floor in scope: add Retile under old vanity ($650) | single $350; double $550 |
| New vanity | Sinks (ask); floating or floor (ask); finish (ask) | Wider than the old one with no new floor: add Retile under old vanity | install single $650, double $950; vanity and top single $900 / $1,800 / $3,500, double $1,600 / $3,200 / $6,000; faucet per sink $250 / $450 / $800 |
| Remove tub | Type: alcove, freestanding, drop-in (camera, then ask) | Cast iron (ask "Is it a heavy metal tub?", or show the edge): +$300 | alcove $650; freestanding $350; drop-in $900 |
| Walk-in shower | Size vs the old tub (ask); glass door, panel or curtain (ask); niche (ask); curbless (ask) | Always adds Permit; curbless +$1,800 | build $6,800 standard size, $8,900 large; tile $900 / $1,800 / $3,600; glass door $1,900, panel $1,200; niche $450; fixtures $350 / $700 / $1,500 |
| Toilet | Moving it (ask) | Moving it adds Move plumbing | install $450 + toilet $300 / $550 / $1,100 |
| Floor tile | Current floor (camera: vinyl, tile, wood); area (measure: tile count first) | Tile removal costs more than vinyl | per sq ft: removal vinyl $2, tile $4; install $12; tile $4 / $8 / $15 |
| Wall tile | Height: wainscot or to the ceiling (ask); area (measure: wall length x height, from the door for scale) | none | $18 / $28 / $45 per sq ft |
| Exhaust fan and lights | Fan exists (camera); vents outside (ask); new lights (ask) | No fan: $650; fan that doesn't vent outside: +$400 duct | light $225 + fixture $150 / $300 / $600 |
| Heated floor | Wanted (ask) | Adds a circuit if the panel is full (see whole-house) | $1,600 |
| Safety and access | Grab bars (ask); bench (ask) | none | grab bar $250 each; bench $650 |

## Knowledge base: living rooms and bedrooms

| Task | Facts it needs (ladder) | Rules that add or change items | Starter price |
| --- | --- | --- | --- |
| Flooring | Current floor (camera: carpet, hardwood, tile, vinyl, laminate); new floor (ask); area (measure); stairs (camera counts, then ask) | Tile or glued-down floor removal costs more; stairs priced per step | installed per sq ft: vinyl plank $7 / $9 / $12, hardwood $12 / $16 / $22, carpet $5 / $7 / $10; removal carpet $1, tile $4, glued wood $3; stairs $150 per step |
| Paint | Walls, ceilings or both (ask); wall area (measure: room perimeter x ceiling height, minus doors and windows); ceiling height (measure: door is 80 in for scale); dark to light color (camera, then ask) | Dark to light adds a coat (+25%); cracks or patches add Drywall repair | walls $3 / $4 / $5 per sq ft; ceilings $2 per sq ft |
| Drywall repair and textured ceiling | Cracks or holes (camera); textured "popcorn" ceiling (camera) | Popcorn ceiling in a house built before 1980: add Asbestos test first | patch $250 per area; popcorn removal $3.50 per sq ft |
| Trim and baseboards | Replacing (ask); length (measure: room perimeter) | none | $8 / $12 / $18 per linear ft |
| Windows | Count (camera); size (measure against the door); type wanted (ask) | none | $700 / $1,100 / $1,800 each |
| Interior doors | Count (camera); style wanted (ask) | none | $450 / $700 / $1,100 each |
| Fireplace | Wood or gas (ask, camera confirms); reface material (ask) | Converting wood to gas adds a gas line | reface $2,500 / $4,500 / $8,000 |
| Lighting and ceiling fans | Existing fixtures (camera); new lights or fans (ask); attic or floor above (ask) | Floor above with no attic access: +$100 per light | recessed $250 each; fan $350 + fixture |
| Built-ins | Wanted (ask); wall length (measure) | none | $600 / $900 / $1,400 per linear ft |

## Knowledge base: whole-house and common items

These are added by rules, not by the homeowner asking for them.

| Item | When it's added | Facts it needs (ladder) | Starter price |
| --- | --- | --- | --- |
| Protection and cleanup | Every quote, per room | none | $450 per room |
| Demolition and haul-away | Any removal task | Scope size (from items) | $650 for one room; $1,200 for two or more |
| Permit | Plumbing, electrical, gas, structural or shower work | none | $450 each trade |
| Move plumbing | A sink, toilet, shower or dishwasher moves | Fixtures moved (ask); what's below: slab, crawlspace or basement (ask) | per fixture: crawlspace or basement $1,500, slab $3,000 |
| Gas line | Electric to gas range, wood to gas fireplace, moving a gas appliance | Gas at the house already (ask) | $1,200 run; $2,500 if no gas service |
| New circuit | Induction range, heated floor, island power, new appliance | Panel amps and free spaces (show the panel label) | $450 per 120 V circuit; $900 per 240 V circuit |
| Panel upgrade | New circuits needed and the panel is 100 A or full (camera on the panel) | Panel label (show) | $2,500 allowance |
| Wall removal | Homeowner wants a wall gone | Floor above (ask); a beam or posts nearby (camera); outlets, switches or vents in the wall (camera). Never ask "Is it load-bearing?" | not likely load-bearing $2,500; likely load-bearing: engineer $800 + beam allowance $6,000; +$800 per utility in the wall |
| HVAC vent move | A vent sits where a cabinet, wall or tub goes (camera) | none | $450 per vent |
| Asbestos test | House built before 1980 (ask) and popcorn ceiling or 9 in tiles seen (camera) | none | $400; abatement priced after results |
| Lead-safe work | House built before 1978 (ask) and painted surfaces are disturbed | none | $600 per job |

## Budget drivers

These move the price on any room. Alex checks each one that applies to the items in scope, cheapest channel first.

| Driver | How we find out | Effect on the quote |
| --- | --- | --- |
| Water damage, leaks, mold | Camera watches for stains, swelling, peeling paint and mold on every call; ask "Any leaks or soft spots you've noticed?" | Water damage allowance $1,800, listed as an assumption until the site visit |
| What's on the floor now | Camera identifies it; assume one layer (people rarely know) | Removal price per sq ft by type; tile over tile raises removal |
| Plumbing or gas moves | Ask "Do you want the sink in the same spot?"; ask what's below | Move plumbing or Gas line items |
| Power needs | Ask what appliances are coming; show the panel label if heavy loads are added | New circuit or Panel upgrade items |
| House age | Ask "Roughly when was the house built?" | Before 1978: lead-safe work; before 1980 with popcorn ceilings or 9 in tiles: asbestos test |
| Walls coming out | Ask about the floor above; camera looks for beams and utilities | Wall removal item; engineer if likely load-bearing |
| Room size | Measure (next section) | Every per-sq-ft and per-linear-ft line; uncertainty widens the range |
| Ceiling height | Measure from the door (80 in) | Wall tile, paint and to-ceiling cabinet quantities |
| Access | Ask which floor and whether there's an elevator or tight stairs | +5% labor above the second floor |
| Living in during the work | Ask | Dust walls and a temporary kitchen setup, $400 |
| Finish level and timeline | Ask | Price tier; rush +8% under 4 weeks; discount levers as today |
| Unknowns behind walls | Nobody can answer | No line item; each assumed fact widens the range by 5%, up to ±25% |

## Measuring without a tape

The Itemizer uses the most accurate method available and keeps the estimate's uncertainty, which feeds the price range. If two methods disagree by more than 20%, Alex asks for steps or a tape. Accuracy figures are working assumptions to check in testing.

| Method | How | Rough accuracy | Best for |
| --- | --- | --- | --- |
| Tape measure | Alex: "Do you have a tape measure handy?" | exact | Anything, if they offer |
| They already know | Alex: "Do you know roughly how big the room is?" (listings and floor plans) | ±10% | Whole rooms |
| Tile count | Percia counts tiles along two walls; tile size from objects in frame, or ask (12 x 12, 12 x 24 and 24 x 24 in are common). 9 x 7 tiles of 12 in = 63 sq ft | ±5 to 10% | Tiled floors and walls |
| Objects of known size | Percia scales from: interior door 80 in tall, 30 to 36 in wide; base cabinet 34.5 in tall, 24 in deep; counter 36 in high; standard tub 60 in long; toilet 28 in deep; vanity 21 in deep; outlet plate 4.5 in | ±15% | Rooms without tile; ceiling height; window sizes |
| Steps | Alex: "If it's easy, walk along the longest wall and count your steps." A normal step is about 2.5 ft; heel-to-toe is about 10 in | ±15 to 20% | Large rooms, as a cross-check |

Percia's goal result gains an optional value and unit for counting goals ("count the floor tiles along the wall by the tub" returns value 9, unit tiles), so measurements use the same async path as other camera facts.

## Build order

Built in three steps, each with its own prompt sent separately: (1) the Itemizer and this knowledge base, (2) the media store and Percia, (3) camera insights into the live call. Treat this file as the source of truth for tasks, facts, ladders, rules, drivers, measuring methods and prices.
