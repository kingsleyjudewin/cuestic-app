import time
from flask import Blueprint, request, g
from datetime import timezone
from app.extensions import db
from app.models.event import Event
from app.models.team import Team
from app.models.member import Member
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.schemas.event import EventCreateSchema, EventUpdateSchema
from app.utils.datetime_utils import utc_now
from app.utils.permissions import token_required, leader_or_admin_required, admin_required
from app.utils.errors import success_response, ValidationError, NotFoundError, ConflictError, validate_payload
from app.services.audit_service import AuditService

events_bp = Blueprint("events", __name__)

_EVENTS_CACHE = None
_EVENTS_CACHE_AT = 0.0
_EVENTS_CACHE_TTL = 1800.0


def invalidate_events_cache():
    global _EVENTS_CACHE, _EVENTS_CACHE_AT
    _EVENTS_CACHE = None
    _EVENTS_CACHE_AT = 0.0


def _load_events_into_cache() -> list[dict]:
    global _EVENTS_CACHE, _EVENTS_CACHE_AT
    now = time.time()
    if _EVENTS_CACHE is not None and (now - _EVENTS_CACHE_AT < _EVENTS_CACHE_TTL):
        return _EVENTS_CACHE

    from sqlalchemy.orm import joinedload
    from sqlalchemy import func

    events = Event.query.options(joinedload(Event.creator)).order_by(Event.start_at.asc()).all()
    task_counts = dict(
        db.session.query(Task.event_id, func.count(Task.id))
        .group_by(Task.event_id)
        .all()
    )

    data = [e.to_dict(task_count=task_counts.get(e.id, 0)) for e in events]
    _EVENTS_CACHE = data
    _EVENTS_CACHE_AT = now
    return _EVENTS_CACHE


@events_bp.route("", methods=["GET"])
@token_required
def list_events():
    """
    List events with optional status filtering.
    ---
    tags:
      - Events
    security:
      - BearerAuth: []
    parameters:
      - in: query
        name: status
        schema:
          type: string
        description: Filter by status (draft, upcoming, active, completed, cancelled)
    responses:
      200:
        description: List of events
    """
    status = request.args.get("status")
    events = _load_events_into_cache()
    if status:
        st = status.strip().lower()
        events = [e for e in events if e.get("status") == st]
    return success_response(data=events)


@events_bp.route("/<int:event_id>", methods=["GET"])
@token_required
def get_event(event_id: int):
    """
    Get detailed information about an event.
    ---
    tags:
      - Events
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
        description: Event details
      404:
        description: Event not found
    """
    event = db.session.get(Event, event_id)
    if not event:
        raise NotFoundError(f"Event with ID {event_id} not found.")
    return success_response(data=event.to_dict())


@events_bp.route("", methods=["POST"])
@leader_or_admin_required
def create_event():
    """
    Create a new departmental event.
    ---
    tags:
      - Events
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - name
              - start_at
            properties:
              name:
                type: string
                example: MAGNOVITE 2026
              description:
                type: string
                example: Annual university tech and cultural symposium
              start_at:
                type: string
                format: date-time
                example: "2026-10-28T09:00:00Z"
              end_at:
                type: string
                format: date-time
                example: "2026-10-30T18:00:00Z"
              location:
                type: string
                example: Main Campus Auditorium
              status:
                type: string
                example: upcoming
    responses:
      201:
        description: Event created
      400:
        description: Validation error
    """
    data = validate_payload(EventCreateSchema, request.get_json(silent=True) or {})

    start_at = data["start_at"]
    if start_at.tzinfo is None:
        start_at = start_at.replace(tzinfo=timezone.utc)

    end_at = data.get("end_at")
    if end_at:
        if end_at.tzinfo is None:
            end_at = end_at.replace(tzinfo=timezone.utc)
        if end_at < start_at:
            raise ValidationError("Event end_at cannot be earlier than start_at.")

    event_name = data["name"].strip()
    existing_event = Event.query.filter(
        db.func.lower(Event.name) == event_name.lower(),
        Event.status.in_([Event.STATUS_DRAFT, Event.STATUS_UPCOMING, Event.STATUS_ACTIVE])
    ).first()
    if existing_event:
        raise ConflictError(f"An event named '{event_name}' already exists.")

    event = Event(
        name=event_name,
        description=data.get("description", "").strip() if data.get("description") else None,
        start_at=start_at,
        end_at=end_at,
        location=data.get("location", "").strip() if data.get("location") else None,
        status=data.get("status", Event.STATUS_UPCOMING),
        created_by=g.current_user.id,
    )
    db.session.add(event)
    db.session.flush()

    AuditService.log_action(
        action="EVENT_CREATED",
        entity_type="Event",
        entity_id=event.id,
        actor_user_id=g.current_user.id,
        details={"name": event.name, "start_at": start_at.isoformat()}
    )
    db.session.commit()
    invalidate_events_cache()

    return success_response(data=event.to_dict(), message="Event created successfully.", status_code=201)


