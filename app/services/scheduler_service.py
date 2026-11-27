"""Background reminder scheduling that is safe to run in several processes at once.

Every Gunicorn worker (or Render instance) may start this scheduler. Each scan opens a
database transaction and first takes a PostgreSQL transaction-scoped advisory lock
(`pg_try_advisory_xact_lock`). Only one process obtains the lock; the others skip that tick.
A transaction-scoped lock is used on purpose: Neon's pooled endpoint runs PgBouncer in
transaction mode, where session-level advisory locks are not reliable.

Exactly-once delivery is guaranteed separately by the unique `reminders.deduplication_key`
and by sending push notifications only after the reminder rows are committed.
"""
import logging
import threading
from datetime import timedelta

from app.utils.datetime_utils import utc_now

logger = logging.getLogger(__name__)

# Arbitrary constant identifying the reminder-scan lock in pg_locks.
REMINDER_SCAN_LOCK_KEY = 482_190_017

_process_lock = threading.Lock()
_scheduler = None


def run_reminder_scan(app, notify: bool = True):
    """Run one reminder scan inside an app context. Returns the stats dict, or None if skipped."""
    from app.services.reminder_service import ReminderService

    with app.app_context():
        if not _process_lock.acquire(blocking=False):
            logger.info("Reminder scan already running in this process; skipping tick.")
            return None
        try:
            stats = ReminderService.scan_and_generate_reminders(acquire_lock=True, notify=notify)
            if stats.get("skipped_lock_held"):
                logger.info("Reminder scan skipped: another process holds the scan lock.")
            else:
                logger.info("Reminder scan completed: %s", stats)
            return stats
        except Exception:
            logger.exception("Reminder scan failed; it will be retried on the next tick.")
            return None
        finally:
            _process_lock.release()


def start_background_scheduler(app):
    """Start the APScheduler interval job once per process."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        interval = max(1, int(app.config.get("REMINDER_SCAN_INTERVAL_MINUTES", 15)))
        scheduler = BackgroundScheduler(timezone="UTC", daemon=True)
        scheduler.add_job(
            func=run_reminder_scan,
            args=[app],
            trigger="interval",
            minutes=interval,
            id="reminder_scan_job",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
            # First scan shortly after boot, so reminders missed during a restart are caught up.
            next_run_time=utc_now() + timedelta(seconds=60),
        )
        scheduler.start()
        _scheduler = scheduler
        app.logger.info("Background reminder scheduler started (every %s min).", interval)
        return scheduler
    except Exception as e:
        app.logger.error("Failed to start background scheduler: %s", e)
        return None
