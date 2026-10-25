from datetime import timedelta
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.utils.datetime_utils import utc_now
from app.extensions import db


def test_dashboard_summary_admin_and_leader(client, admin_user, team_leader_user, sample_event, seed_members):
    """Test dashboard summary endpoint for admin and team leader."""
    task = Task(
        event_id=sample_event.id,
        title="Dashboard Test Task",
        deadline=utc_now() + timedelta(hours=20),
        created_by=admin_user["user"].id,
    )
    db.session.add(task)
    db.session.flush()

    assignment = TaskAssignment(
        task_id=task.id,
        member_id=seed_members["m1"].id,
        assigned_by=admin_user["user"].id,
        status=TaskAssignment.STATUS_AWAITING_CONFIRMATION,
    )
    db.session.add(assignment)
    db.session.commit()

    # Admin view
    res1 = client.get("/api/v1/dashboard/summary", headers=admin_user["headers"])
    assert res1.status_code == 200
    data1 = res1.get_json()["data"]
    assert data1["active_events"] >= 1
    assert data1["total_active_members"] >= 3
    assert data1["active_task_assignments"] >= 1
    assert data1["awaiting_confirmations"] >= 1
    assert len(data1["upcoming_deadlines"]) >= 1

    # Team leader view
    res2 = client.get("/api/v1/dashboard/summary", headers=team_leader_user["headers"])
    assert res2.status_code == 200
    data2 = res2.get_json()["data"]
    assert "active_task_assignments" in data2


def test_reports_filtering(client, admin_user, sample_event, seed_members, seed_teams):
    """Test assignments report endpoint with query filters."""
    task = Task(
        event_id=sample_event.id,
        title="Report Task",
        deadline=utc_now() + timedelta(days=2),
        created_by=admin_user["user"].id,
    )
    db.session.add(task)
    db.session.flush()

    a1 = TaskAssignment(
        task_id=task.id,
        member_id=seed_members["m1"].id,
        assigned_by=admin_user["user"].id,
        status=TaskAssignment.STATUS_COMPLETED,
    )
    db.session.add(a1)
    db.session.commit()

    # Filter by event_id and status
    res = client.get(
        f"/api/v1/reports/assignments?event_id={sample_event.id}&status=completed",
        headers=admin_user["headers"]
    )
    assert res.status_code == 200
    data = res.get_json()["data"]
    metrics = data["metrics"]
    assert metrics["total_assignments"] >= 1
    assert metrics["completed_assignments"] >= 1
    assert metrics["completion_rate_percentage"] == 100.0


def test_reminders_api_endpoints(client, admin_user, sample_event, seed_members):
    """Test reminder scan, list, due, and actioned API routes."""
    task = Task(
        event_id=sample_event.id,
        title="Reminder API Task",
        deadline=utc_now() + timedelta(hours=6),
        created_by=admin_user["user"].id,
    )
    db.session.add(task)
    db.session.flush()

    a = TaskAssignment(
        task_id=task.id,
        member_id=seed_members["m1"].id,
        assigned_by=admin_user["user"].id,
        status=TaskAssignment.STATUS_ACCEPTED,
    )
    db.session.add(a)
    db.session.commit()

    # 1. Trigger process
    res1 = client.post("/api/v1/reminders/process", headers=admin_user["headers"])
    assert res1.status_code == 200

    # 2. List reminders
    res2 = client.get("/api/v1/reminders", headers=admin_user["headers"])
    assert res2.status_code == 200
    reminders = res2.get_json()["data"]
    assert len(reminders) >= 1
    rem_id = reminders[0]["id"]

    # 3. Action reminder
    res3 = client.post(f"/api/v1/reminders/{rem_id}/actioned", headers=admin_user["headers"])
    assert res3.status_code == 200
    assert res3.get_json()["data"]["status"] == "actioned"
