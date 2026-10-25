"""Itemizer knowledge base (from docs/itemizer-design.md). All prices are placeholders. Seeded into kb_tasks, kb_facts, kb_rules."""
from core.db import db

C, S, A, M, X = "camera", "show", "ask", "measure", "assume"


def F(scope, ladder, label, default, question="", show="", goal="", numeric=False, step=None):
    d = {"scope": scope, "ladder": ladder, "label": label, "default": default, "question": question,
         "show": show, "goals": [goal] if goal else [], "numeric": numeric}
    return {**d, "step": step} if step else d


FACTS = {
    "sinks": F("item", [C, A], "number of sinks", "1", "Is it a single sink or a double?", goal="How many sinks does the vanity have?"),
    "vanity_mount": F("item", [C, S, A, X], "vanity mount", "floor", "Does it sit right on the floor, or hang on the wall with space underneath?",
                      "Could you point the camera at the bottom of the vanity for a second?", "Does the vanity sit on the floor, or hang on the wall with open floor beneath?"),
    "replacing_vanity": F("item", [A, X], "replacing the vanity", "new", "Are you putting a new vanity there, or leaving the space open?"),
    "new_vanity_sinks": F("item", [A, X], "sinks in the new vanity", "1", "Would you like one sink or two in the new vanity?"),
    "new_vanity_mount": F("item", [A, X], "new vanity mount", "floor", "Do you want the new one floating on the wall, or standing on the floor?"),
    "finish_level": F("job", [A, X], "finish level", "standard", "What finish level feels right: refresh, standard or premium?"),
    "tub_type": F("item", [C, A, X], "tub type", "alcove", "Is the tub tucked between three walls, standing on its own, or set into a frame?", goal="What type of tub is this: alcove, freestanding or drop-in?"),
    "cast_iron": F("item", [S, A, X], "cast iron tub", "no", "Is it a heavy metal tub?", "Could you show me the edge of the tub for a second?"),
    "shower_size": F("item", [A, X], "shower size", "standard", "Should the new shower be about the size of the old tub, or bigger?"),
    "shower_glass": F("item", [A, X], "shower enclosure", "door", "Would you like a glass door, a fixed glass panel, or a curtain?"),
    "shower_niche": F("item", [A, X], "shower niche", "no", "Would you like a built-in shelf niche in the shower?"),
    "curbless": F("item", [A, X], "curbless shower", "no", "Do you want a step-in shower with no lip at the entry?"),
    "moving": F("item", [A, X], "moving it", "same", "Do you want it in the same spot, or moved somewhere else?"),
    "floor_type": F("room", [C, A, X], "current floor", "vinyl", "What's on the floor now: vinyl, tile, wood or carpet?", goal="What is the current floor: carpet, hardwood, tile, vinyl or laminate?"),
    "floor_area": F("room", [C, M, X], "floor area (sq ft)", 60, show="If it's easy, count the floor tiles along two walls, or walk the longest wall and count your steps.",
                    goal="Count the floor tiles along two walls", numeric=True, step="square"),
    "wall_tile_height": F("item", [A, X], "wall tile height", "wainscot", "Should the wall tile go part way up, or all the way to the ceiling?"),
    "wall_tile_area": F("item", [M, X], "wall tile area (sq ft)", 60, show="If it's easy, tell me how long the tiled walls are, using the door for scale.", numeric=True, step=4),
    "fan_exists": F("room", [C, A, X], "exhaust fan", "yes", "Is there an exhaust fan in there now?", goal="Is there an exhaust fan in the ceiling?"),
    "fan_vents_outside": F("room", [A, X], "fan vents outside", "yes", "Does the fan blow air outside?"),
    "new_lights": F("item", [A, X], "new lights", 1, "How many new lights would you like?", numeric=True),
    "grab_bars": F("item", [A, X], "grab bars", 2, "How many grab bars would you like?", numeric=True),
    "bench": F("item", [A, X], "shower bench", "no", "Would you like a shower bench?"),
    "cabinet_work": F("item", [A, X], "cabinet work", "replace", "Do you want new cabinets, new doors on the old boxes, or just paint?"),
    "cabinet_length": F("item", [C, M, X], "cabinet length (linear ft)", 20, show="If it's easy, count your steps along the cabinets.",
                        goal="Count base cabinet boxes (24 in deep, 34.5 in tall) to estimate linear feet", numeric=True),
    "uppers_to_ceiling": F("item", [C, X], "uppers to the ceiling", "no", goal="Do the upper cabinets go all the way to the ceiling?"),
    "counter_material_now": F("item", [C, X], "current countertop", "laminate", goal="What is the countertop: laminate, tile, stone or quartz?"),
    "counter_material_new": F("item", [A, X], "new countertop", "quartz", "What countertop would you like: laminate, stone or quartz?"),
    "counter_area": F("item", [M, X], "countertop area (sq ft)", 30, show="If it's easy, count your steps along the counters.", numeric=True, step=2.125),
    "undermount_sink": F("item", [A, X], "undermount sink", "no", "Would you like the sink mounted under the counter?"),
    "backsplash_exists": F("item", [C, X], "existing backsplash", "yes", goal="Is there a backsplash on the wall behind the counter?"),
    "backsplash_area": F("item", [M, X], "backsplash area (sq ft)", 25, show="If it's easy, count your steps along the counters.", numeric=True, step=1.5),
    "sink_bowls": F("item", [C, A, X], "sink bowls", "1", "Is it a single or double bowl sink?", goal="How many bowls does the kitchen sink have?"),
    "stove_fuel_now": F("item", [A, X], "stove fuel now", "electric", "Is your stove gas or electric?"),
    "stove_fuel_new": F("item", [A, X], "stove fuel wanted", "electric", "Would you like gas, electric or induction for the new one?"),
    "hood_type": F("item", [C, S, A, X], "range hood type", "under-cabinet", "Does the fan sit above the stove, or pop up from the cooktop?",
                   "Could you show me the hood above the stove?", "What type of range hood is this: chimney, under-cabinet, microwave, downdraft or none?"),
    "hood_vents_outside": F("item", [S, A, X], "hood vents outside", "yes", "Does it blow air outside?", "Could you show me the top of the hood for a second?"),
    "island_change": F("item", [A, X], "island change", "add", "Are you adding, removing or changing an island?"),
    "island_needs": F("item", [A, X], "island water or power", "none", "Will the island need water or power?"),
    "island_length": F("item", [M, X], "island length (linear ft)", 6, show="If it's easy, count your steps along the island.", numeric=True),
    "dishwasher_exists": F("room", [C, X], "existing dishwasher", "yes", goal="Is there a dishwasher?"),
    "appliance_count": F("item", [A, X], "appliances to install", 1, "How many appliances should we install?", numeric=True),
    "light_count": F("item", [A, X], "new recessed lights", 4, "How many new recessed lights would you like?", numeric=True),
    "attic_above": F("room", [A, X], "attic above", "attic", "Is there an attic above, or another floor?"),
    "floor_new": F("item", [A, X], "new floor", "vinyl", "What new floor would you like: vinyl plank, hardwood or carpet?"),
    "stairs": F("item", [C, A, X], "stairs", 0, "How many stairs are there, if any?", goal="Count the stairs", numeric=True),
    "paint_surfaces": F("item", [A, X], "paint surfaces", "walls", "Walls, ceilings, or both?"),
    "wall_area": F("room", [M, X], "wall area (sq ft)", 400, show="If it's easy, walk along the longest wall and count your steps.", numeric=True, step=32),
    "ceiling_height": F("room", [M, X], "ceiling height (ft)", 8, show="Is the ceiling about a door and a half high, or taller?", numeric=True),
    "dark_to_light": F("item", [C, A, X], "dark to light color", "no", "Are you going from a dark color to a light one?", goal="Are the walls a dark color?"),
    "wall_cracks": F("item", [C, X], "cracks or patches", "no", goal="Any cracks, holes or patches on the walls?"),
    "drywall_areas": F("item", [C, X], "drywall areas to patch", 1, goal="How many cracked or damaged wall areas are there?", numeric=True),
    "popcorn": F("room", [C, X], "popcorn ceiling", "no", goal="Is the ceiling textured popcorn?"),
    "house_built": F("job", [A, X], "year built", 1990, "Roughly when was the house built?", numeric=True),
    "trim_length": F("item", [M, X], "trim length (linear ft)", 60, show="If it's easy, walk around the room and count your steps.", numeric=True),
    "window_count": F("item", [C, A, X], "windows", 1, "How many windows are we replacing?", goal="Count the windows", numeric=True),
    "door_count": F("item", [C, A, X], "doors", 1, "How many doors are we replacing?", goal="Count the interior doors", numeric=True),
    "fireplace_fuel": F("item", [A, X], "fireplace fuel", "wood", "Is the fireplace wood or gas?"),
    "fireplace_fuel_new": F("item", [A, X], "fireplace fuel wanted", "wood", "Would you like it to burn wood or gas afterwards?"),
    "fan_count": F("item", [A, X], "ceiling fans", 0, "How many ceiling fans would you like?", numeric=True),
    "builtin_length": F("item", [M, X], "built-in length (linear ft)", 6, show="If it's easy, count your steps along that wall.", numeric=True),
    "what_below": F("job", [A, X], "what's below", "crawlspace", "What's under the floor: a slab, a crawlspace or a basement?"),
    "fixtures_moved": F("item", [A, X], "fixtures moved", 1, "How many fixtures are moving?", numeric=True),
    "gas_service": F("job", [A, X], "gas service", "yes", "Does the house have gas service already?"),
    "panel_label": F("job", [S, X], "panel amps", "200A", show="Could you show me the label on your electrical panel?"),
    "floor_above": F("item", [A, X], "floor above", "no", "Is there another floor above that wall?"),
    "beam_nearby": F("item", [C, X], "beam or posts nearby", "no", goal="Is there a beam or posts near this wall?"),
    "wall_utilities": F("item", [C, X], "utilities in the wall", 0, goal="Count outlets, switches or vents in this wall", numeric=True),
    "water_damage": F("job", [C, A, X], "water damage", "no", "Any leaks or soft spots you've noticed?", goal="Any stains, swelling, peeling paint or mold?"),
    "timeline": F("job", [A, X], "timeline", "in two months", "When would you like to start?"),
    "live_in": F("job", [A, X], "living in during work", "yes", "Will you be living there during the work?"),
}

