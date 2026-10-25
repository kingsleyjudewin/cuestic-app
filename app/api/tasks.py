from flask import Blueprint, request, g
from datetime import timezone
from app.extensions import db
from app.models.task import Task
from app.models.event import Event
from app.schemas.task import TaskCreateSchema, TaskUpdateSchema, AddAssignmentsSchema
from app.services.task_service import TaskService
from app.utils.datetime_utils import utc_now
from app.utils.permissions import token_required, leader_or_admin_required
from app.utils.errors import success_response, ValidationError, NotFoundError, validate_payload
from app.services.audit_service import AuditService

tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.route("/events/<int:event_id>/tasks", methods=["GET"])
@token_required
def list_event_tasks(event_id: int):
    """
    List all tasks associated with an event.
    ---
    tags:
      - Tasks
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: event_id
        required: true
        schema:
          type: integer
    responses:
      200:
        description: List of tasks
      404:
        description: Event not found
    """
    event = db.session.get(Event, event_id)
    if not event:
        raise NotFoundError(f"Event with ID {event_id} not found.")

    tasks = Task.query.filter_by(event_id=event_id).order_by(Task.deadline.asc()).all()
    return success_response(data=[t.to_dict(include_assignments=True) for t in tasks])


@tasks_bp.route("/events/<int:event_id>/tasks", methods=["POST"])
@leader_or_admin_required
def create_task_for_event(event_id: int):
    """
    Create a new task for an event and assign it to multiple members transactionally.
    ---
    tags:
      - Tasks
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: event_id
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
              - title
              - deadline
              - member_ids
            properties:
              title:
                type: string
                example: Prepare the event announcement poster
              description:
                type: string
                example: Design social media assets and print banners in Canva/Photoshop
              priority:
                type: string
                enum: [low, medium, high, urgent]
                example: high
              deadline:
                type: string
                format: date-time
                example: "2026-10-28T17:00:00Z"
              member_ids:
                type: array
                items:
                  type: integer
                example: [1, 2]
    responses:
      201:
        description: Task and assignments successfully created
      400:
        description: Validation error
      404:
        description: Member or event not found
    """
    data = validate_payload(TaskCreateSchema, request.get_json(silent=True) or {})

    task = TaskService.create_task_with_assignments(
        event_id=event_id,
        data=data,
        member_ids=data["member_ids"],
        actor_user=g.current_user
    )

    return success_response(
        data=task.to_dict(include_assignments=True),
        message="Task and assignments created successfully.",
        status_code=201
    )


@tasks_bp.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def get_task(task_id: int):
    """
    Get detailed task information and assignment statuses.
    ---
    tags:
      - Tasks
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: task_id
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Task details
      404:
        description: Task not found
    """
    task = TaskService.get_task_by_id(task_id)
    return success_response(data=task.to_dict(include_assignments=True))


@tasks_bp.route("/tasks/<int:task_id>", methods=["PATCH"])
@leader_or_admin_required
def update_task(task_id: int):
    """
    Update task details (title, description, priority, deadline).
    ---
    tags:
      - Tasks
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: task_id
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Task successfully updated
      404:
        description: Task not found
    """
    task = TaskService.get_task_by_id(task_id)
    if task.is_cancelled:
        raise ValidationError("Cannot update a cancelled task.")

    data = validate_payload(TaskUpdateSchema, request.get_json(silent=True) or {})

    if "title" in data:
        task.title = data["title"].strip()
    if "description" in data:
        task.description = data["description"].strip() if data["description"] else None
    if "priority" in data:
        task.priority = data["priority"]
    if "deadline" in data:
        dl = data["deadline"]
        if dl.tzinfo is None:
            dl = dl.replace(tzinfo=timezone.utc)
        task.deadline = dl

    AuditService.log_action(
        action="TASK_UPDATED",
        entity_type="Task",
        entity_id=task.id,
        actor_user_id=g.current_user.id,
        details={"changes": list(data.keys())}
    )
    db.session.commit()

    return success_response(data=task.to_dict(include_assignments=True), message="Task updated successfully.")


@tasks_bp.route("/tasks/<int:task_id>/assignments", methods=["POST"])
@leader_or_admin_required
def add_task_assignments(task_id: int):
    """
    Add more members to an existing task.
    ---
    tags:
      - Tasks
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: task_id
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
              - member_ids
            properties:
              member_ids:
                type: array
                items:
                  type: integer
                example: [3, 4]
    responses:
      201:
        description: Assignments created
      400:
        description: Validation error
      409:
        description: Member already assigned
    """
    data = validate_payload(AddAssignmentsSchema, request.get_json(silent=True) or {})

    new_assignments = TaskService.add_assignments_to_task(
        task_id=task_id,
        member_ids=data["member_ids"],
        actor_user=g.current_user
    )

    return success_response(
        data=[a.to_dict() for a in new_assignments],
        message="Assignments added successfully.",
        status_code=201
    )


@tasks_bp.route("/tasks/<int:task_id>/cancel", methods=["POST"])
@leader_or_admin_required
def cancel_task(task_id: int):
    """
    Cancel a task and all associated active assignments and reminders.
    ---
    tags:
      - Tasks
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: task_id
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Task cancelled
      404:
        description: Task not found
    """
    task = TaskService.get_task_by_id(task_id)
    cancelled = TaskService.cancel_task(task, g.current_user)
    return success_response(data=cancelled.to_dict(include_assignments=True), message="Task cancelled successfully.")
