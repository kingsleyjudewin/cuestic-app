from flask import Blueprint, request, g
from app.extensions import db
from app.models.task_assignment import TaskAssignment
from app.models.task import Task
from app.models.member import Member
from app.schemas.assignment import StatusUpdateSchema, CompleteAssignmentSchema
from app.services.task_service import TaskService
from app.utils.datetime_utils import utc_now
from app.utils.permissions import token_required
from app.utils.errors import success_response, ValidationError, NotFoundError, PermissionDeniedError

assignments_bp = Blueprint("assignments", __name__)


@assignments_bp.route("", methods=["GET"])
@token_required
def list_assignments():
    """
    List and filter task assignments.
    ---
    tags:
      - Assignments
    security:
      - BearerAuth: []
    parameters:
      - in: query
        name: event_id
        schema:
          type: integer
      - in: query
        name: team_id
        schema:
          type: integer
      - in: query
        name: member_id
        schema:
          type: integer
      - in: query
        name: status
        schema:
          type: string
      - in: query
        name: overdue
        schema:
          type: boolean
    responses:
      200:
        description: List of task assignments
    """
    event_id = request.args.get("event_id", type=int)
    team_id = request.args.get("team_id", type=int)
    member_id = request.args.get("member_id", type=int)
    status = request.args.get("status")
    overdue_arg = request.args.get("overdue")

    query = TaskAssignment.query.join(Task).join(Member)

    user = g.current_user
    # If user is regular member, restrict strictly to their own assignments
    if not user.is_admin() and not user.is_team_leader():
        if not user.linked_member:
            return success_response(data=[])
        query = query.filter(TaskAssignment.member_id == user.linked_member.id)
    elif user.is_team_leader() and not user.is_admin():
        led_team_ids = [t.id for t in user.led_teams.all()]
        query = query.filter(Member.team_id.in_(led_team_ids))

    if event_id:
        query = query.filter(Task.event_id == event_id)
    if team_id:
        query = query.filter(Member.team_id == team_id)
    if member_id:
        query = query.filter(TaskAssignment.member_id == member_id)
    if status:
        query = query.filter(TaskAssignment.status == status.strip().lower())
    if overdue_arg is not None:
        is_overdue = overdue_arg.lower() in ("true", "1")
        now = utc_now()
        if is_overdue:
            query = query.filter(
                TaskAssignment.status.in_(TaskAssignment.ACTIVE_STATUSES),
                Task.deadline < now
            )
        else:
            query = query.filter(
                (TaskAssignment.status.in_(TaskAssignment.TERMINAL_STATUSES)) | (Task.deadline >= now)
            )

    assignments = query.order_by(Task.deadline.asc()).all()

    can_view_phones = user.is_admin()
    return success_response(data=[a.to_dict(include_sensitive=can_view_phones) for a in assignments])


@assignments_bp.route("/me", methods=["GET"])
@token_required
def list_my_assignments():
    """
    Personal task assignments endpoint for the authenticated member.
    """
    user = g.current_user
    member = user.linked_member
    if not member:
        raise NotFoundError("Your user account is not associated with any club member record.")

    query = (
        TaskAssignment.query
        .options(
            db.joinedload(TaskAssignment.task).joinedload(Task.event),
            db.joinedload(TaskAssignment.member).joinedload(Member.team),
        )
        .filter(TaskAssignment.member_id == member.id)
        .join(Task)
        .order_by(Task.deadline.asc(), TaskAssignment.id.desc())
    )
    assignments = query.all()
    return success_response(
        data=[a.to_dict(include_sensitive=False) for a in assignments],
        meta={
            "member_id": member.id,
            "member_name": member.full_name,
            "team_id": member.team_id,
            "team_name": member.team.name if member.team else None,
        }
    )


@assignments_bp.route("/<int:assignment_id>", methods=["GET"])
@token_required
def get_assignment(assignment_id: int):
    """
    Get detailed assignment information.
    ---
    tags:
      - Assignments
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
        description: Assignment details
      404:
        description: Assignment not found
    """
    assignment = TaskService.get_assignment_by_id(assignment_id)
    user = g.current_user

    # Permission check
    is_self = assignment.member and assignment.member.linked_user_id == user.id
    is_leader = user.is_team_leader() and assignment.member and assignment.member.team_id in [t.id for t in user.led_teams.all()]
    if not user.is_admin() and not is_leader and not is_self:
        raise PermissionDeniedError("You do not have permission to view this assignment.")

    return success_response(data=assignment.to_dict(include_sensitive=user.is_admin() or is_leader))


