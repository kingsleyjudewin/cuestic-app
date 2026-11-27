"""Gunicorn settings for production (Render). Every value can be overridden with env vars.

Why ONE worker by default
-------------------------
Teams/events/members/communities/chat caches live in process memory. With several worker
processes, a write handled by one worker is invisible to the others until their cache TTL
expires (up to 30 minutes). One worker with many threads keeps every user on the same cache.
Auth tokens are revalidated against the database on each request (AUTH_CACHE_REVALIDATE), and
reminder scans take a database lock, so those two stay correct even with more workers.
Idle memory is ~225 MB per worker; OCR adds ~150-250 MB while it runs.
"""
import os
import threading

bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", "12"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", "5"))
# Render's proxy sets X-Forwarded-*; it is the only thing that can reach the container port.
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "*")

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")
# %(U)s is the path WITHOUT the query string, so OAuth codes or other query secrets are never logged.
access_log_format = '%(h)s "%(m)s %(U)s" %(s)s %(B)sB %(M)sms'

if workers > 1:
    print(
        f"[gunicorn.conf] WARNING: WEB_CONCURRENCY={workers}. In-memory caches are per process; "
        "data edited via one worker can look stale on another for up to 30 minutes."
    )


def post_worker_init(worker):
    """Warm caches in the background so the first real requests are fast."""
    def _warm():
        try:
            import wsgi
            wsgi.prewarm_cache()
        except Exception as exc:  # never let warm-up kill a worker
            worker.log.warning("Cache pre-warm skipped: %s", type(exc).__name__)

    threading.Thread(target=_warm, name="cache-prewarm", daemon=True).start()
