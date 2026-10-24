"""Pricing engine ported from mock_tool_server.py. Pure functions; persistence lives in the callers."""
import re

PACKAGES = {
    "refresh": {"small": 9500, "medium": 12500, "large": 17000},
    "standard": {"small": 15500, "medium": 21000, "large": 29000},
    "premium": {"small": 24000, "medium": 34000, "large": 46000},
}
ADDONS = {
    "walk-in shower": 4200, "double vanity": 2400, "heated floor": 1600,
    "glass door": 1900, "relocate plumbing": 3500, "electrical": 1500,
}
ADDON_LABELS = {
    "walk-in shower": "Walk-in shower conversion", "double vanity": "Double vanity",
    "heated floor": "Heated floor", "glass door": "Frameless glass door",
    "relocate plumbing": "Relocate plumbing", "electrical": "Electrical updates",
}
ADDON_KEYWORDS = {
    "walk-in shower": ["walk-in", "walk in", "walkin"],
    "double vanity": ["double vanity", "double sink", "two sinks"],
    "heated floor": ["heated floor", "radiant", "heated"],
    "glass door": ["glass", "frameless"],
    "relocate plumbing": ["relocat", "move the plumbing", "move plumbing"],
    "electrical": ["electrical", "circuit"],
}
DAMAGE_ALLOWANCE = 1800
RUSH_SURCHARGE = 0.08
DEPOSIT_PCT = 5
COST_RATIO = 0.75  # estimated job cost as a share of list price, used for the margin floor


def r500(x):
    return int(round(x / 500.0)) * 500


def is_rush(text):
    t = (text or "").lower()
    if any(w in t for w in ["asap", "rush", "urgent", "next week", "right away"]):
        return True
    m = re.search(r"(\d+)\s*week", t)
    return bool(m and int(m.group(1)) < 4)


def price(st):
    items = [{"key": "base", "label": f'{st["finish"].capitalize()} package, {st["size"]} bath',
              "amount": PACKAGES[st["finish"]][st["size"]]}]
    items += [{"key": f"add:{a}", "label": ADDON_LABELS[a], "amount": ADDONS[a]} for a in st["adds"]]
    items += [{"key": f"credit:{k}", "label": k[0].upper() + k[1:], "amount": -v} for k, v in st["credits"].items()]
    if st["damage"]:
        items.append({"key": "damage", "label": "Possible water damage allowance", "amount": DAMAGE_ALLOWANCE})
    total = sum(i["amount"] for i in items)
    if st["rush"]:
        rush = int(round(total * RUSH_SURCHARGE))
        items.append({"key": "rush", "label": "Rush schedule (8%)", "amount": rush})
        total += rush
    if st["disc"]:
        disc = int(round(total * st["disc"] / 100.0))
        items.append({"key": "discount", "label": f'Discount ({st["disc"]}%)', "amount": -disc})
        total -= disc
    return items, int(total)


def margin_pct(st, total):
    list_items, list_total = price({**st, "disc": 0})
    cost = list_total * COST_RATIO
    return round((1 - cost / total) * 100, 1) if total else 0


def margin_discount_cap(min_margin_pct):
    return max(0, int((1 - COST_RATIO / (1 - min_margin_pct / 100.0)) * 100))


def drivers(st):
    return list(st["adds"])[:3] or [f'{st["finish"]} package']


def new_state(a):
    """Returns (state, say) on success or (None, result_dict)."""
    if a.get("project_type", "other") != "bathroom_remodel":
        return None, {"status": "needs_human", "say": "Only bathroom remodels can be priced automatically."}
    size, finish = a.get("room_size", "unknown"), a.get("finish_level", "unknown")
    missing = [k for k, v in (("room_size", size), ("finish_level", finish))
               if v not in ("small", "medium", "large", "refresh", "standard", "premium")]
    if missing:
        return None, {"status": "needs_info", "missing": missing,
                      "say": "I still need " + " and ".join(missing).replace("_", " ") + "."}
    changes = " ".join(a.get("requested_changes") or []).lower()
    adds = [n for n, kws in ADDON_KEYWORDS.items() if any(k in changes for k in kws)]
    issues = (a.get("known_issues") or "").lower()
    st = {"size": size, "finish": finish, "adds": adds, "credits": {},
          "damage": any(w in issues for w in ["water", "mold", "soft", "rot", "leak"]),
          "rush": is_rush(a.get("timeline")), "disc": 0}
    say = "Estimate ready."
    if st["damage"]:
        say += " It includes an allowance for possible water damage; the real number is found at the site visit."
    return st, say


def adjust_state(st, a, max_discount_pct, min_margin_pct):
    """Mutates st. Returns (say, status) on success or (None, result_dict)."""
    kind = a.get("change_type")
    desc = (a.get("description") or "").lower()
    if kind == "scope_change":
        if "vinyl" in desc:
            st["credits"]["vinyl plank instead of tile"] = 1200
        elif "single vanity" in desc or "skip the double" in desc or "no double" in desc:
            if "double vanity" in st["adds"]:
                st["adds"].remove("double vanity")
            else:
                st["credits"]["single vanity"] = 2400
        elif "own fixtures" in desc or "supply" in desc:
            st["credits"]["customer-supplied fixtures"] = 900
        elif "heated" in desc and "heated floor" in st["adds"]:
            st["adds"].remove("heated floor")
        elif "glass" in desc and "glass door" in st["adds"]:
            st["adds"].remove("glass door")
        else:
            return None, {"status": "needs_human", "say": "That change needs the contractor to review."}
        return "Scope updated.", "ok"
    if kind == "timeline_change":
        weeks = a.get("timeline_weeks")
        st["rush"] = weeks is not None and weeks < 4
        return "Timeline updated.", "ok"
    if kind == "discount_request":
        allowed = 0
        if (a.get("flexible_timeline_weeks") or 0) >= 4:
            allowed += 3
        if a.get("can_sign_within_7_days"):
            allowed += 3
        allowed = min(allowed, max_discount_pct, margin_discount_cap(min_margin_pct))
        if allowed <= st["disc"]:
            return None, {"status": "limit_reached", "say": "That is the best available right now.",
                          "max_discount_percent": max_discount_pct}
        st["disc"] = allowed
        return f"Applied a {allowed} percent discount.", "ok"
    return None, {"status": "needs_human", "say": "That request needs the contractor."}