OPTIONS = {
    "sinks": ["1", "2"], "vanity_mount": ["floor", "floating"], "tub_type": ["alcove", "freestanding", "drop-in"],
    "cast_iron": ["yes", "no"], "floor_type": ["vinyl", "tile", "wood", "carpet", "laminate"], "fan_exists": ["yes", "no"],
    "uppers_to_ceiling": ["yes", "no"], "counter_material_now": ["laminate", "tile", "stone", "quartz"], "backsplash_exists": ["yes", "no"],
    "sink_bowls": ["1", "2"], "hood_type": ["chimney", "under-cabinet", "microwave", "downdraft", "none"], "hood_vents_outside": ["yes", "no"],
    "dishwasher_exists": ["yes", "no"], "dark_to_light": ["yes", "no"], "wall_cracks": ["yes", "no"], "popcorn": ["yes", "no"],
    "beam_nearby": ["yes", "no"], "water_damage": ["yes", "no"], "panel_label": ["100A", "150A", "200A", "full"],
}
CAMERA_GOALS = {
    "cast_iron": "Is the tub heavy cast iron (thick enamel edge, very solid)?",
    "hood_vents_outside": "Does the range hood have a duct going up into the cabinet, wall or ceiling to the outside?",
    "panel_label": "Read the main breaker amps on the electrical panel label, or say if the panel has no free spaces.",
    "floor_area": "Count the floor tiles along two walls and estimate the floor area.",
}
for _k, _v in OPTIONS.items():
    FACTS[_k]["options"] = _v
