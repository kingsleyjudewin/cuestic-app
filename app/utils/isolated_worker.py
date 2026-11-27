"""Run CPU-heavy jobs (OCR) in a separate, lower-priority process.

Why
---
Load testing on a 1-CPU instance showed that OCR running inside the web process starved
every other request (API p50 rose from ~4 ms to ~2.9 s), and abandoned OCR requests kept
burning CPU. Running OCR in a child process:
  * lets the OS favour the web process (the child is `nice`d), so normal API calls stay fast;
  * caps the native thread pools (onnxruntime / OpenCV) to OCR_THREADS instead of one per host core;
  * enforces a hard timeout (OCR_TIMEOUT_SECONDS) by killing the child;
  * contains crashes and out-of-memory kills to the child, never the web server.

The synchronous API contract is unchanged: the request waits for the result.
Disabled automatically under TESTING (jobs run inline) or with OCR_ISOLATION=false.
"""
import concurrent.futures as cf
import logging
import multiprocessing as mp
import os
import threading
from concurrent.futures.process import BrokenProcessPool

from flask import current_app, has_app_context

from app.utils.errors import AppError

logger = logging.getLogger(__name__)

_pool = None
_pool_lock = threading.Lock()


class IsolatedJobError(AppError):
    status_code = 503
    code = "JOB_FAILED"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _init_worker(nice_level: int, threads: int):
    """Runs once in each child process before any job."""
    try:
        os.nice(nice_level)
    except Exception:
        pass
    os.environ["OMP_NUM_THREADS"] = str(threads)
    os.environ["OPENBLAS_NUM_THREADS"] = str(threads)
    try:
        import cv2
        cv2.setNumThreads(threads)
    except Exception:
        pass
    try:
        # RapidOCR builds onnxruntime sessions without a thread limit (one thread per host
        # core, ignoring container CPU quotas). Give it pre-configured session options.
        import onnxruntime as ort
        import rapidocr_onnxruntime.utils as rapid_utils

        def _limited_session_options():
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = threads
            opts.inter_op_num_threads = 1
            return opts

        rapid_utils.SessionOptions = _limited_session_options
    except Exception:
        pass


def _enabled() -> bool:
    if os.environ.get("OCR_ISOLATION", "true").lower() in ("0", "false", "no", "off"):
        return False
    if has_app_context() and current_app.config.get("TESTING"):
        return False
    return True


def _get_pool() -> cf.ProcessPoolExecutor:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = cf.ProcessPoolExecutor(
                max_workers=max(1, _env_int("OCR_PROCESS_WORKERS", 1)),
                mp_context=mp.get_context("spawn"),
                initializer=_init_worker,
                initargs=(_env_int("OCR_NICE", 10), max(1, _env_int("OCR_THREADS", 1))),
            )
        return _pool


def _reset_pool():
    """Kill worker processes (e.g. a stuck job) and start fresh on the next call."""
    global _pool
    with _pool_lock:
        pool, _pool = _pool, None
    if pool is None:
        return
    for proc in list(getattr(pool, "_processes", {}).values()):
        try:
            proc.kill()
        except Exception:
            pass
    pool.shutdown(wait=False, cancel_futures=True)


def run_isolated(fn, *args, timeout: float = None, **kwargs):
    """Run fn(*args, **kwargs) in the worker process and return its result."""
    if not _enabled():
        return fn(*args, **kwargs)
    timeout = timeout or _env_int("OCR_TIMEOUT_SECONDS", 100)
    future = _get_pool().submit(fn, *args, **kwargs)
    try:
        return future.result(timeout=timeout)
    except cf.TimeoutError:
        logger.error("Isolated job %s exceeded %ss; worker process killed.", getattr(fn, "__name__", fn), timeout)
        _reset_pool()
        raise IsolatedJobError(
            "Processing this file took too long. Try a smaller file or fewer pages.",
            code="JOB_TIMEOUT",
        )
    except BrokenProcessPool:
        logger.error("Isolated job %s crashed (likely out of memory); worker restarted.", getattr(fn, "__name__", fn))
        _reset_pool()
        raise IsolatedJobError(
            "The server ran out of resources while processing this file. Please try again with a smaller file.",
            code="JOB_CRASHED",
        )


def ocr_attendance_job(file_bytes: bytes, filename: str, member_directory: dict, existing_records):
    """Top-level (picklable) OCR entry point executed inside the worker process."""
    from app.services.attendance_ocr_service import AttendanceOCRService
    return AttendanceOCRService.process_attendance_file(
        file_bytes=file_bytes,
        filename=filename,
        member_directory=member_directory,
        existing_records=existing_records,
    )
