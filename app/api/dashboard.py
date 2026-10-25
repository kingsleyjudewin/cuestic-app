from flask import Blueprint, g
from datetime import timedelta
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

    active_events_count = events_query.count()
    active_members_count = members_query.count()

    active_assignments_count = assignments_query.filter(
        TaskAssignment.status.in_(TaskAssignment.ACTIVE_STATUSES)
    ).count()

    awaiting_confirmations_count = assignments_query.filter(
        TaskAssignment.status == TaskAssignment.STATUS_AWAITING_CONFIRMATION
    ).count()

    completed_assignments_count = assignments_query.filter(
        TaskAssignment.status == TaskAssignment.STATUS_COMPLETED
    ).count()

    overdue_assignments_count = assignments_query.filter(
        TaskAssignment.status.in_(TaskAssignment.ACTIVE_STATUSES),
        Task.deadline < now
    ).count()

    # Upcoming deadlines within next 48 hours
    upcoming_window = now + timedelta(hours=48)
    upcoming_tasks = Task.query.filter(
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
