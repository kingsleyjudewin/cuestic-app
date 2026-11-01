from datetime import timedelta, timezone
from flask import current_app
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models.task_assignment import TaskAssignment
from app.models.reminder import Reminder
from app.models.task import Task
from app.utils.datetime_utils import utc_now
from app.utils.errors import NotFoundError
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService



class ReminderService:
    @staticmethod
    def get_reminder_by_id(reminder_id: int) -> Reminder:
        """Fetch reminder by ID or raise NotFoundError."""
        reminder = db.session.get(Reminder, reminder_id)
        if not reminder:
            raise NotFoundError(f"Reminder #{reminder_id} not found.")
        return reminder

    @classmethod
    def scan_and_generate_reminders(cls, current_time=None) -> dict:
        """
        Scan active assignments and generate deduplicated reminders for:
        1. Pending confirmations older than configurable threshold (default 24h)
        2. Approaching deadlines within configurable threshold (default 24h)
        3. Passed deadlines without completion (overdue)
        """
        if current_time is None:
            now = utc_now()
        else:
            now = current_time
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)

        conf_hours = current_app.config.get("CONFIRMATION_REMINDER_HOURS", 24)
        deadline_hours = current_app.config.get("DEADLINE_REMINDER_HOURS", 24)

        conf_threshold = now - timedelta(hours=conf_hours)
        deadline_window = now + timedelta(hours=deadline_hours)

        stats = {
            "confirmation_reminders_created": 0,
            "deadline_reminders_created": 0,
            "overdue_reminders_created": 0,
            "reminders_marked_due": 0,
            "total_skipped_duplicates": 0,
        }

        # 1. Unconfirmed assignments older than threshold
        unconfirmed = TaskAssignment.query.join(Task).filter(
            TaskAssignment.status == TaskAssignment.STATUS_AWAITING_CONFIRMATION,
            TaskAssignment.assigned_at <= conf_threshold,
            Task.is_cancelled == False
        ).all()

        for a in unconfirmed:
            dedup_key = f"conf:{a.id}:{a.assigned_at.strftime('%Y%m%d%H%M')}"
            created = cls._create_reminder_if_absent(
                assignment_id=a.id,
                reminder_type=Reminder.TYPE_CONFIRMATION,
                scheduled_at=now,
                deduplication_key=dedup_key
            )
            if created:
                stats["confirmation_reminders_created"] += 1
            else:
                stats["total_skipped_duplicates"] += 1

        # 2. Approaching deadline reminders (within deadline_hours)
        approaching = TaskAssignment.query.join(Task).filter(
            TaskAssignment.status.in_(TaskAssignment.ACTIVE_STATUSES),
            Task.deadline > now,
            Task.deadline <= deadline_window,
            Task.is_cancelled == False
        ).all()

        for a in approaching:
            dedup_key = f"deadline:{a.id}:{a.task.deadline.strftime('%Y%m%d%H%M')}"
            created = cls._create_reminder_if_absent(
                assignment_id=a.id,
                reminder_type=Reminder.TYPE_DEADLINE,
                scheduled_at=now,
                deduplication_key=dedup_key
            )
            if created:
                stats["deadline_reminders_created"] += 1
            else:
                stats["total_skipped_duplicates"] += 1

        # 3. Overdue assignments (past deadline, not completed/cancelled)
        overdue = TaskAssignment.query.join(Task).filter(
            TaskAssignment.status.in_(TaskAssignment.ACTIVE_STATUSES),
            Task.deadline <= now,
            Task.is_cancelled == False
        ).all()

        for a in overdue:
            dedup_key = f"overdue:{a.id}:{a.task.deadline.strftime('%Y%m%d%H%M')}"
            created = cls._create_reminder_if_absent(
                assignment_id=a.id,
                reminder_type=Reminder.TYPE_OVERDUE,
                scheduled_at=now,
                deduplication_key=dedup_key
            )
            if created:
                stats["overdue_reminders_created"] += 1
            else:
                stats["total_skipped_duplicates"] += 1

        # Mark any scheduled reminders whose scheduled_at has arrived as DUE
        scheduled_due = Reminder.query.filter(
            Reminder.status == Reminder.STATUS_SCHEDULED,
            Reminder.scheduled_at <= now
        ).all()

        for r in scheduled_due:
            r.mark_due()
            stats["reminders_marked_due"] += 1

        db.session.commit()
        return stats

    @staticmethod
    def _create_reminder_if_absent(assignment_id: int, reminder_type: str, scheduled_at, deduplication_key: str) -> bool:
        """Create reminder safely if deduplication key does not exist."""
        existing = Reminder.query.filter_by(deduplication_key=deduplication_key).first()
        if existing:
            return False

        try:
            reminder = Reminder(
                assignment_id=assignment_id,
                reminder_type=reminder_type,
                scheduled_at=scheduled_at,
                status=Reminder.STATUS_DUE if scheduled_at <= utc_now() else Reminder.STATUS_SCHEDULED,
                deduplication_key=deduplication_key,
            )
            db.session.add(reminder)
            db.session.flush()

            # Push notification for deadline / overdue reminders
            try:
                assignment = db.session.get(TaskAssignment, assignment_id)
                if reminder_type == Reminder.TYPE_DEADLINE:
                    NotificationService.notify_deadline_reminder(assignment)
                elif reminder_type == Reminder.TYPE_OVERDUE:
                    NotificationService.notify_overdue_reminder(assignment)
            except Exception:
                pass

            return True

        except IntegrityError:
            db.session.rollback()
            return False

    @staticmethod
    def get_due_reminders() -> list[Reminder]:
        """Fetch all reminders currently due or scheduled in the past."""
        now = utc_now()
        return Reminder.query.filter(
            Reminder.status.in_([Reminder.STATUS_DUE, Reminder.STATUS_SCHEDULED]),
            Reminder.scheduled_at <= now
        ).order_by(Reminder.scheduled_at.asc()).all()

    @staticmethod
    def action_reminder(reminder: Reminder, actor_user_id: int = None) -> Reminder:
        """Mark reminder as actioned."""
        reminder.mark_actioned()
        AuditService.log_action(
            action="REMINDER_ACTIONED",
            entity_type="Reminder",
            entity_id=reminder.id,
            actor_user_id=actor_user_id,
            details={"reminder_type": reminder.reminder_type, "assignment_id": reminder.assignment_id}
        )
        db.session.commit()
        return reminder
