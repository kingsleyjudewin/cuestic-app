from datetime import timedelta
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.reminder import Reminder
from app.utils.datetime_utils import utc_now
from app.extensions import db


def create_assignment_helper(event, member, admin_user, deadline_days=3):
    task = Task(
        event_id=event.id,
        title="Test Assignment Workflow Task",
        deadline=utc_now() + timedelta(days=deadline_days),
        created_by=admin_user["user"].id,
    )
    db.session.add(task)
    db.session.flush()

    assignment = TaskAssignment(
        task_id=task.id,
        member_id=member.id,
        assigned_by=admin_user["user"].id,
        status=TaskAssignment.STATUS_AWAITING_CONFIRMATION,
    )
    db.session.add(assignment)
    db.session.commit()
    return assignment


def test_member_accepts_own_assignment(client, member_user, seed_members, sample_event, admin_user):
    """Test member accepting their own task assignment."""
    # m1 is linked to member_user
    assignment = create_assignment_helper(sample_event, seed_members["m1"], admin_user)

    response = client.post(
        f"/api/v1/assignments/{assignment.id}/confirm",
        headers=member_user["headers"]
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["status"] == "accepted"
    assert data["confirmed_at"] is not None


def test_member_submits_work(client, member_user, seed_members, sample_event, admin_user):
    """Test member transitioning from accepted -> in_progress -> submitted."""
    assignment = create_assignment_helper(sample_event, seed_members["m1"], admin_user)
    # First confirm
    client.post(f"/api/v1/assignments/{assignment.id}/confirm", headers=member_user["headers"])
    # Start progress
    client.patch(
        f"/api/v1/assignments/{assignment.id}/status",
        headers=member_user["headers"],
        json={"status": "in_progress"}
    )
    # Submit work
    response = client.post(
        f"/api/v1/assignments/{assignment.id}/submit",
        headers=member_user["headers"],
        json={"note": "Poster files uploaded to Drive folder"}
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == "submitted"


def test_member_cannot_mark_completed(client, member_user, seed_members, sample_event, admin_user):
    """Test that a member CANNOT mark their own or others' assignments as completed."""
    assignment = create_assignment_helper(sample_event, seed_members["m1"], admin_user)

    # Attempt to complete as member
    response = client.post(
        f"/api/v1/assignments/{assignment.id}/complete",
        headers=member_user["headers"],
        json={"completion_note": "I finished it myself"}
    )
    assert response.status_code == 403
    assert "authorized team leader" in response.get_json()["error"]["message"].lower()


def test_authorized_leader_approves_submission(client, team_leader_user, seed_members, sample_event, admin_user):
    """Test authorized team leader can approve and mark completed."""
    # m1 belongs to Volunteering team, which team_leader_user leads
    assignment = create_assignment_helper(sample_event, seed_members["m1"], admin_user)
    assignment.status = TaskAssignment.STATUS_SUBMITTED
    db.session.commit()

    response = client.post(
        f"/api/v1/assignments/{assignment.id}/complete",
        headers=team_leader_user["headers"],
        json={"completion_note": "Excellent design quality, approved!"}
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["status"] == "completed"
    assert data["completion_note"] == "Excellent design quality, approved!"
    assert data["completed_at"] is not None


def test_unauthorized_member_cannot_modify_other_assignment(client, member_user, seed_members, sample_event, admin_user):
    """Test that an ordinary member cannot update an assignment belonging to another member."""
    # m2 has no linked user and is a different member
    assignment = create_assignment_helper(sample_event, seed_members["m2"], admin_user)

    response = client.post(
        f"/api/v1/assignments/{assignment.id}/confirm",
        headers=member_user["headers"]
    )
    assert response.status_code == 403


def test_completed_assignment_cancels_pending_reminders(client, admin_user, seed_members, sample_event):
    """Test that completing an assignment cancels any pending scheduled reminders."""
    assignment = create_assignment_helper(sample_event, seed_members["m1"], admin_user)
    assignment.status = TaskAssignment.STATUS_SUBMITTED

    # Create a scheduled reminder
    reminder = Reminder(
        assignment_id=assignment.id,
        reminder_type=Reminder.TYPE_DEADLINE,
        scheduled_at=utc_now() + timedelta(days=1),
        status=Reminder.STATUS_SCHEDULED,
        deduplication_key=f"deadline:{assignment.id}:test",
    )
    db.session.add(reminder)
    db.session.commit()

    # Complete assignment
    res = client.post(
        f"/api/v1/assignments/{assignment.id}/complete",
        headers=admin_user["headers"],
        json={"completion_note": "Done"}
    )
    assert res.status_code == 200

    # Verify reminder was cancelled
    refreshed_reminder = db.session.get(Reminder, reminder.id)
    assert refreshed_reminder.status == Reminder.STATUS_CANCELLED
