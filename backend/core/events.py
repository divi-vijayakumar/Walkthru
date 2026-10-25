"""Tiny in-process event bus so modules don't import each other (e.g. media.stored -> Itemizer)."""
import asyncio
import logging

logger = logging.getLogger("events")
_subs = {}


def subscribe(name, fn):
    _subs.setdefault(name, []).append(fn)


def publish(name, data):
    for fn in _subs.get(name, []):
        asyncio.create_task(_run(fn, name, data))


async def _run(fn, name, data):
    try:
        await fn(data)
    except Exception:
        logger.exception("handler for %s failed", name)