for _k, _v in CAMERA_GOALS.items():
    FACTS[_k]["goals"] = [_v]


def P(amount=None, tiers=None, qty=None, mult=1, when=None, label=None):
    return {k: v for k, v in dict(amount=amount, tiers=tiers, qty=qty, mult=mult, when=when, label=label).items() if v is not None}


def T(room, label, facts, price, triggers=(), tags=(), auto=False):
    return {"room": room, "label": label, "facts": list(facts), "price": price, "triggers": list(triggers), "tags": list(tags), "auto": auto}


TASKS = {
    # bathroom
    "remove_vanity": T("bathroom", "Remove vanity", ["sinks", "vanity_mount", "replacing_vanity"],
                       [P(350, when={"sinks": ["1"]}), P(550, when={"sinks": ["2"]})],
                       [r"\b(sink|vanity)\b.*\b(gone|out|remove|rip|tear|replace)", r"\b(remove|rip out|tear out|get rid of)\b.*\b(sink|vanity)"], ["removal"]),
    "new_vanity": T("bathroom", "New vanity", ["new_vanity_sinks", "new_vanity_mount"],
                    [P(650, when={"new_vanity_sinks": ["1"]}, label="install"), P(950, when={"new_vanity_sinks": ["2"]}, label="install"),
                     P(tiers=[900, 1800, 3500], when={"new_vanity_sinks": ["1"]}, label="vanity and top"),
                     P(tiers=[1600, 3200, 6000], when={"new_vanity_sinks": ["2"]}, label="vanity and top"),
                     P(tiers=[250, 450, 800], qty="new_vanity_sinks", label="faucets")],
                    [r"\b(new|double|floating) vanity\b"], ["plumbing"]),
    "retile_under_vanity": T("bathroom", "Retile under old vanity", [], [P(650)], auto=True),
    "remove_tub": T("bathroom", "Remove tub", ["tub_type", "cast_iron"],
                    [P(650, when={"tub_type": ["alcove"]}), P(350, when={"tub_type": ["freestanding"]}), P(900, when={"tub_type": ["drop-in"]})],
                    [r"\btub\b.*\b(gone|out|remove)", r"\b(remove|rip out|instead of)\b.*\btub\b"], ["removal"]),
    "cast_iron_tub": T("bathroom", "Cast iron tub removal", [], [P(300)], auto=True),
    "walk_in_shower": T("bathroom", "Walk-in shower", ["shower_size", "shower_glass", "shower_niche", "curbless"],
                        [P(6800, when={"shower_size": ["standard"]}, label="build"), P(8900, when={"shower_size": ["large", "bigger"]}, label="build"),
                         P(tiers=[900, 1800, 3600], label="tile"), P(1900, when={"shower_glass": ["door"]}, label="glass door"),
                         P(1200, when={"shower_glass": ["panel"]}, label="glass panel"), P(450, when={"shower_niche": ["yes"]}, label="niche"),
                         P(tiers=[350, 700, 1500], label="fixtures")],
                        [r"walk[- ]?in", r"\bshower\b"], ["shower", "plumbing"]),
    "curbless_upgrade": T("bathroom", "Curbless shower upgrade", [], [P(1800)], auto=True),
    "toilet": T("bathroom", "Toilet", ["moving"], [P(450, label="install"), P(tiers=[300, 550, 1100], label="toilet")], [r"\btoilet\b"]),
    "floor_tile": T("bathroom", "Floor tile", ["floor_type", "floor_area"],
                    [P(2, qty="floor_area", when={"floor_type": ["vinyl"]}, label="removal"), P(4, qty="floor_area", when={"floor_type": ["tile", "wood"]}, label="removal"),
                     P(12, qty="floor_area", label="install"), P(tiers=[4, 8, 15], qty="floor_area", label="tile")],
                    [r"\b(floor|tile floor|new floor)\b"], ["removal"]),
    "wall_tile": T("bathroom", "Wall tile", ["wall_tile_height", "wall_tile_area"], [P(tiers=[18, 28, 45], qty="wall_tile_area")], [r"\bwall tile\b", r"\btile (the )?walls?\b"]),
    "exhaust_fan_lights": T("bathroom", "Exhaust fan and lights", ["fan_exists", "fan_vents_outside", "new_lights"],
                            [P(650, when={"fan_exists": ["no"]}, label="new fan"), P(400, when={"fan_exists": ["yes"], "fan_vents_outside": ["no"]}, label="duct to outside"),
                             P(225, qty="new_lights", label="light install"), P(tiers=[150, 300, 600], qty="new_lights", label="fixtures")],
                            [r"\b(fan|exhaust|lights?|lighting)\b"], ["electrical"]),
    "heated_floor": T("bathroom", "Heated floor", [], [P(1600)], [r"\bheated floor", r"\bradiant\b"], ["electrical"]),
    "safety_access": T("bathroom", "Safety and access", ["grab_bars", "bench"], [P(250, qty="grab_bars", label="grab bars"), P(650, when={"bench": ["yes"]}, label="bench")],
                       [r"\bgrab bars?\b", r"\bbench\b"]),
    # kitchen
    "cabinets": T("kitchen", "Cabinets", ["cabinet_work", "cabinet_length", "uppers_to_ceiling"],
                  [P(tiers=[350, 550, 900], qty="cabinet_length", when={"cabinet_work": ["replace"]}), P(220, qty="cabinet_length", when={"cabinet_work": ["reface"]}),
                   P(120, qty="cabinet_length", when={"cabinet_work": ["paint"]})], [r"\bcabinets?\b"], ["removal"]),
    "countertops": T("kitchen", "Countertops", ["counter_material_now", "counter_material_new", "counter_area", "undermount_sink"],
                     [P(tiers=[45, 75, 120], qty="counter_area", label="install"), P(5, qty="counter_area", when={"counter_material_now": ["laminate"]}, label="removal"),
                      P(10, qty="counter_area", when={"counter_material_now": ["tile", "stone", "quartz"]}, label="removal")],
                     [r"\bcounter(top)?s?\b"], ["removal"]),
    "backsplash": T("kitchen", "Backsplash", ["backsplash_exists", "backsplash_area"], [P(tiers=[30, 45, 75], qty="backsplash_area")], [r"\bbacksplash\b"]),
    "kitchen_sink": T("kitchen", "Sink and faucet", ["sink_bowls", "moving"], [P(tiers=[650, 1100, 2000])], [r"\b(sink|faucet)\b"], ["plumbing"]),
    "range": T("kitchen", "Range or cooktop", ["stove_fuel_now", "stove_fuel_new"], [P(250)], [r"\b(stove|range|cooktop|oven)\b"]),
    "range_hood": T("kitchen", "Range hood", ["hood_type", "hood_vents_outside"], [P(450, label="install"), P(tiers=[300, 800, 2000], label="hood")], [r"\bhood\b", r"\bvent(ilation)?\b"]),
    "island": T("kitchen", "Island", ["island_change", "island_needs", "island_length"],
                [P(tiers=[350, 550, 900], qty="island_length", label="cabinets"), P(tiers=[45, 75, 120], qty="island_length", mult=3, label="countertop")], [r"\bisland\b"]),
    "appliances": T("kitchen", "Dishwasher and appliances", ["appliance_count"], [P(250, qty="appliance_count")], [r"\b(dishwasher|fridge|refrigerator|appliances?|microwave)\b"]),
    "kitchen_lighting": T("kitchen", "Lighting", ["light_count", "attic_above"], [P(250, qty="light_count")], [r"\b(lights?|lighting|recessed|pendants?)\b"], ["electrical"]),
    # living rooms and bedrooms (flooring also used by kitchen)
    "flooring": T(None, "Flooring", ["floor_type", "floor_new", "floor_area", "stairs"],
                  [P(tiers=[7, 9, 12], qty="floor_area", when={"floor_new": ["vinyl"]}, label="vinyl plank"), P(tiers=[12, 16, 22], qty="floor_area", when={"floor_new": ["hardwood"]}, label="hardwood"),
                   P(tiers=[5, 7, 10], qty="floor_area", when={"floor_new": ["carpet"]}, label="carpet"), P(1, qty="floor_area", when={"floor_type": ["carpet", "laminate"]}, label="removal"),
                   P(4, qty="floor_area", when={"floor_type": ["tile"]}, label="removal"), P(3, qty="floor_area", when={"floor_type": ["wood", "hardwood"]}, label="removal"),
                   P(2, qty="floor_area", when={"floor_type": ["vinyl"]}, label="removal"), P(150, qty="stairs", label="stairs")],
                  [r"\b(floor|flooring|carpet|hardwood|vinyl plank|laminate)\b"], ["removal"]),
    "paint": T(None, "Paint", ["paint_surfaces", "wall_area", "ceiling_height", "dark_to_light", "wall_cracks", "house_built"],
               [P(tiers=[3, 4, 5], qty="wall_area", when={"paint_surfaces": ["walls", "both"]}, label="walls"),
                P(tiers=[0.75, 1, 1.25], qty="wall_area", when={"paint_surfaces": ["walls", "both"], "dark_to_light": ["yes"]}, label="extra coat"),
                P(2, qty="floor_area", when={"paint_surfaces": ["ceilings", "both"]}, label="ceilings")], [r"\bpaint(ing)?\b"]),
    "drywall": T(None, "Drywall repair and textured ceiling", ["drywall_areas", "popcorn", "house_built"],
                 [P(250, qty="drywall_areas", label="patch"), P(3.5, qty="floor_area", when={"popcorn": ["yes"]}, label="popcorn removal")], [r"\b(drywall|crack|holes?|popcorn)\b"]),
    "trim": T(None, "Trim and baseboards", ["trim_length"], [P(tiers=[8, 12, 18], qty="trim_length")], [r"\b(trim|baseboards?|molding)\b"]),
    "windows": T(None, "Windows", ["window_count"], [P(tiers=[700, 1100, 1800], qty="window_count")], [r"\bwindows?\b"]),
    "interior_doors": T(None, "Interior doors", ["door_count"], [P(tiers=[450, 700, 1100], qty="door_count")], [r"\bdoors?\b"]),
    "fireplace": T(None, "Fireplace", ["fireplace_fuel", "fireplace_fuel_new"], [P(tiers=[2500, 4500, 8000])], [r"\bfireplace\b"]),
    "lighting_fans": T(None, "Lighting and ceiling fans", ["light_count", "fan_count", "attic_above"], [P(250, qty="light_count", label="recessed"), P(350, qty="fan_count", label="fans")],
                       [r"\b(lights?|lighting|recessed|ceiling fans?)\b"], ["electrical"]),
    "built_ins": T(None, "Built-ins", ["builtin_length"], [P(tiers=[600, 900, 1400], qty="builtin_length")], [r"\bbuilt[- ]?ins?\b", r"\bshelves\b"]),
    # whole-house and common items (added by rules or the price step)
    "protection": T(None, "Protection and cleanup", [], [P(450)], auto=True),
    "demolition": T(None, "Demolition and haul-away", [], [P(650)], auto=True),
    "permit": T(None, "Permit", [], [P(450)], auto=True),
    "move_plumbing": T(None, "Move plumbing", ["fixtures_moved", "what_below"],
                       [P(1500, qty="fixtures_moved", when={"what_below": ["crawlspace", "basement"]}), P(3000, qty="fixtures_moved", when={"what_below": ["slab"]})], auto=True, tags=["plumbing"]),
    "gas_line": T(None, "Gas line", ["gas_service"], [P(1200, when={"gas_service": ["yes"]}), P(2500, when={"gas_service": ["no"]})], auto=True, tags=["gas"]),
    "circuit_120": T(None, "New 120 V circuit", [], [P(450)], auto=True, tags=["electrical"]),
    "circuit_240": T(None, "New 240 V circuit", [], [P(900)], auto=True, tags=["electrical"]),
    "panel_upgrade": T(None, "Panel upgrade allowance", ["panel_label"], [P(2500)], auto=True, tags=["electrical"]),
    "wall_removal": T(None, "Wall removal", ["floor_above", "beam_nearby", "wall_utilities"],
                      [P(2500, when={"floor_above": ["no"], "beam_nearby": ["no"]}, label="not likely load-bearing"),
                       P(6800, when={"floor_above": ["yes"]}, label="engineer and beam allowance"), P(6800, when={"floor_above": ["no"], "beam_nearby": ["yes"]}, label="engineer and beam allowance"),
                       P(800, qty="wall_utilities", label="utilities in the wall")], [r"\bwall\b.*\b(gone|out|remove|open)", r"\b(remove|knock down|take out|open up)\b.*\bwall\b"], ["structural", "removal"]),
    "hvac_vent_move": T(None, "HVAC vent move", [], [P(450)], auto=True),
    "asbestos_test": T(None, "Asbestos test", [], [P(400)], auto=True),
    "lead_safe": T(None, "Lead-safe work", [], [P(600)], auto=True),
    "outside_venting": T("kitchen", "Add outside venting", [], [P(1200)], auto=True),
    "downdraft_replace": T("kitchen", "Replace downdraft", [], [P(800)], auto=True),
    "new_dishwasher_hookup": T("kitchen", "New dishwasher hookup", [], [P(900)], auto=True, tags=["plumbing"]),
    "no_attic_lights": T(None, "No attic access for lights", ["light_count"], [P(100, qty="light_count")], auto=True),
    "water_damage_allowance": T(None, "Water damage allowance", [], [P(1800)], auto=True),
    "temp_kitchen": T("kitchen", "Dust walls and temporary kitchen", [], [P(400)], auto=True),
}


