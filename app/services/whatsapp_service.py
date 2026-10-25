import urllib.parse
from flask import current_app
from app.extensions import db
from app.models.member import Member
from app.models.task import Task
from app.models.event import Event
from app.models.task_assignment import TaskAssignment
from app.models.message_log import MessageLog
from app.models.user import User
from app.utils.phone_numbers import normalize_phone_number
from app.utils.datetime_utils import format_friendly_local
from app.utils.errors import ValidationError, NotFoundError
from app.services.audit_service import AuditService


class WhatsAppService:
    @staticmethod
    def build_assignment_message(member: Member, task: Task, event: Event, assignment: TaskAssignment, tz_name: str = None) -> str:
        """
        Build personalized WhatsApp message draft for an event task assignment.
        Uses actual database values and localized deadline string.
        """
        deadline_str = format_friendly_local(task.deadline, tz_name)
        desc_line = f"\nDetails: {task.description}" if task.description else ""

        message = (
            f"Hi {member.full_name},\n\n"
            f"You have been assigned a task for {event.name}.\n\n"
            f"Task: {task.title}{desc_line}\n"
            f"Priority: {task.priority.capitalize()}\n"
            f"Deadline: {deadline_str}\n\n"
            f"Please confirm this assignment and update your progress through the club task application.\n\n"
            f"— Department Club Team"
        )
        return message

    @staticmethod
    def build_reminder_message(member: Member, task: Task, event: Event, assignment: TaskAssignment,
                               reminder_type: str, tz_name: str = None) -> str:
        """Build follow-up / reminder messages for unconfirmed, upcoming, or overdue tasks."""
        deadline_str = format_friendly_local(task.deadline, tz_name)

        if reminder_type == MessageLog.TYPE_CONFIRMATION_REMINDER:
            return (
                f"Hi {member.full_name},\n\n"
                f"Reminder: You have a pending task assignment for {event.name}.\n\n"
                f"Task: {task.title}\n"
                f"Deadline: {deadline_str}\n\n"
                f"Please open the club app to confirm whether you accept this task.\n\n"
                f"— Department Club Team"
            )
        elif reminder_type == MessageLog.TYPE_DEADLINE_REMINDER:
            return (
                f"Hi {member.full_name},\n\n"
                f"Friendly reminder: The deadline for your task '{task.title}' for {event.name} is approaching.\n\n"
                f"Deadline: {deadline_str}\n\n"
                f"Please update your task progress in the club app.\n\n"
                f"— Department Club Team"
            )
        elif reminder_type == MessageLog.TYPE_OVERDUE_REMINDER:
            return (
                f"Hi {member.full_name},\n\n"
                f"URGENT: Your task '{task.title}' for {event.name} was due on {deadline_str} and is now overdue.\n\n"
                f"Please contact your team lead or submit your progress immediately.\n\n"
                f"— Department Club Team"
            )
        else:
            return WhatsAppService.build_assignment_message(member, task, event, assignment, tz_name)

    @classmethod
    def prepare_message_draft(cls, assignment: TaskAssignment, actor_user: User,
                              message_type: str = MessageLog.TYPE_INITIAL_ASSIGNMENT) -> dict:
        """
        Validate recipient consent, normalize phone number, build personalized text,
        record draft in MessageLog, and return draft info and wa.me URL.
        """
        member = assignment.member
        if not member:
            raise NotFoundError("Assignment has no associated member.")

        if not member.is_active:
            raise ValidationError(
                f"Member {member.full_name} is inactive. Cannot send WhatsApp messages to deactivated members.",
                details={"member_id": member.id}
            )

        if not member.whatsapp_opt_in:
            raise ValidationError(
                f"Member {member.full_name} has opted out of WhatsApp communications.",
                details={"member_id": member.id, "whatsapp_opt_in": False}
            )

        task = assignment.task
        event = task.event if task else None
        if not task or not event:
            raise NotFoundError("Associated task or event not found.")

        # Phone normalization
        phone_info = normalize_phone_number(member.phone_number, member.country_code or "IN")
        wa_phone = phone_info["wa_phone"]

        # Build message
        tz_name = current_app.config.get("APP_TIMEZONE", "Asia/Kolkata")
        if message_type == MessageLog.TYPE_INITIAL_ASSIGNMENT:
            message_text = cls.build_assignment_message(member, task, event, assignment, tz_name)
        else:
            message_text = cls.build_reminder_message(member, task, event, assignment, message_type, tz_name)

        # URL encode text
        encoded_text = urllib.parse.quote(message_text)
        whatsapp_url = f"https://wa.me/{wa_phone}?text={encoded_text}"

        # Persist draft to MessageLog
        log_entry = MessageLog(
            assignment_id=assignment.id,
            created_by=actor_user.id,
            message_type=message_type,
            message_text=message_text,
            status=MessageLog.STATUS_DRAFTED,
        )
        db.session.add(log_entry)
        db.session.commit()

        return {
            "message_log_id": log_entry.id,
            "assignment_id": assignment.id,
            "member_id": member.id,
            "member_name": member.full_name,
            "phone_number": phone_info["e164"],
            "wa_phone": wa_phone,
            "message_text": message_text,
            "whatsapp_url": whatsapp_url,
            "status": log_entry.status,
            "disclaimer": "Opening the link opens WhatsApp; message delivery is user-controlled and does not automatically confirm assignment acceptance."
        }

    @staticmethod
    def record_message_action(assignment_id: int, message_log_id: int, action: str, actor_user: User) -> MessageLog:
        """
        Record that administrator opened the link or manually confirmed sending.
        Allowed actions: 'link_opened', 'marked_sent', 'actioned', 'failed'.
        Never automatically mark assignment as accepted!
        """
        valid_actions = {
            MessageLog.STATUS_LINK_OPENED,
            MessageLog.STATUS_MARKED_SENT,
            MessageLog.STATUS_ACTIONED,
            MessageLog.STATUS_FAILED,
        }
        if action not in valid_actions:
            raise ValidationError(
                f"Invalid message action '{action}'. Allowed actions: {list(valid_actions)}.",
                details={"action": action}
            )

        log_entry = MessageLog.query.filter_by(id=message_log_id, assignment_id=assignment_id).first()
        if not log_entry:
            raise NotFoundError(f"Message log entry #{message_log_id} not found for assignment #{assignment_id}.")

        log_entry.record_action(action)
        AuditService.log_action(
            action=f"WHATSAPP_MESSAGE_{action.upper()}",
            entity_type="MessageLog",
            entity_id=log_entry.id,
            actor_user_id=actor_user.id,
            details={"assignment_id": assignment_id, "action": action}
        )
        db.session.commit()
        return log_entry
