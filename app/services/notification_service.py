import os
import json
import logging
from flask import current_app
from app.extensions import db
from app.models.device_token import DeviceToken
from app.models.task_assignment import TaskAssignment
from app.models.user import User
from app.utils.datetime_utils import utc_now

logger = logging.getLogger(__name__)

_firebase_initialized = False


def _get_firebase_app():
    """Lazily initialize Firebase Admin SDK using server credentials."""
    global _firebase_initialized
    if _firebase_initialized:
        return True

    try:
        import firebase_admin
        from firebase_admin import credentials

        cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH")
        cred_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")

        if cred_path:
            if not os.path.isabs(cred_path):
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                cred_path = os.path.join(base_dir, cred_path)
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                _firebase_initialized = True
                logger.info("Firebase Admin initialized from credentials file: %s", cred_path)
                return True
            else:
                logger.warning("Firebase credentials file specified but not found at: %s", cred_path)
        elif cred_json:
            service_account_info = json.loads(cred_json)
            cred = credentials.Certificate(service_account_info)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            logger.info("Firebase Admin initialized from JSON env variable.")
            return True
        else:
            logger.info("Firebase Admin credentials not set. Running in development/mock notification mode.")
            return False
    except Exception as e:
        logger.warning("Could not initialize Firebase Admin SDK: %s", e)
        return False


class NotificationService:
    @staticmethod
    def register_device_token(user_id: int, token: str, device_type: str = "android", device_name: str = None) -> DeviceToken:
        """Register or activate an FCM device token for an authenticated user."""
        token_str = token.strip()
        existing = DeviceToken.query.filter_by(token=token_str).first()
        now = utc_now()

        if existing:
            existing.user_id = user_id
            existing.device_type = device_type
            if device_name:
                existing.device_name = device_name
            existing.is_active = True
            existing.updated_at = now
            existing.last_used_at = now
            db.session.commit()
            return existing

        new_token = DeviceToken(
            user_id=user_id,
            token=token_str,
            device_type=device_type,
            device_name=device_name,
            is_active=True,
            created_at=now,
            updated_at=now,
            last_used_at=now,
        )
        db.session.add(new_token)
        db.session.commit()
        return new_token

    @staticmethod
    def unregister_device_token(user_id: int, token: str) -> bool:
        """Deactivate a device token for a user."""
        token_str = token.strip()
        existing = DeviceToken.query.filter_by(user_id=user_id, token=token_str).first()
        if existing:
            existing.is_active = False
            existing.updated_at = utc_now()
            db.session.commit()
            return True
        return False

    @staticmethod
    def send_push_notification(user_id: int, title: str, body: str, data: dict = None) -> int:
        """
        Send push notification to all active devices registered to user_id.
        Returns count of successfully notified devices.
        """
        tokens = DeviceToken.query.filter_by(user_id=user_id, is_active=True).all()
        if not tokens:
            logger.info("No active device tokens found for user_id=%s", user_id)
            return 0

        data_payload = {str(k): str(v) for k, v in (data or {}).items()}
        has_fb = _get_firebase_app()
        sent_count = 0

        for dev_token in tokens:
            if has_fb:
                try:
                    import firebase_admin
                    from firebase_admin import messaging

                    message = messaging.Message(
                        notification=messaging.Notification(
                            title=title,
                            body=body,
                        ),
                        data=data_payload,
                        token=dev_token.token,
                    )
                    messaging.send(message)
                    dev_token.last_used_at = utc_now()
                    sent_count += 1
                except Exception as ex:
                    logger.error("Failed to deliver FCM push to device %s: %s", dev_token.id, ex)
                    # If unregistered or invalid, deactivate
                    err_str = str(ex).lower()
                    if "unregistered" in err_str or "invalid" in err_str:
                        dev_token.is_active = False
            else:
                # Mock / logging mode for local testing and dev
                logger.info(
                    "[FCM MOCK PUSH] to user=%s device=%s: title='%s', body='%s', data=%s",
                    user_id, dev_token.id, title, body, data_payload
                )
                dev_token.last_used_at = utc_now()
                sent_count += 1

        db.session.commit()
        return sent_count

    @classmethod
    def notify_new_assignment(cls, assignment: TaskAssignment, actor_user: User = None) -> int:
        """Send concise push notification when a new task is assigned."""
        if not assignment or not assignment.member:
            return 0

        user_id = assignment.member.linked_user_id
        if not user_id:
            # Check if there is an active user with matching email or username
            return 0

        event_name = assignment.task.event.name if assignment.task and assignment.task.event else "Club Event"
        task_title = assignment.task.title if assignment.task else "Task"

        title = "New task assigned"
        body = f"{event_name} — {task_title}"
        data = {
            "type": "new_assignment",
            "assignment_id": str(assignment.id),
            "task_id": str(assignment.task_id),
            "event_id": str(assignment.task.event_id if assignment.task else ""),
        }
        return cls.send_push_notification(user_id=user_id, title=title, body=body, data=data)

    @classmethod
    def notify_assignment_update(cls, assignment: TaskAssignment, new_status: str) -> int:
        """Send push notification on assignment status updates."""
        if not assignment or not assignment.member:
            return 0

        user_id = assignment.member.linked_user_id
        if not user_id:
            return 0

        event_name = assignment.task.event.name if assignment.task and assignment.task.event else "Club Event"
        task_title = assignment.task.title if assignment.task else "Task"

        title = "Task status updated"
        body = f"{event_name} — {task_title}: {new_status}"
        data = {
            "type": "assignment_update",
            "assignment_id": str(assignment.id),
            "task_id": str(assignment.task_id),
            "status": new_status,
        }
        return cls.send_push_notification(user_id=user_id, title=title, body=body, data=data)

    @classmethod
    def notify_deadline_reminder(cls, assignment: TaskAssignment) -> int:
        """Send push notification for upcoming deadline."""
        if not assignment or not assignment.member:
            return 0

        user_id = assignment.member.linked_user_id
        if not user_id:
            return 0

        event_name = assignment.task.event.name if assignment.task and assignment.task.event else "Club Event"
        task_title = assignment.task.title if assignment.task else "Task"

        title = "Upcoming deadline"
        body = f"{event_name} — {task_title}"
        data = {
            "type": "deadline_reminder",
            "assignment_id": str(assignment.id),
            "task_id": str(assignment.task_id),
        }
        return cls.send_push_notification(user_id=user_id, title=title, body=body, data=data)

    @classmethod
    def notify_overdue_reminder(cls, assignment: TaskAssignment) -> int:
        """Send push notification for overdue assignment."""
        if not assignment or not assignment.member:
            return 0

        user_id = assignment.member.linked_user_id
        if not user_id:
            return 0

        event_name = assignment.task.event.name if assignment.task and assignment.task.event else "Club Event"
        task_title = assignment.task.title if assignment.task else "Task"

        title = "Task overdue"
        body = f"{event_name} — {task_title}"
        data = {
            "type": "overdue_reminder",
            "assignment_id": str(assignment.id),
            "task_id": str(assignment.task_id),
        }
        return cls.send_push_notification(user_id=user_id, title=title, body=body, data=data)
