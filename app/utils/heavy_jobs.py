"""Concurrency limits for slow endpoints (OCR, DOCX/chart generation, AI calls).

The API runs a small fixed number of request threads. Without a limit, a handful of users
generating reports at the same moment would occupy every thread and stall normal requests
(login, dashboard, chat). Each heavy endpoint must acquire a slot from its pool first:

* "cpu" — OCR, DOCX, charts (CPU/memory heavy). Size: MAX_CONCURRENT_HEAVY_JOBS (default 2).
* "ai"  — calls to external AI providers (mostly waiting on the network).
          Size: MAX_CONCURRENT_AI_JOBS (default 4).

A request waits up to HEAVY_JOB_QUEUE_TIMEOUT seconds for a slot, then receives HTTP 503
with Retry-After, which the client can show as "Server busy, please retry".
This keeps the existing synchronous API contract; see DEPLOYMENT.md for when to move these
jobs to a queue.
"""
import os
import threading
from functools import wraps

from flask import current_app

from app.utils.errors import AppError

_pools: dict = {}
_pools_lock = threading.Lock()

_DEFAULT_SIZES = {"cpu": ("MAX_CONCURRENT_HEAVY_JOBS", 2), "ai": ("MAX_CONCURRENT_AI_JOBS", 4)}


class ServerBusyError(AppError):
    status_code = 503
    code = "SERVER_BUSY"


def _pool(kind: str) -> threading.BoundedSemaphore:
    with _pools_lock:
        sem = _pools.get(kind)
        if sem is None:
            key, default = _DEFAULT_SIZES.get(kind, ("MAX_CONCURRENT_HEAVY_JOBS", 2))
            size = current_app.config.get(key) or int(os.environ.get(key, default))
            sem = threading.BoundedSemaphore(max(1, int(size)))
            _pools[kind] = sem
        return sem


def heavy_job(kind: str = "cpu"):
    """Decorator limiting how many requests of this kind run at once (per process)."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if current_app.config.get("TESTING"):
                return f(*args, **kwargs)
            timeout = float(current_app.config.get("HEAVY_JOB_QUEUE_TIMEOUT", 60))
            sem = _pool(kind)
            if not sem.acquire(timeout=timeout):
                raise ServerBusyError(
                    "The server is busy processing other reports right now. Please try again in a minute.",
                    details={"retry_after_seconds": 30, "pool": kind},
                )
            try:
                return f(*args, **kwargs)
            finally:
                sem.release()
        return wrapper
    return decorator
