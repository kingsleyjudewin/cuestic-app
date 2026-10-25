from flask import Blueprint, request, g
from datetime import datetime, timezone
from app.models.task_assignment import TaskAssignment
from app.models.task import Task
from app.models.member import Member
from app.models.team import Team
from app.utils.datetime_utils import utc_now
from app.utils.permissions import leader_or_admin_required
from app.utils.errors import success_response, ValidationError

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/reports/assignments", methods=["GET"])
@leader_or_admin_required
def get_assignment_report():
    """
    Generate assignments report with filters (event, team, status, date range) and metrics.
    ---
    tags:
      - Reports
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
        name: status
        schema:
          type: string
      - in: query
        name: start_date
        schema:
          type: string
          format: date
      - in: query
        name: end_date
        schema:
          type: string
          format: date
    responses:
      200:
        description: Assignment report and metrics
    """
    event_id = request.args.get("event_id", type=int)
    team_id = request.args.get("team_id", type=int)
    status = request.args.get("status")
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    query = TaskAssignment.query.join(Task).join(Member)

    user = g.current_user
    if user.is_team_leader() and not user.is_admin():
        led_team_ids = [t.id for t in user.led_teams.all()]
        query = query.filter(Member.team_id.in_(led_team_ids))

    if event_id:
        query = query.filter(Task.event_id == event_id)
    if team_id:
        query = query.filter(Member.team_id == team_id)
    if status:
        query = query.filter(TaskAssignment.status == status.strip().lower())

    if start_date_str:
        try:
            start_date = datetime.fromisoformat(start_date_str).replace(tzinfo=timezone.utc)
            query = query.filter(TaskAssignment.assigned_at >= start_date)
        except ValueError:
            raise ValidationError("Invalid start_date format. Expected ISO-8601 (YYYY-MM-DD).")

    if end_date_str:
        try:
            end_date = datetime.fromisoformat(end_date_str).replace(tzinfo=timezone.utc)
            query = query.filter(TaskAssignment.assigned_at <= end_date)
        except ValueError:
            raise ValidationError("Invalid end_date format. Expected ISO-8601 (YYYY-MM-DD).")

    assignments = query.order_by(Task.deadline.asc()).all()

    # Calculate metrics
    total = len(assignments)
    by_status = {}
    by_team = {}
    overdue_count = 0
    completed_count = 0

    now = utc_now()
    for a in assignments:
        st = a.status
        by_status[st] = by_status.get(st, 0) + 1
        if st == TaskAssignment.STATUS_COMPLETED:
            completed_count += 1

        tname = a.member.team.name if (a.member and a.member.team) else "Unassigned"
        by_team[tname] = by_team.get(tname, 0) + 1

        if a.is_overdue():
            overdue_count += 1

    completion_rate = round((completed_count / total * 100), 2) if total > 0 else 0.0

    report_data = {
        "metrics": {
            "total_assignments": total,
            "completed_assignments": completed_count,
            "completion_rate_percentage": completion_rate,
            "overdue_assignments": overdue_count,
            "breakdown_by_status": by_status,
            "breakdown_by_team": by_team,
        },
        "assignments": [a.to_dict(include_sensitive=user.is_admin()) for a in assignments],
    }

    return success_response(data=report_data)
