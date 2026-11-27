from flask import Blueprint, g
from datetime import timedelta
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.models.event import Event
from app.models.member import Member
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.utils.datetime_utils import utc_now, format_iso_utc
from app.utils.permissions import token_required
from app.utils.errors import success_response

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/summary", methods=["GET"])
@token_required
def get_summary():
    """
    Get aggregated dashboard summary metrics.
    ---
    tags:
      - Dashboard
    security:
      - BearerAuth: []
    responses:
      200:
        description: Aggregated dashboard summary
      401:
        description: Unauthorized
    """
    user = g.current_user
    now = utc_now()

    # Base queries
    events_query = Event.query.filter(Event.status.in_([Event.STATUS_UPCOMING, Event.STATUS_ACTIVE]))
    members_query = Member.query.filter_by(is_active=True)
    assignments_query = TaskAssignment.query.join(Task).filter(Task.is_cancelled == False)

    # If team leader, filter assignments and members to their led teams
    if user.is_team_leader() and not user.is_admin():
        led_team_ids = [t.id for t in user.led_teams.all()]
        members_query = members_query.filter(Member.team_id.in_(led_team_ids))
        assignments_query = assignments_query.join(Member).filter(Member.team_id.in_(led_team_ids))

    # All counters in ONE round trip (scalar subqueries + conditional aggregation) instead of six.
    active_cond = TaskAssignment.status.in_(TaskAssignment.ACTIVE_STATUSES)
    assignment_counts = assignments_query.with_entities(
        func.count(case((active_cond, 1))).label("active"),
        func.count(case((TaskAssignment.status == TaskAssignment.STATUS_AWAITING_CONFIRMATION, 1))).label("awaiting"),
        func.count(case((TaskAssignment.status == TaskAssignment.STATUS_COMPLETED, 1))).label("completed"),
        func.count(case((and_(active_cond, Task.deadline < now), 1))).label("overdue"),
    ).subquery()
    counts = db.session.execute(
        select(
            events_query.with_entities(func.count(Event.id)).scalar_subquery().label("events"),
            members_query.with_entities(func.count(Member.id)).scalar_subquery().label("members"),
            assignment_counts.c.active,
            assignment_counts.c.awaiting,
            assignment_counts.c.completed,
            assignment_counts.c.overdue,
        )
    ).one()

    active_events_count = int(counts.events or 0)
    active_members_count = int(counts.members or 0)
    active_assignments_count = int(counts.active or 0)
    awaiting_confirmations_count = int(counts.awaiting or 0)
    completed_assignments_count = int(counts.completed or 0)
    overdue_assignments_count = int(counts.overdue or 0)

    # Upcoming deadlines within next 48 hours (event eager-loaded: no per-task query)
    upcoming_window = now + timedelta(hours=48)
    upcoming_tasks = Task.query.options(joinedload(Task.event)).filter(
        Task.is_cancelled == False,
        Task.deadline >= now,
        Task.deadline <= upcoming_window
    ).order_by(Task.deadline.asc()).limit(10).all()

    upcoming_deadlines = [
        {
            "task_id": t.id,
            "title": t.title,
            "event_name": t.event.name if t.event else None,
            "priority": t.priority,
            "deadline": format_iso_utc(t.deadline),
        }
        for t in upcoming_tasks
    ]

    summary_data = {
        "active_events": active_events_count,
        "total_active_members": active_members_count,
        "active_task_assignments": active_assignments_count,
        "awaiting_confirmations": awaiting_confirmations_count,
        "completed_assignments": completed_assignments_count,
        "overdue_assignments": overdue_assignments_count,
        "upcoming_deadlines": upcoming_deadlines,
    }

    return success_response(data=summary_data)
