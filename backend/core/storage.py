"""Emergent object storage (per playbook). Paths are prefixed with the app name."""
import os
import asyncio
import requests

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
APP = "walkthru"
_key = None


def _init(force=False):
    global _key
    if _key and not force:
        return _key
    r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": os.environ["EMERGENT_LLM_KEY"]}, timeout=30)
    r.raise_for_status()
    _key = r.json()["storage_key"]
    return _key


def _call(method, path, **kw):
    for attempt in (0, 1):
        r = requests.request(method, f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": _init(attempt == 1), **kw.pop("headers", {})},
                             timeout=180, **kw)
        if r.status_code == 404 and attempt == 0 and method == "PUT":
            continue
        r.raise_for_status()
        return r


async def put(path, data, content_type):
    r = await asyncio.to_thread(_call, "PUT", f"{APP}/{path}", data=data, headers={"Content-Type": content_type})
    return r.json()["path"]


async def get(path):
    r = await asyncio.to_thread(_call, "GET", path)
    return r.content, r.headers.get("Content-Type", "application/octet-stream")