@assignments_bp.route("/<int:assignment_id>/status", methods=["PATCH"])
@token_required
def patch_assignment_status(assignment_id: int):
    """
    Update assignment status with transition validation.
    ---
    tags:
      - Assignments
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
              - status
            properties:
              status:
                type: string
                example: in_progress
              note:
                type: string
                example: Started researching vendors
    responses:
      200:
        description: Status updated
      400:
        description: Invalid transition
    """
    data = request.get_json(silent=True) or {}
    errors = StatusUpdateSchema().validate(data)
    if errors:
        raise ValidationError("Validation error on status update.", details=errors)

    assignment = TaskService.get_assignment_by_id(assignment_id)
    updated = TaskService.update_assignment_status(
        assignment=assignment,
        new_status=data["status"],
        actor_user=g.current_user,
        note=data.get("note") or data.get("completion_note")
    )
    return success_response(data=updated.to_dict(include_sensitive=True), message=f"Status updated to '{data['status']}'.")


@assignments_bp.route("/<int:assignment_id>/confirm", methods=["POST"])
@token_required
def confirm_assignment(assignment_id: int):
    """
    Member or leader confirms / accepts the task assignment.
    ---
    tags:
      - Assignments
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
        description: Assignment accepted
    """
    assignment = TaskService.get_assignment_by_id(assignment_id)
    updated = TaskService.update_assignment_status(
        assignment=assignment,
        new_status=TaskAssignment.STATUS_ACCEPTED,
        actor_user=g.current_user
    )
    return success_response(data=updated.to_dict(include_sensitive=True), message="Assignment confirmed/accepted.")


@assignments_bp.route("/<int:assignment_id>/submit", methods=["POST"])
@token_required
def submit_assignment(assignment_id: int):
    """
    Member submits completed work for team leader review.
    ---
    tags:
      - Assignments
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
        description: Assignment submitted
    """
    data = request.get_json(silent=True) or {}
    note = data.get("note") or data.get("completion_note")

    assignment = TaskService.get_assignment_by_id(assignment_id)
    updated = TaskService.update_assignment_status(
        assignment=assignment,
        new_status=TaskAssignment.STATUS_SUBMITTED,
        actor_user=g.current_user,
        note=note
    )
    return success_response(data=updated.to_dict(include_sensitive=True), message="Assignment submitted for review.")


@assignments_bp.route("/<int:assignment_id>/complete", methods=["POST"])
@token_required
def complete_assignment(assignment_id: int):
    """
    Authorized team leader or admin approves and marks assignment completed.
    Members cannot mark their own assignment completed.
    ---
    tags:
      - Assignments
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
        description: Assignment marked completed
      403:
        description: Members cannot approve completion
    """
    data = request.get_json(silent=True) or {}
    errors = CompleteAssignmentSchema().validate(data)
    if errors:
        raise ValidationError("Validation error on completion.", details=errors)

    assignment = TaskService.get_assignment_by_id(assignment_id)
    updated = TaskService.update_assignment_status(
        assignment=assignment,
        new_status=TaskAssignment.STATUS_COMPLETED,
        actor_user=g.current_user,
        note=data.get("completion_note")
    )
    return success_response(data=updated.to_dict(include_sensitive=True), message="Assignment marked as completed.")


@assignments_bp.route("/<int:assignment_id>/decline", methods=["POST"])
@token_required
def decline_assignment(assignment_id: int):
    """
    Member declines task assignment.
    ---
    tags:
      - Assignments
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
        description: Assignment declined
    """
    data = request.get_json(silent=True) or {}
    note = data.get("reason") or data.get("note")

    assignment = TaskService.get_assignment_by_id(assignment_id)
    updated = TaskService.update_assignment_status(
        assignment=assignment,
        new_status=TaskAssignment.STATUS_DECLINED,
        actor_user=g.current_user,
        note=note
    )
    return success_response(data=updated.to_dict(include_sensitive=True), message="Assignment declined.")


@assignments_bp.route("/<int:assignment_id>/block", methods=["POST"])
@token_required
def block_assignment(assignment_id: int):
    """
    Member or leader marks assignment as blocked by an impediment.
    ---
    tags:
      - Assignments
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
        description: Assignment marked as blocked
    """
    data = request.get_json(silent=True) or {}
    note = data.get("reason") or data.get("note")

    assignment = TaskService.get_assignment_by_id(assignment_id)
    updated = TaskService.update_assignment_status(
        assignment=assignment,
        new_status=TaskAssignment.STATUS_BLOCKED,
        actor_user=g.current_user,
        note=note
    )
    return success_response(data=updated.to_dict(include_sensitive=True), message="Assignment marked as blocked.")
