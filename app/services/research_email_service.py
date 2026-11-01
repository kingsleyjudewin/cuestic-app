"""
Research Email and Notification Service.
Handles automated transactional emails and reminder dispatch for Research Management System.
Includes deduplication via ResearchEmailLog, asynchronous background processing,
and delivery tracking.
"""
import os
import smtplib
import threading
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from app import db
from app.models.research import ResearchEmailLog, ResearchNotification

logger = logging.getLogger(__name__)


def _send_smtp_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str = None
) -> tuple[bool, Optional[str]]:
    """
    Direct low-overhead SMTP dispatch using environment configuration.
    Returns (success, error_message).
    """
    mail_server = os.getenv("MAIL_SERVER")
    mail_port = int(os.getenv("MAIL_PORT", "587"))
    mail_username = os.getenv("MAIL_USERNAME")
    mail_password = os.getenv("MAIL_PASSWORD")
    mail_sender = os.getenv("MAIL_DEFAULT_SENDER", mail_username or "research@department.edu")
    use_tls = os.getenv("MAIL_USE_TLS", "true").lower() in ("true", "1", "yes")

    if not mail_server or not mail_username or not mail_password:
        logger.info(f"[ResearchEmailService] SMTP not fully configured. Email to {to_email} skipped.")
        return True, "SMTP configuration not provided; logged as skipped"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = mail_sender
        msg["To"] = to_email

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        if use_tls:
            with smtplib.SMTP(mail_server, mail_port, timeout=10) as server:
                server.starttls()
                server.login(mail_username, mail_password)
                server.sendmail(mail_sender, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(mail_server, mail_port, timeout=10) as server:
                server.login(mail_username, mail_password)
                server.sendmail(mail_sender, [to_email], msg.as_string())

        return True, None
    except Exception as e:
        logger.warning(f"[ResearchEmailService] Failed to send email to {to_email}: {str(e)}")
        return False, str(e)


def dispatch_research_email(
    app,
    recipient_email: str,
    recipient_user_id: Optional[int],
    subject: str,
    html_body: str,
    text_body: str,
    event_type: str,
    deduplication_key: str,
):
    """
    Background worker thread function for sending email with deduplication and logging.
    """
    with app.app_context():
        existing_log = ResearchEmailLog.query.filter_by(deduplication_key=deduplication_key).first()
        if existing_log and existing_log.status in ("sent", "skipped"):
            logger.info(f"[ResearchEmailService] Duplicate email suppressed: {deduplication_key}")
            return

        if not existing_log:
            log_entry = ResearchEmailLog(
                recipient_email=recipient_email,
                recipient_user_id=recipient_user_id,
                subject=subject,
                event_type=event_type,
                status="queued",
                deduplication_key=deduplication_key,
            )
            db.session.add(log_entry)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                return
        else:
            log_entry = existing_log

        success, err = _send_smtp_email(
            to_email=recipient_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

        log_entry.status = "sent" if success and not err else ("skipped" if "skipped" in (err or "") else "failed")
        log_entry.error_message = err
        if success and not err:
            log_entry.sent_at = datetime.now(timezone.utc)
        else:
            log_entry.retry_count += 1

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()


class ResearchEmailService:
    """Service API for triggering research-related emails and in-app notifications."""

    @staticmethod
    def _enqueue(
        app,
        recipient_email: Optional[str],
        recipient_user_id: Optional[int],
        subject: str,
        html_body: str,
        text_body: str,
        event_type: str,
        deduplication_key: str,
        in_app_title: Optional[str] = None,
        in_app_message: Optional[str] = None,
        reference_id: Optional[int] = None,
        reference_type: Optional[str] = None,
    ):
        # 1. In-App Notification
        if recipient_user_id and in_app_title and in_app_message:
            try:
                notif = ResearchNotification(
                    user_id=recipient_user_id,
                    title=in_app_title,
                    body=in_app_message,
                    notification_type=event_type,
                    reference_id=reference_id,
                    reference_type=reference_type,
                )
                db.session.add(notif)
                db.session.flush()
            except Exception as e:
                logger.warning(f"Error creating in-app notification: {e}")

        # 2. Email Dispatch (Suppress background threads in test environment)
        if not recipient_email or "@" not in recipient_email:
            return

        if app and app.config.get("TESTING"):
            logger.info(f"[ResearchEmailService] Testing mode active, skipping background thread for {recipient_email}")
            return

        thread = threading.Thread(
            target=dispatch_research_email,
            args=(
                app,
                recipient_email,
                recipient_user_id,
                subject,
                html_body,
                text_body,
                event_type,
                deduplication_key,
            ),
            daemon=True,
        )
        thread.start()

    @classmethod
    def notify_student_account_created(cls, app, student, temp_password: str):
        key = f"student_account_created:{student.email}:{student.id}"
        subject = "Welcome to Research Management Portal - Your Credentials"
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; color: #111;">
            <h2 style="font-weight: 600; letter-spacing: -0.5px;">Welcome to Research Management</h2>
            <p>Dear {student.full_name},</p>
            <p>Your Student Researcher account has been provisioned.</p>
            <div style="background: #f7f7f7; border: 1px solid #e5e5e5; border-radius: 8px; padding: 16px; margin: 20px 0;">
                <p style="margin: 0 0 8px;"><strong>Registration Number:</strong> {student.registration_number}</p>
                <p style="margin: 0 0 8px;"><strong>Username:</strong> {student.user.username if student.user else student.registration_number}</p>
                <p style="margin: 0;"><strong>Temporary Password:</strong> <code style="background: #eee; padding: 2px 6px; border-radius: 4px;">{temp_password}</code></p>
            </div>
            <p style="color: #666; font-size: 14px;">Please sign in and change your password immediately upon first login.</p>
        </div>
        """
        text = f"Welcome {student.full_name},\nYour research account has been created. Username: {student.user.username if student.user else student.registration_number}, Temp Password: {temp_password}"
        cls._enqueue(
            app=app,
            recipient_email=student.email,
            recipient_user_id=student.user_id,
            subject=subject,
            html_body=html,
            text_body=text,
            event_type="student_account_created",
            deduplication_key=key,
            in_app_title="Welcome to Research Portal",
            in_app_message="Your student researcher account is active. Please complete password setup.",
            reference_id=student.id,
            reference_type="student_profile",
        )

    @classmethod
    def notify_student_added_to_team(cls, app, student, team, faculty):
        key = f"student_added_to_team:{student.id}:{team.id}"
        subject = f"Added to Research Team: {team.name}"
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
            <h3>Added to Research Team</h3>
            <p>Dear {student.full_name},</p>
            <p>You have been added to the research team <strong>{team.name}</strong> ({team.domain}) by <strong>{faculty.full_name}</strong>.</p>
            <p>Visit your Research Portal to view team objectives and projects.</p>
        </div>
        """
        text = f"Dear {student.full_name}, You were added to {team.name} by {faculty.full_name}."
        cls._enqueue(
            app=app,
            recipient_email=student.email,
            recipient_user_id=student.user_id,
            subject=subject,
            html_body=html,
            text_body=text,
            event_type="student_added_to_team",
            deduplication_key=key,
            in_app_title=f"Added to Team: {team.name}",
            in_app_message=f"You are now a member of {team.name} guided by {faculty.full_name}.",
            reference_id=team.id,
            reference_type="team",
        )

    @classmethod
    def notify_student_assigned_to_project(cls, app, student, project, faculty):
        key = f"student_assigned_to_project:{student.id}:{project.id}"
        subject = f"Assigned to Research Project: {project.title}"
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
            <h3>Assigned to Research Project</h3>
            <p>Dear {student.full_name},</p>
            <p>You have been assigned to the project <strong>{project.title}</strong> under team <em>{project.team.name if project.team else ''}</em>.</p>
            <p><strong>Coordinator:</strong> {faculty.full_name}</p>
        </div>
        """
        text = f"Dear {student.full_name}, you have been assigned to project: {project.title}."
        cls._enqueue(
            app=app,
            recipient_email=student.email,
            recipient_user_id=student.user_id,
            subject=subject,
            html_body=html,
            text_body=text,
            event_type="student_assigned_to_project",
            deduplication_key=key,
            in_app_title=f"Assigned to Project: {project.title}",
            in_app_message=f"You have been assigned to research project {project.title}.",
            reference_id=project.id,
            reference_type="project",
        )

    @classmethod
    def notify_task_assigned(cls, app, student, task, project):
        key = f"task_assigned:{student.id}:{task.id}"
        subject = f"New Research Task: {task.title}"
        deadline_str = task.due_date.strftime('%b %d, %Y') if task.due_date else "Flexible"
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
            <h3>New Task Assigned</h3>
            <p>Dear {student.full_name},</p>
            <p>A new research task has been assigned to you in project <strong>{project.title}</strong>:</p>
            <div style="background: #f7f7f7; padding: 12px; border-radius: 6px;">
                <strong>{task.title}</strong><br/>
                <span style="color: #666;">Deadline: {deadline_str}</span><br/>
                <span style="color: #666;">Priority: {task.priority.capitalize()}</span>
            </div>
            <p style="margin-top: 12px;">{task.instructions or ''}</p>
        </div>
        """
        text = f"New Task: {task.title} in {project.title}. Deadline: {deadline_str}"
        cls._enqueue(
            app=app,
            recipient_email=student.email,
            recipient_user_id=student.user_id,
            subject=subject,
            html_body=html,
            text_body=text,
            event_type="task_assigned",
            deduplication_key=key,
            in_app_title=f"New Task: {task.title}",
            in_app_message=f"Assigned task '{task.title}' with deadline {deadline_str}.",
            reference_id=task.id,
            reference_type="task",
        )

    @classmethod
    def notify_deadline_approaching(cls, app, student, task, days_left: int):
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = f"deadline_approaching:{student.id}:{task.id}:{days_left}d:{today_str}"
        subject = f"Reminder: Task '{task.title}' is due in {days_left} day{'s' if days_left != 1 else ''}"
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
            <h3>Deadline Approaching</h3>
            <p>Dear {student.full_name},</p>
            <p>Your research task <strong>{task.title}</strong> is due in <strong>{days_left} day{'s' if days_left != 1 else ''}</strong>.</p>
            <p>Please make sure your progress update and required deliverables are submitted.</p>
        </div>
        """
        text = f"Reminder: Task '{task.title}' due in {days_left} days."
        cls._enqueue(
            app=app,
            recipient_email=student.email,
            recipient_user_id=student.user_id,
            subject=subject,
            html_body=html,
            text_body=text,
            event_type="deadline_approaching",
            deduplication_key=key,
            in_app_title=f"Task Due in {days_left} Day{'s' if days_left != 1 else ''}",
            in_app_message=f"Task '{task.title}' deadline is approaching.",
            reference_id=task.id,
            reference_type="task",
        )

    @classmethod
    def notify_task_overdue(cls, app, student, task):
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = f"task_overdue:{student.id}:{task.id}:{today_str}"
        subject = f"Urgent: Task '{task.title}' is Overdue"
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
            <h3 style="color: #c00;">Task Overdue</h3>
            <p>Dear {student.full_name},</p>
            <p>The deadline for <strong>{task.title}</strong> has passed. Please submit your progress report or contact your faculty coordinator immediately.</p>
        </div>
        """
        text = f"Urgent: Task '{task.title}' is overdue. Please submit progress immediately."
        cls._enqueue(
            app=app,
            recipient_email=student.email,
            recipient_user_id=student.user_id,
            subject=subject,
            html_body=html,
            text_body=text,
            event_type="task_overdue",
            deduplication_key=key,
            in_app_title=f"Task Overdue: {task.title}",
            in_app_message=f"The deadline for task '{task.title}' has passed. Please submit your update.",
            reference_id=task.id,
            reference_type="task",
        )

    @classmethod
    def notify_faculty_feedback_added(cls, app, student, task, faculty, message_text: str):
        timestamp_sec = int(datetime.now(timezone.utc).timestamp())
        key = f"faculty_feedback:{student.id}:{task.id}:{timestamp_sec}"
        subject = f"Faculty Feedback on Task: {task.title}"
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
            <h3>Feedback Received</h3>
            <p>Dear {student.full_name},</p>
            <p><strong>{faculty.full_name}</strong> has provided feedback on your task <strong>{task.title}</strong>:</p>
            <blockquote style="border-left: 3px solid #111; padding-left: 12px; margin: 16px 0; color: #444;">
                {message_text}
            </blockquote>
            <p>Check the feedback thread in your Research Portal to review and reply.</p>
        </div>
        """
        text = f"{faculty.full_name} provided feedback on '{task.title}': {message_text}"
        cls._enqueue(
            app=app,
            recipient_email=student.email,
            recipient_user_id=student.user_id,
            subject=subject,
            html_body=html,
            text_body=text,
            event_type="faculty_feedback_added",
            deduplication_key=key,
            in_app_title=f"Feedback on {task.title}",
            in_app_message=f"{faculty.full_name}: {message_text[:80]}...",
            reference_id=task.id,
            reference_type="task",
        )

    @classmethod
    def notify_revision_requested(cls, app, student, task, faculty, notes: str):
        timestamp_sec = int(datetime.now(timezone.utc).timestamp())
        key = f"revision_requested:{student.id}:{task.id}:{timestamp_sec}"
        subject = f"Revision Requested: {task.title}"
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
            <h3 style="color: #b54708;">Revision Requested</h3>
            <p>Dear {student.full_name},</p>
            <p><strong>{faculty.full_name}</strong> has requested revisions on your submission for <strong>{task.title}</strong>:</p>
            <blockquote style="border-left: 3px solid #b54708; padding-left: 12px; margin: 16px 0; color: #444;">
                {notes}
            </blockquote>
            <p>Please review the comments, update your deliverables, and resubmit.</p>
        </div>
        """
        text = f"Revision requested on '{task.title}' by {faculty.full_name}: {notes}"
        cls._enqueue(
            app=app,
            recipient_email=student.email,
            recipient_user_id=student.user_id,
            subject=subject,
            html_body=html,
            text_body=text,
            event_type="revision_requested",
            deduplication_key=key,
            in_app_title=f"Revision Requested: {task.title}",
            in_app_message=f"{faculty.full_name} requested corrections on {task.title}.",
            reference_id=task.id,
            reference_type="task",
        )

    @classmethod
    def notify_submission_approved(cls, app, student, task, faculty):
        key = f"submission_approved:{student.id}:{task.id}"
        subject = f"Submission Approved: {task.title}"
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
            <h3 style="color: #027a48;">Task Approved</h3>
            <p>Dear {student.full_name},</p>
            <p>Congratulations! Your submission for <strong>{task.title}</strong> has been approved by <strong>{faculty.full_name}</strong>.</p>
        </div>
        """
        text = f"Your submission for '{task.title}' was approved by {faculty.full_name}."
        cls._enqueue(
            app=app,
            recipient_email=student.email,
            recipient_user_id=student.user_id,
            subject=subject,
            html_body=html,
            text_body=text,
            event_type="submission_approved",
            deduplication_key=key,
            in_app_title=f"Task Approved: {task.title}",
            in_app_message=f"Your work on '{task.title}' has been approved.",
            reference_id=task.id,
            reference_type="task",
        )

    @classmethod
    def notify_meeting_scheduled(cls, app, recipient_email, recipient_user_id, recipient_name, meeting, faculty, is_update: bool = False):
        key = f"meeting:{meeting.id}:{recipient_user_id}:{'updated' if is_update else 'scheduled'}"
        action_word = "Updated" if is_update else "Scheduled"
        subject = f"Research Meeting {action_word}: {meeting.title}"
        time_str = meeting.scheduled_at.strftime("%A, %b %d, %Y at %I:%M %p") if meeting.scheduled_at else "TBD"
        location_info = f"Location / Link: {meeting.location_or_link}" if meeting.location_or_link else ""

        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
            <h3>Research Meeting {action_word}</h3>
            <p>Dear {recipient_name},</p>
            <p>A research meeting has been {action_word.lower()} by <strong>{faculty.full_name}</strong>.</p>
            <div style="background: #f7f7f7; padding: 16px; border-radius: 8px; margin: 16px 0;">
                <p style="margin: 0 0 6px;"><strong>Title:</strong> {meeting.title}</p>
                <p style="margin: 0 0 6px;"><strong>Time:</strong> {time_str}</p>
                {f'<p style="margin: 0 0 6px;"><strong>{location_info}</strong></p>' if location_info else ''}
                {f'<p style="margin: 0;"><strong>Agenda:</strong> {meeting.agenda}</p>' if meeting.agenda else ''}
            </div>
        </div>
        """
        text = f"Research Meeting {action_word}: {meeting.title} on {time_str} by {faculty.full_name}."
        cls._enqueue(
            app=app,
            recipient_email=recipient_email,
            recipient_user_id=recipient_user_id,
            subject=subject,
            html_body=html,
            text_body=text,
            event_type="meeting_scheduled_or_updated",
            deduplication_key=key,
            in_app_title=f"Meeting {action_word}: {meeting.title}",
            in_app_message=f"{meeting.title} scheduled for {time_str}.",
            reference_id=meeting.id,
            reference_type="meeting",
        )