def R(rid, add, has=(), lacks=(), facts=None, lt=None, note="", nots=None):
    return {"rule_id": rid, "kind": "rule", "add": add, "has": list(has), "lacks": list(lacks), "facts": facts or {}, "lt": lt or {},
            "not": nots or {}, "note": note}


RULES = [
    R("retile_floating", "retile_under_vanity", ["remove_vanity", "new_vanity"], ["floor_tile"], {"vanity_mount": ["floor"], "new_vanity_mount": ["floating"]}, note="Floor-standing out, floating in, no new floor"),
    R("retile_open_space", "retile_under_vanity", ["remove_vanity"], ["floor_tile", "new_vanity"], {"vanity_mount": ["floor"]},
      note="Floor-standing vanity removed, no new vanity and no new floor in scope"),
    R("new_vanity_from_answer", "new_vanity", ["remove_vanity"], [], {"replacing_vanity": ["new"]}, note="Homeowner is putting in a new vanity"),
    R("cast_iron", "cast_iron_tub", ["remove_tub"], [], {"cast_iron": ["yes"]}, note="Heavy cast iron tub +$300"),
    R("curbless", "curbless_upgrade", ["walk_in_shower"], [], {"curbless": ["yes"]}, note="Curbless shower +$1,800"),
    R("toilet_moves", "move_plumbing", ["toilet"], [], {"moving": ["move", "moved", "yes"]}, note="Moving a fixture adds Move plumbing"),
    R("sink_moves", "move_plumbing", ["kitchen_sink"], [], {"moving": ["move", "moved", "yes"]}, note="Moving the sink adds Move plumbing"),
    R("gas_to_electric", "circuit_240", ["range"], [], {"stove_fuel_now": ["gas"], "stove_fuel_new": ["electric", "induction"]}, note="Gas to electric or induction adds a 240 V circuit"),
    R("electric_to_gas", "gas_line", ["range"], [], {"stove_fuel_now": ["electric"], "stove_fuel_new": ["gas"]}, note="Electric to gas adds a gas line"),
    R("hood_outside", "outside_venting", ["range_hood"], [], {"hood_vents_outside": ["no"]}, note="Adding outside venting"),
    R("hood_downdraft", "downdraft_replace", ["range_hood"], [], {"hood_type": ["downdraft"]}, note="Replacing a downdraft"),
    R("island_water", "move_plumbing", ["island"], [], {"island_needs": ["water", "both"]}, note="Island water adds Move plumbing"),
    R("island_power", "circuit_120", ["island"], [], {"island_needs": ["power", "both"]}, note="Island power adds a circuit"),
    R("new_dishwasher", "new_dishwasher_hookup", ["appliances"], [], {"dishwasher_exists": ["no"]}, note="Dishwasher where there was none"),
    R("no_attic_kitchen", "no_attic_lights", ["kitchen_lighting"], [], {"attic_above": ["floor", "no"]}, note="Floor above, no attic access"),
    R("no_attic_living", "no_attic_lights", ["lighting_fans"], [], {"attic_above": ["floor", "no"]}, note="Floor above, no attic access"),
    R("paint_cracks", "drywall", ["paint"], [], {"wall_cracks": ["yes"]}, note="Cracks or patches add Drywall repair"),
    R("asbestos", "asbestos_test", ["drywall"], [], {"popcorn": ["yes"]}, {"house_built": 1980}, note="Popcorn ceiling, house before 1980"),
    R("lead", "lead_safe", ["paint"], [], {}, {"house_built": 1978}, note="House before 1978 and painted surfaces disturbed"),
    R("wood_to_gas", "gas_line", ["fireplace"], [], {"fireplace_fuel": ["wood"], "fireplace_fuel_new": ["gas"]}, note="Wood to gas fireplace adds a gas line"),
    R("heated_floor_circuit", "circuit_120", ["heated_floor"], [], {"panel_label": ["full", "100A"]}, note="Heated floor and the panel is full"),
    R("panel_upgrade", "panel_upgrade", ["circuit_240"], [], {"panel_label": ["full", "100A"]}, note="New circuits and a 100 A or full panel"),
    R("water_damage", "water_damage_allowance", [], [], {"water_damage": ["yes"]}, note="Allowance, listed as an assumption until the site visit"),
    R("live_in_kitchen", "temp_kitchen", ["cabinets"], [], {"live_in": ["yes"]}, note="Living in during kitchen work"),
]

