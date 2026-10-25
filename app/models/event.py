from app.extensions import db
from app.utils.datetime_utils import utc_now, format_iso_utc, to_local_datetime
from app.utils.errors import ValidationError


class Event(db.Model):
    """Event model representing departmental club events."""
    __tablename__ = "events"

    STATUS_DRAFT = "draft"
    STATUS_UPCOMING = "upcoming"
    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    ALL_STATUSES = (STATUS_DRAFT, STATUS_UPCOMING, STATUS_ACTIVE, STATUS_COMPLETED, STATUS_CANCELLED)

    ALLOWED_TRANSITIONS = {
        STATUS_DRAFT: {STATUS_UPCOMING, STATUS_ACTIVE, STATUS_CANCELLED},
        STATUS_UPCOMING: {STATUS_ACTIVE, STATUS_COMPLETED, STATUS_CANCELLED},
        STATUS_ACTIVE: {STATUS_COMPLETED, STATUS_CANCELLED},
        STATUS_COMPLETED: set(),  # terminal state
        STATUS_CANCELLED: set(),  # terminal state
    }

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    start_at = db.Column(db.DateTime(timezone=True), nullable=False)
    end_at = db.Column(db.DateTime(timezone=True), nullable=True)
    location = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(30), default=STATUS_UPCOMING, nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    creator = db.relationship("User", back_populates="created_events")
    tasks = db.relationship("Task", back_populates="event", cascade="all, delete-orphan", lazy="dynamic")

    def can_transition_to(self, new_status: str) -> bool:
        """Check if transition from current status to new_status is allowed."""
        if new_status == self.status:
            return True
        allowed = self.ALLOWED_TRANSITIONS.get(self.status, set())
        return new_status in allowed

    def transition_to(self, new_status: str):
        """Transition status or raise ValidationError."""
        if not self.can_transition_to(new_status):
            raise ValidationError(
                f"Cannot transition event status from '{self.status}' to '{new_status}'.",
                details={"current_status": self.status, "requested_status": new_status}
            )
        self.status = new_status

    def to_dict(self) -> dict:
        """Serialize event to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "start_at": format_iso_utc(self.start_at),
            "end_at": format_iso_utc(self.end_at),
            "location": self.location,
            "status": self.status,
            "created_by": self.created_by,
            "creator_name": self.creator.username if self.creator else None,
            "task_count": self.tasks.count(),
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }
