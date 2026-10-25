import json
from app.extensions import db
from app.utils.datetime_utils import utc_now, format_iso_utc


class ActivityLog(db.Model):
    """Audit log model for administrative and assignment lifecycle actions."""
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    details_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    actor = db.relationship("User")

    @classmethod
    def log(cls, action: str, entity_type: str, entity_id: int = None, actor_user_id: int = None, details: dict = None):
        """Create and persist an activity log entry."""
        # Sanitize details: remove sensitive keywords if present
        sanitized_details = None
        if details:
            sanitized = {}
            for k, v in details.items():
                if any(secret_term in k.lower() for secret_term in ("password", "token", "secret", "auth")):
                    continue
                sanitized[k] = v
            sanitized_details = json.dumps(sanitized)

        entry = cls(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details_json=sanitized_details,
        )
        db.session.add(entry)
        return entry

    def to_dict(self) -> dict:
        """Serialize activity log entry."""
        details = {}
        if self.details_json:
            try:
                details = json.loads(self.details_json)
            except Exception:
                details = {"raw": self.details_json}

        return {
            "id": self.id,
            "actor_user_id": self.actor_user_id,
            "actor_username": self.actor.username if self.actor else None,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "details": details,
            "created_at": format_iso_utc(self.created_at),
        }