DRIVERS = [
    ("water_damage", "Water damage, leaks, mold", "Camera watches for stains, swelling, peeling paint and mold; ask \"Any leaks or soft spots you've noticed?\"", "Water damage allowance $1,800, listed as an assumption"),
    ("floor_now", "What's on the floor now", "Camera identifies it; assume one layer", "Removal price per sq ft by type; tile over tile raises removal"),
    ("plumbing_gas_moves", "Plumbing or gas moves", "Ask \"Do you want the sink in the same spot?\"; ask what's below", "Move plumbing or Gas line items"),
    ("power_needs", "Power needs", "Ask what appliances are coming; show the panel label if heavy loads are added", "New circuit or Panel upgrade items"),
    ("house_age", "House age", "Ask \"Roughly when was the house built?\"", "Before 1978: lead-safe work; before 1980 with popcorn or 9 in tiles: asbestos test"),
    ("walls_out", "Walls coming out", "Ask about the floor above; camera looks for beams and utilities", "Wall removal item; engineer if likely load-bearing"),
    ("room_size", "Room size", "Measure", "Every per-sq-ft and per-linear-ft line; uncertainty widens the range"),
    ("ceiling_height", "Ceiling height", "Measure from the door (80 in)", "Wall tile, paint and to-ceiling cabinet quantities"),
    ("access", "Access", "Ask which floor and whether there's an elevator or tight stairs", "+5% labor above the second floor"),
    ("live_in", "Living in during the work", "Ask", "Dust walls and a temporary kitchen setup, $400"),
    ("finish_timeline", "Finish level and timeline", "Ask", "Price tier; rush +8% under 4 weeks; discount levers as today"),
    ("unknowns", "Unknowns behind walls", "Nobody can answer", "No line item; each assumed fact widens the range by 5%, up to 25%"),
]
METHODS = [
    ("tape", "Tape measure", "Alex: \"Do you have a tape measure handy?\"", "exact", "Anything, if they offer", 0),
    ("known", "They already know", "Alex: \"Do you know roughly how big the room is?\"", "10%", "Whole rooms", 10),
    ("tiles", "Tile count", "Percia counts tiles along two walls; 9 x 7 tiles of 12 in = 63 sq ft", "5 to 10%", "Tiled floors and walls", 7),
    ("objects", "Objects of known size", "Door 80 in, base cabinet 34.5 x 24 in, counter 36 in, tub 60 in, toilet 28 in, vanity 21 in, outlet plate 4.5 in", "15%", "Rooms without tile; ceiling height; windows", 15),
    ("steps", "Steps", "Alex: \"If it's easy, walk along the longest wall and count your steps.\" Step about 2.5 ft", "15 to 20%", "Large rooms, as a cross-check", 18),
]


async def seed_kb(force=False):
    if not force and await db.kb_tasks.count_documents({}):
        return
    for c in ("kb_tasks", "kb_facts", "kb_rules"):
        await db[c].delete_many({})
    await db.kb_tasks.insert_many([{"task_id": k, **v} for k, v in TASKS.items()])
    await db.kb_facts.insert_many([{"fact_id": k, **v} for k, v in FACTS.items()])
    await db.kb_rules.insert_many(RULES + [{"rule_id": f"driver_{d[0]}", "kind": "driver", "name": d[1], "how": d[2], "effect": d[3]} for d in DRIVERS]
                                  + [{"rule_id": f"measure_{m[0]}", "kind": "measure_method", "name": m[1], "how": m[2], "accuracy": m[3], "best_for": m[4], "uncertainty_pct": m[5]} for m in METHODS])


async def load_kb():
    tasks = {t["task_id"]: t async for t in db.kb_tasks.find({}, {"_id": 0})}
    facts = {f["fact_id"]: f async for f in db.kb_facts.find({}, {"_id": 0})}
    rules = [r async for r in db.kb_rules.find({"kind": "rule"}, {"_id": 0})]
    return tasks, facts, rules
