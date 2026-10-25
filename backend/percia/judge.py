"""judge_goal: the only place a vision model is called. Swap this module for Percept later."""
import os
import json
import uuid
import base64
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

SYSTEM = (
    "You are Percia, a careful home-renovation vision inspector. You get video frames from a homeowner's phone, in order, "
    "and a list of goals (questions). For each goal decide from the frames only:\n"
    "- met: the frames clearly answer it\n- ambiguous: some evidence, but you are not sure\n- not_found: the frames don't show it\n"
    "Reply with JSON only, no prose: {\"goals\": [{\"goal_id\": str, \"result\": \"met|ambiguous|not_found\", "
    "\"explanation\": one sentence, \"value\": number or null (counts and measurements only), \"unit\": str or null, "
    "\"hits\": [{\"frame\": frame index, \"box\": [x, y, w, h] as 0-1 fractions of the frame, \"label\": short label, "
    "\"confidence\": 0-1}]}]}. Give at most 2 hits per goal, best first. Follow any label format a goal asks for."
)


def _clamp(v):
    return min(1.0, max(0.0, float(v)))


def _clean(raw, n_frames):
    result = raw.get("result") if raw.get("result") in ("met", "ambiguous", "not_found") else "not_found"
    hits = []
    for h in raw.get("hits") or []:
        try:
            i = int(h["frame"])
            box = [_clamp(v) for v in h["box"]][:4]
            if 0 <= i < n_frames and len(box) == 4:
                hits.append({"frame": i, "box": box, "label": str(h.get("label") or "")[:80], "confidence": _clamp(h.get("confidence", 0.5))})
        except (KeyError, TypeError, ValueError):
            continue
    value = raw.get("value")
    return {"result": result, "explanation": str(raw.get("explanation") or "")[:300],
            "value": value if isinstance(value, (int, float)) and not isinstance(value, bool) else None,
            "unit": raw.get("unit") if isinstance(raw.get("unit"), str) else None, "hits": hits}


async def judge_goal(frames, queries):
    """frames: [{t_ms, path}] JPEGs in order; queries: [{goal_id, query}]. Returns {goal_id: result}. Raises on model failure."""
    chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"percia-{uuid.uuid4().hex[:12]}", system_message=SYSTEM)
    chat.with_model("gemini", os.environ["VISION_MODEL"])
    images = [ImageContent(image_base64=base64.b64encode(open(f["path"], "rb").read()).decode()) for f in frames]
    listing = "\n".join(f"Frame {i}: t={f['t_ms']} ms" for i, f in enumerate(frames))
    text = f"Frames (attached in this order):\n{listing}\n\nGoals:\n{json.dumps(queries)}"
    reply = str(await chat.send_message(UserMessage(text=text, file_contents=images)))
    data = json.loads(reply[reply.find("{"): reply.rfind("}") + 1])
    by_id = {g.get("goal_id"): g for g in data.get("goals") or [] if isinstance(g, dict)}
    return {q["goal_id"]: _clean(by_id.get(q["goal_id"]) or {}, len(frames)) for q in queries}