@events_bp.route("/<int:event_id>", methods=["PATCH"])
@leader_or_admin_required
def update_event(event_id: int):
    """
    Update event information and handle status transitions safely.
    ---
    tags:
      - Events
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
        description: Event updated successfully
      400:
        description: Invalid transition or dates
      404:
        description: Event not found
    """
    event = db.session.get(Event, event_id)
    if not event:
        raise NotFoundError(f"Event with ID {event_id} not found.")

    data = validate_payload(EventUpdateSchema, request.get_json(silent=True) or {})

    if "status" in data and data["status"] != event.status:
        event.transition_to(data["status"])

    if "name" in data:
        event.name = data["name"].strip()
    if "description" in data:
        event.description = data["description"].strip() if data["description"] else None
    if "location" in data:
        event.location = data["location"].strip() if data["location"] else None

    if "start_at" in data:
        s = data["start_at"]
        if s.tzinfo is None:
            s = s.replace(tzinfo=timezone.utc)
        event.start_at = s

    if "end_at" in data:
        e = data["end_at"]
        if e:
            if e.tzinfo is None:
                e = e.replace(tzinfo=timezone.utc)
            if e < event.start_at:
                raise ValidationError("Event end_at cannot be earlier than start_at.")
            event.end_at = e
        else:
            event.end_at = None

    AuditService.log_action(
        action="EVENT_UPDATED",
        entity_type="Event",
        entity_id=event.id,
        actor_user_id=g.current_user.id,
        details={"changes": list(data.keys())}
    )
    db.session.commit()
    invalidate_events_cache()

    return success_response(data=event.to_dict(), message="Event updated successfully.")


@events_bp.route("/<int:event_id>/archive", methods=["POST"])
@leader_or_admin_required
def archive_event(event_id: int):
    """
    Archive/complete an event.
    ---
    tags:
      - Events
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
        description: Event archived
      404:
        description: Event not found
    """
    event = db.session.get(Event, event_id)
    if not event:
        raise NotFoundError(f"Event with ID {event_id} not found.")

    event.transition_to(Event.STATUS_COMPLETED)
    AuditService.log_action(
        action="EVENT_ARCHIVED",
        entity_type="Event",
        entity_id=event.id,
        actor_user_id=g.current_user.id,
    )
    db.session.commit()
    invalidate_events_cache()

    return success_response(data=event.to_dict(), message="Event successfully marked as completed/archived.")


@events_bp.route("/<int:event_id>/teams", methods=["GET"])
@token_required
def get_event_teams(event_id: int):
    """
    Get available teams and member counts for the selected event.
    Team membership is independent of the event.
    ---
    tags:
      - Events
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
        description: List of club teams available for task assignment in this event
      404:
        description: Event not found
    """
    event = db.session.get(Event, event_id)
    if not event:
        raise NotFoundError(f"Event with ID {event_id} not found.")

    teams = Team.query.filter_by(is_active=True).order_by(Team.name.asc()).all()
    teams_data = []
    for t in teams:
        td = t.to_dict(include_counts=True)
        # Also include count of tasks assigned in this event for this team
        assigned_in_event = TaskAssignment.query.join(Task).join(Member).filter(
            Task.event_id == event.id,
            Member.team_id == t.id,
            Task.is_cancelled == False
        ).count()
        td["event_task_assignments_count"] = assigned_in_event
        teams_data.append(td)

    return success_response(data={
        "event_id": event.id,
        "event_name": event.name,
        "event_status": event.status,
        "teams": teams_data,
    })
