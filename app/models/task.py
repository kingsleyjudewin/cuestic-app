from app.extensions import db
from app.utils.datetime_utils import utc_now, format_iso_utc, format_friendly_local


class Task(db.Model):
    """Task model representing work to be done for an event."""
    __tablename__ = "tasks"

    PRIORITY_LOW = "low"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_HIGH = "high"
    PRIORITY_URGENT = "urgent"

    ALL_PRIORITIES = (PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH, PRIORITY_URGENT)

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    priority = db.Column(db.String(20), default=PRIORITY_MEDIUM, nullable=False)
    deadline = db.Column(db.DateTime(timezone=True), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    is_cancelled = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    event = db.relationship("Event", back_populates="tasks")
    creator = db.relationship("User", back_populates="created_tasks")
    assignments = db.relationship("TaskAssignment", back_populates="task", cascade="all, delete-orphan", lazy="dynamic")

    def to_dict(self, include_assignments: bool = False) -> dict:
        """Serialize task to dictionary."""
        data = {
            "id": self.id,
            "event_id": self.event_id,
            "event_name": self.event.name if self.event else None,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "deadline": format_iso_utc(self.deadline),
            "deadline_formatted": format_friendly_local(self.deadline),
            "created_by": self.created_by,
            "creator_name": self.creator.username if self.creator else None,
            "is_cancelled": self.is_cancelled,
            "assignee_count": self.assignments.count(),
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }
        if include_assignments:
            data["assignments"] = [a.to_dict() for a in self.assignments]
        return data
