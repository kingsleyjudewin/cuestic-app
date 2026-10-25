from app.extensions import db
from app.utils.datetime_utils import utc_now, format_iso_utc


class MessageLog(db.Model):
    """MessageLog model for recording WhatsApp message drafts and user actions."""
    __tablename__ = "message_logs"

    TYPE_INITIAL_ASSIGNMENT = "initial_assignment"
    TYPE_CONFIRMATION_REMINDER = "confirmation_reminder"
    TYPE_DEADLINE_REMINDER = "deadline_reminder"
    TYPE_OVERDUE_REMINDER = "overdue_reminder"
    TYPE_CUSTOM = "custom"

    ALL_TYPES = (
        TYPE_INITIAL_ASSIGNMENT,
        TYPE_CONFIRMATION_REMINDER,
        TYPE_DEADLINE_REMINDER,
        TYPE_OVERDUE_REMINDER,
        TYPE_CUSTOM,
    )

    STATUS_DRAFTED = "drafted"
    STATUS_LINK_OPENED = "link_opened"
    STATUS_MARKED_SENT = "marked_sent"
    STATUS_ACTIONED = "actioned"
    STATUS_FAILED = "failed"

    ALL_STATUSES = (
        STATUS_DRAFTED,
        STATUS_LINK_OPENED,
        STATUS_MARKED_SENT,
        STATUS_ACTIONED,
        STATUS_FAILED,
    )

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey("task_assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    message_type = db.Column(db.String(50), default=TYPE_INITIAL_ASSIGNMENT, nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default=STATUS_DRAFTED, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    action_recorded_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    assignment = db.relationship("TaskAssignment", back_populates="message_logs")
    creator = db.relationship("User")

    def record_action(self, action_status: str):
        """Record administrator interaction with the message."""
        self.status = action_status
        self.action_recorded_at = utc_now()

    def to_dict(self) -> dict:
        """Serialize message log entry."""
        return {
            "id": self.id,
            "assignment_id": self.assignment_id,
            "created_by": self.created_by,
            "creator_name": self.creator.username if self.creator else None,
            "message_type": self.message_type,
            "message_text": self.message_text,
            "status": self.status,
            "created_at": format_iso_utc(self.created_at),
            "action_recorded_at": format_iso_utc(self.action_recorded_at),
        }
