from app.models.activity_log import ActivityLog
from app.extensions import db


class AuditService:
    @staticmethod
    def log_action(action: str, entity_type: str, entity_id: int = None, actor_user_id: int = None, details: dict = None):
        """Record an administrative or domain action to ActivityLog."""
        return ActivityLog.log(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            details=details,
        )
