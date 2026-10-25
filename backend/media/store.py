"""Media store: video clips in object storage, metadata in the `media` collection."""
import os
import re
import time
import uuid
import asyncio
import tempfile
import imageio_ffmpeg
from pymongo.errors import DuplicateKeyError
from core.db import db, iso
from core import events, storage
from core.service_auth import sign, app_url

URL_TTL_S = 900
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
EXT = {"video/webm": "webm", "video/mp4": "mp4", "video/quicktime": "mov", "video/x-matroska": "mkv"}
PUBLIC = ("media_id", "kind", "t_start_ms", "duration_ms")


async def init():
    await db.media.create_index([("session_id", 1), ("kind", 1), ("seq", 1)], unique=True)
    await db.media.create_index("media_id", unique=True)


def url_sig(media_id, exp):
    return sign(os.environ["MEDIA_SIGNING_KEY"], f"{media_id}.{exp}".encode())


def signed_url(media_id):
    exp = int(time.time()) + URL_TTL_S
    return f"{app_url()}/api/media/{media_id}/file?exp={exp}&sig={url_sig(media_id, exp)}"


def public(doc):
    return {**{k: doc[k] for k in PUBLIC}, "url": signed_url(doc["media_id"])}


async def probe_duration_ms(data: bytes):
    """Container duration without decoding (MediaRecorder webm has none in the header)."""
    with tempfile.NamedTemporaryFile(suffix=".bin") as f:
        f.write(data)
        f.flush()
        proc = await asyncio.create_subprocess_exec(FFMPEG, "-hide_banner", "-i", f.name, "-map", "0:v:0", "-c", "copy", "-f", "null", "-",
                                                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        _, err = await proc.communicate()
    times = re.findall(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", err.decode(errors="ignore"))
    if not times:
        return None
    h, m, s = times[-1]
    return int((int(h) * 3600 + int(m) * 60 + float(s)) * 1000)


async def store_clip(session, kind, seq, t_start_ms, data, content_type, duration_ms=None):
    """Idempotent on session_id + kind + seq. Publishes media.stored for new clips."""
    key = {"session_id": session["id"], "kind": kind, "seq": seq}
    existing = await db.media.find_one(key, {"_id": 0})
    if existing:
        return existing, False
    ctype = (content_type or "video/webm").split(";")[0].strip()
    measured = await probe_duration_ms(data)
    media_id = f"m_{uuid.uuid4().hex}"
    path = await storage.put(f"media/{session['id']}/{kind}-{seq}-{media_id}.{EXT.get(ctype, 'webm')}", data, ctype)
    doc = {"media_id": media_id, **key, "lead_id": session["lead_id"], "t_start_ms": t_start_ms,
           "duration_ms": measured or duration_ms or 10000, "content_type": ctype, "size": len(data),
           "storage_path": path, "is_deleted": False, "created_at": iso()}
    try:
        await db.media.insert_one(dict(doc))
    except DuplicateKeyError:
        return await db.media.find_one(key, {"_id": 0}), False
    events.publish("media.stored", {"media_id": media_id, "session_id": session["id"], "t_start_ms": t_start_ms})
    return doc, True
