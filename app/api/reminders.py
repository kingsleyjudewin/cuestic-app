from flask import Blueprint, request, g
from datetime import timezone
from app.models.reminder import Reminder
from app.models.task_assignment import TaskAssignment
from app.schemas.reminder import ReminderCreateSchema
from app.services.reminder_service import ReminderService
from app.services.task_service import TaskService
from app.utils.datetime_utils import utc_now
from app.utils.permissions import leader_or_admin_required, check_can_manage_assignment
from app.utils.errors import success_response, ValidationError, NotFoundError

reminders_bp = Blueprint("reminders", __name__)


@reminders_bp.route("/reminders", methods=["GET"])
@leader_or_admin_required
def list_reminders():
    """
    List reminders with optional status and assignment filtering.
    ---
    tags:
      - Reminders
    security:
      - BearerAuth: []
    parameters:
      - in: query
        name: status
        schema:
          type: string
        description: Filter by status (scheduled, due, actioned, cancelled, skipped)
      - in: query
        name: assignment_id
        schema:
          type: integer
    responses:
      200:
        description: List of reminders
    """
    status = request.args.get("status")
    assignment_id = request.args.get("assignment_id", type=int)

    query = Reminder.query
    if status:
        query = query.filter_by(status=status.strip().lower())
    if assignment_id:
        query = query.filter_by(assignment_id=assignment_id)

    reminders = query.order_by(Reminder.scheduled_at.asc()).all()
    return success_response(data=[r.to_dict() for r in reminders])


@reminders_bp.route("/reminders/due", methods=["GET"])
@leader_or_admin_required
def list_due_reminders():
    """
    List all reminders that are currently due or pending action.
    ---
    tags:
      - Reminders
    security:
      - BearerAuth: []
    responses:
      200:
        description: Due reminders
    """
    due_reminders = ReminderService.get_due_reminders()
    return success_response(data=[r.to_dict() for r in due_reminders])


@reminders_bp.route("/reminders/process", methods=["POST"])
@leader_or_admin_required
def process_reminders():
    """
    Trigger reminder scan to find unconfirmed, approaching deadline, and overdue assignments.
    ---
    tags:
      - Reminders
    security:
      - BearerAuth: []
    responses:
      200:
        description: Scan statistics
    """
    stats = ReminderService.scan_and_generate_reminders()
    return success_response(data=stats, message="Reminder scan completed.")


@reminders_bp.route("/reminders/<int:reminder_id>/actioned", methods=["POST"])
@leader_or_admin_required
def mark_reminder_actioned(reminder_id: int):
    """
    Mark a reminder as actioned by the administrator.
    ---
    tags:
      - Reminders
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: reminder_id
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Reminder marked actioned
      404:
        description: Reminder not found
    """
    reminder = ReminderService.get_reminder_by_id(reminder_id)
    actioned = ReminderService.action_reminder(reminder, actor_user_id=g.current_user.id)
    return success_response(data=actioned.to_dict(), message="Reminder marked as actioned.")


@reminders_bp.route("/assignments/<int:assignment_id>/reminders", methods=["POST"])
@leader_or_admin_required
def create_assignment_reminder(assignment_id: int):
    """
    Schedule a manual reminder for an assignment.
    ---
    tags:
      - Reminders
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: assignment_id
        required: true
        schema:
          type: integer
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - reminder_type
            properties:
              reminder_type:
                type: string
                enum: [confirmation_reminder, deadline_reminder, overdue_reminder, custom]
                example: custom
              scheduled_at:
                type: string
                format: date-time
    responses:
      201:
        description: Reminder created
      400:
        description: Validation error
    """
    data = request.get_json(silent=True) or {}
    errors = ReminderCreateSchema().validate(data)
    if errors:
        raise ValidationError("Validation error on reminder creation.", details=errors)

    assignment = TaskService.get_assignment_by_id(assignment_id)
    check_can_manage_assignment(g.current_user, assignment)

    scheduled_at = data.get("scheduled_at") or utc_now()
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)

    dedup_key = f"manual:{assignment.id}:{data['reminder_type']}:{scheduled_at.strftime('%Y%m%d%H%M%S')}"

    created = ReminderService._create_reminder_if_absent(
        assignment_id=assignment.id,
        reminder_type=data["reminder_type"],
        scheduled_at=scheduled_at,
        deduplication_key=dedup_key
    )

    if not created:
        raise ValidationError("A duplicate reminder with the exact key already exists.")

    reminder = Reminder.query.filter_by(deduplication_key=dedup_key).first()
    return success_response(data=reminder.to_dict(), message="Reminder scheduled successfully.", status_code=201)
