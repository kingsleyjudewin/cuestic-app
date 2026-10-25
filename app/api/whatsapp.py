from flask import Blueprint, request, g
from app.models.task_assignment import TaskAssignment
from app.models.message_log import MessageLog
from app.services.task_service import TaskService
from app.services.whatsapp_service import WhatsAppService
from app.utils.permissions import leader_or_admin_required, check_can_manage_assignment
from app.utils.errors import success_response, ValidationError, NotFoundError

whatsapp_bp = Blueprint("whatsapp", __name__)


@whatsapp_bp.route("/assignments/<int:assignment_id>/message-draft", methods=["POST"])
@leader_or_admin_required
def get_message_draft(assignment_id: int):
    """
    Generate a personalized WhatsApp message draft without link URL.
    ---
    tags:
      - WhatsApp
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: assignment_id
        required: true
        schema:
          type: integer
    requestBody:
      required: false
      content:
        application/json:
          schema:
            type: object
            properties:
              message_type:
                type: string
                enum: [initial_assignment, confirmation_reminder, deadline_reminder, overdue_reminder, custom]
                default: initial_assignment
    responses:
      200:
        description: Personalized message draft
      400:
        description: Member inactive or opted out
      404:
        description: Assignment not found
    """
    data = request.get_json(silent=True) or {}
    message_type = data.get("message_type", MessageLog.TYPE_INITIAL_ASSIGNMENT)

    assignment = TaskService.get_assignment_by_id(assignment_id)
    check_can_manage_assignment(g.current_user, assignment)

    draft_info = WhatsAppService.prepare_message_draft(
        assignment=assignment,
        actor_user=g.current_user,
        message_type=message_type
    )

    return success_response(data=draft_info)


@whatsapp_bp.route("/assignments/<int:assignment_id>/whatsapp-link", methods=["POST"])
@leader_or_admin_required
def get_whatsapp_link(assignment_id: int):
    """
    Generate click-to-chat URL with prefilled URL-encoded message text for wa.me.
    ---
    tags:
      - WhatsApp
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: assignment_id
        required: true
        schema:
          type: integer
    requestBody:
      required: false
      content:
        application/json:
          schema:
            type: object
            properties:
              message_type:
                type: string
                enum: [initial_assignment, confirmation_reminder, deadline_reminder, overdue_reminder, custom]
                default: initial_assignment
    responses:
      200:
        description: WhatsApp link generated
      400:
        description: Member inactive or opted out
      404:
        description: Assignment not found
    """
    data = request.get_json(silent=True) or {}
    message_type = data.get("message_type", MessageLog.TYPE_INITIAL_ASSIGNMENT)

    assignment = TaskService.get_assignment_by_id(assignment_id)
    check_can_manage_assignment(g.current_user, assignment)

    draft_info = WhatsAppService.prepare_message_draft(
        assignment=assignment,
        actor_user=g.current_user,
        message_type=message_type
    )

    return success_response(data={
        "assignment_id": assignment.id,
        "message_log_id": draft_info["message_log_id"],
        "whatsapp_url": draft_info["whatsapp_url"],
        "phone_number": draft_info["phone_number"],
        "wa_phone": draft_info["wa_phone"],
        "message_text": draft_info["message_text"],
        "disclaimer": draft_info["disclaimer"],
    })


@whatsapp_bp.route("/assignments/<int:assignment_id>/message-action", methods=["POST"])
@leader_or_admin_required
def record_message_action(assignment_id: int):
    """
    Record administrator action (link_opened, marked_sent, actioned, failed).
    Opening or sending DOES NOT automatically mark assignment as accepted.
    ---
    tags:
      - WhatsApp
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
              - message_log_id
              - action
            properties:
              message_log_id:
                type: integer
                example: 1
              action:
                type: string
                enum: [link_opened, marked_sent, actioned, failed]
                example: marked_sent
    responses:
      200:
        description: Message action recorded
      400:
        description: Invalid action
      404:
        description: Assignment or log not found
    """
    data = request.get_json(silent=True) or {}
    message_log_id = data.get("message_log_id")
    action = data.get("action")

    if not message_log_id or not action:
        raise ValidationError("Both 'message_log_id' and 'action' are required.")

    assignment = TaskService.get_assignment_by_id(assignment_id)
    check_can_manage_assignment(g.current_user, assignment)

    log_entry = WhatsAppService.record_message_action(
        assignment_id=assignment.id,
        message_log_id=message_log_id,
        action=action,
        actor_user=g.current_user
    )

    return success_response(
        data=log_entry.to_dict(),
        message=f"Message action '{action}' recorded successfully."
    )


@whatsapp_bp.route("/assignments/<int:assignment_id>/message-history", methods=["GET"])
@leader_or_admin_required
def get_message_history(assignment_id: int):
    """
    Get audit history of message drafts and actions for an assignment.
    ---
    tags:
      - WhatsApp
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: assignment_id
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Message history
      404:
        description: Assignment not found
    """
    assignment = TaskService.get_assignment_by_id(assignment_id)
    check_can_manage_assignment(g.current_user, assignment)

    logs = assignment.message_logs.order_by(MessageLog.created_at.desc()).all()
    return success_response(data=[log.to_dict() for log in logs])
