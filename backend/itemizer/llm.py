import os
import json
import hashlib
import logging
from emergentintegrations.llm.chat import LlmChat, UserMessage
from core.db import db

logger = logging.getLogger("itemizer.llm")
SYSTEM = ("You map a homeowner's words to task ids from a renovation knowledge base. You never price anything. "
          "Reply with JSON only: {\"task_ids\": [...]}. Use only ids from the list. Use [] if no work is described. "
          "Use [\"needs_human\"] if they describe work that is not in the list.")


async def map_tasks(said, room, catalog):
    key = hashlib.sha256(f"{room}|{said.strip().lower()}|{sorted(catalog)}".encode()).hexdigest()
    cached = await db.itemizer_llm_cache.find_one({"key": key})
    if cached:
        return cached["task_ids"]
    try:
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"itemizer-{key[:12]}", system_message=SYSTEM)
        chat.with_model("anthropic", "claude-opus-5-5")
        reply = await chat.send_message(UserMessage(text=f"Room: {room}\nTasks: {json.dumps(catalog)}\nHomeowner said: {said}"))
        text = str(reply)
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
        ids = [t for t in data.get("task_ids", []) if t in catalog or t == "needs_human"]
    except Exception as e:
        logger.warning("task mapping failed: %s", e)
        return ["needs_human"]
    await db.itemizer_llm_cache.insert_one({"key": key, "task_ids": ids})
    return ids
