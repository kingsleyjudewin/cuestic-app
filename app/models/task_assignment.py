from datetime import datetime, timezone
from app.extensions import db
from app.utils.datetime_utils import utc_now, format_iso_utc, format_friendly_local
from app.utils.errors import ValidationError


class TaskAssignment(db.Model):
    """TaskAssignment model tracking individual member assignment and state."""
    __tablename__ = "task_assignments"
    __table_args__ = (
        db.UniqueConstraint("task_id", "member_id", name="uq_task_assignment_task_member"),
    )

    STATUS_AWAITING_CONFIRMATION = "awaiting_confirmation"
    STATUS_ACCEPTED = "accepted"
    STATUS_DECLINED = "declined"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_SUBMITTED = "submitted"
    STATUS_COMPLETED = "completed"
    STATUS_BLOCKED = "blocked"
    STATUS_CANCELLED = "cancelled"

    ALL_STATUSES = (
        STATUS_AWAITING_CONFIRMATION,
        STATUS_ACCEPTED,
        STATUS_DECLINED,
        STATUS_IN_PROGRESS,
        STATUS_SUBMITTED,
        STATUS_COMPLETED,
        STATUS_BLOCKED,
        STATUS_CANCELLED,
    )

    TERMINAL_STATUSES = (STATUS_COMPLETED, STATUS_CANCELLED)
    ACTIVE_STATUSES = (
        STATUS_AWAITING_CONFIRMATION,
        STATUS_ACCEPTED,
        STATUS_IN_PROGRESS,
        STATUS_SUBMITTED,
        STATUS_BLOCKED,
    )

    ALLOWED_TRANSITIONS = {
        STATUS_AWAITING_CONFIRMATION: {
            STATUS_ACCEPTED,
            STATUS_DECLINED,
            STATUS_IN_PROGRESS,
            STATUS_CANCELLED,
        },
        STATUS_ACCEPTED: {
            STATUS_IN_PROGRESS,
            STATUS_DECLINED,
            STATUS_BLOCKED,
            STATUS_CANCELLED,
        },
        STATUS_DECLINED: {
            STATUS_AWAITING_CONFIRMATION,
            STATUS_CANCELLED,
        },
        STATUS_IN_PROGRESS: {
            STATUS_SUBMITTED,
            STATUS_BLOCKED,
            STATUS_CANCELLED,
        },
        STATUS_SUBMITTED: {
            STATUS_COMPLETED,
            STATUS_IN_PROGRESS,  # rejected submission / rework requested
            STATUS_CANCELLED,
        },
        STATUS_BLOCKED: {
            STATUS_IN_PROGRESS,
            STATUS_CANCELLED,
        },
        STATUS_COMPLETED: {
            STATUS_IN_PROGRESS,  # reopening by admin
        },
        STATUS_CANCELLED: set(),
    }

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id", ondelete="RESTRICT"), nullable=False, index=True)
    assigned_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    status = db.Column(db.String(30), default=STATUS_AWAITING_CONFIRMATION, nullable=False, index=True)
    assigned_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    confirmed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completion_note = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    task = db.relationship("Task", back_populates="assignments")
    member = db.relationship("Member", back_populates="assignments")
    assigner = db.relationship("User", back_populates="assigned_tasks")
    message_logs = db.relationship("MessageLog", back_populates="assignment", cascade="all, delete-orphan", lazy="dynamic")
    reminders = db.relationship("Reminder", back_populates="assignment", cascade="all, delete-orphan", lazy="dynamic")

    def can_transition_to(self, target_status: str) -> bool:
        """Check if transition to target_status is valid."""
        if target_status == self.status:
            return True
        allowed = self.ALLOWED_TRANSITIONS.get(self.status, set())
        return target_status in allowed

    def transition_to(self, target_status: str, note: str = None):
        """Transition assignment status with timestamp updates and validation."""
        if not self.can_transition_to(target_status):
            raise ValidationError(
                f"Cannot transition assignment status from '{self.status}' to '{target_status}'.",
                details={"current_status": self.status, "target_status": target_status}
            )

        now = utc_now()
        if target_status == self.STATUS_ACCEPTED:
            if not self.confirmed_at:
                self.confirmed_at = now
        elif target_status == self.STATUS_IN_PROGRESS:
            if not self.confirmed_at:
                self.confirmed_at = now
            if not self.started_at:
                self.started_at = now
        elif target_status == self.STATUS_SUBMITTED:
            self.submitted_at = now
            if note:
                self.completion_note = note
        elif target_status == self.STATUS_COMPLETED:
            self.completed_at = now
            if note:
                self.completion_note = note

        self.status = target_status
        self.updated_at = now

    def is_overdue(self) -> bool:
        """Check if assignment deadline has passed without completion."""
        if self.status in (self.STATUS_COMPLETED, self.STATUS_CANCELLED):
            return False
        if not self.task or not self.task.deadline:
            return False
        now = utc_now()
        dl = self.task.deadline
        if dl.tzinfo is None:
            dl = dl.replace(tzinfo=timezone.utc)
        return now > dl

    def to_dict(self, include_sensitive: bool = True) -> dict:
        """Serialize assignment to dictionary."""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "task_title": self.task.title if self.task else None,
            "task_description": self.task.description if self.task else None,
            "task_priority": self.task.priority if self.task else None,
            "deadline": format_iso_utc(self.task.deadline) if self.task else None,
            "deadline_formatted": format_friendly_local(self.task.deadline) if self.task else None,
            "event_id": self.task.event_id if self.task else None,
            "event_name": self.task.event.name if (self.task and self.task.event) else None,
            "member_id": self.member_id,
            "member_name": self.member.full_name if self.member else None,
            "member_phone": (self.member.phone_number if include_sensitive else "*****") if self.member else None,
            "member_reg_no": self.member.registration_number if self.member else None,
            "team_id": self.member.team_id if self.member else None,
            "team_name": self.member.team.name if (self.member and self.member.team) else None,
            "assigned_by": self.assigned_by,
            "assigner_name": self.assigner.username if self.assigner else None,
            "status": self.status,
            "is_overdue": self.is_overdue(),
            "assigned_at": format_iso_utc(self.assigned_at),
            "confirmed_at": format_iso_utc(self.confirmed_at),
            "started_at": format_iso_utc(self.started_at),
            "submitted_at": format_iso_utc(self.submitted_at),
            "completed_at": format_iso_utc(self.completed_at),
            "completion_note": self.completion_note,
            "updated_at": format_iso_utc(self.updated_at),
        }
