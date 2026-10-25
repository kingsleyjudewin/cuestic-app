from app.extensions import db
from app.utils.datetime_utils import utc_now, format_iso_utc


class Reminder(db.Model):
    """Reminder model for tracking pending confirmations and deadline follow-ups."""
    __tablename__ = "reminders"

    TYPE_CONFIRMATION = "confirmation_reminder"
    TYPE_DEADLINE = "deadline_reminder"
    TYPE_OVERDUE = "overdue_reminder"
    TYPE_CUSTOM = "custom"

    ALL_TYPES = (TYPE_CONFIRMATION, TYPE_DEADLINE, TYPE_OVERDUE, TYPE_CUSTOM)

    STATUS_SCHEDULED = "scheduled"
    STATUS_DUE = "due"
    STATUS_ACTIONED = "actioned"
    STATUS_CANCELLED = "cancelled"
    STATUS_SKIPPED = "skipped"

    ALL_STATUSES = (STATUS_SCHEDULED, STATUS_DUE, STATUS_ACTIONED, STATUS_CANCELLED, STATUS_SKIPPED)

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey("task_assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    reminder_type = db.Column(db.String(50), nullable=False)
    scheduled_at = db.Column(db.DateTime(timezone=True), nullable=False)
    status = db.Column(db.String(30), default=STATUS_SCHEDULED, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    actioned_at = db.Column(db.DateTime(timezone=True), nullable=True)
    deduplication_key = db.Column(db.String(150), unique=True, nullable=False, index=True)

    # Relationships
    assignment = db.relationship("TaskAssignment", back_populates="reminders")

    def mark_actioned(self):
        """Mark reminder as actioned."""
        self.status = self.STATUS_ACTIONED
        self.actioned_at = utc_now()

    def mark_cancelled(self):
        """Cancel reminder."""
        self.status = self.STATUS_CANCELLED

    def mark_due(self):
        """Mark scheduled reminder as due."""
        if self.status == self.STATUS_SCHEDULED:
            self.status = self.STATUS_DUE

    def to_dict(self) -> dict:
        """Serialize reminder to dictionary."""
        return {
            "id": self.id,
            "assignment_id": self.assignment_id,
            "task_id": self.assignment.task_id if self.assignment else None,
            "task_title": self.assignment.task.title if (self.assignment and self.assignment.task) else None,
            "member_id": self.assignment.member_id if self.assignment else None,
            "member_name": self.assignment.member.full_name if (self.assignment and self.assignment.member) else None,
            "reminder_type": self.reminder_type,
            "scheduled_at": format_iso_utc(self.scheduled_at),
            "status": self.status,
            "deduplication_key": self.deduplication_key,
            "created_at": format_iso_utc(self.created_at),
            "actioned_at": format_iso_utc(self.actioned_at),
        }
