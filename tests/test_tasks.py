from datetime import timedelta
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.utils.datetime_utils import utc_now
from app.extensions import db


def test_create_task_with_multiple_assignments(client, admin_user, sample_event, seed_members):
    """Test creating a task and assigning to multiple members transactionally."""
    event_id = sample_event.id
    m1_id = seed_members["m1"].id
    m2_id = seed_members["m2"].id
    deadline = utc_now() + timedelta(days=3)

    response = client.post(f"/api/v1/events/{event_id}/tasks", headers=admin_user["headers"], json={
        "title": "Design Event Posters & Banners",
        "description": "Prepare Canva/Photoshop graphics",
        "priority": "high",
        "deadline": deadline.isoformat(),
        "member_ids": [m1_id, m2_id],
    })
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["title"] == "Design Event Posters & Banners"
    assert data["assignee_count"] == 2
    assert len(data["assignments"]) == 2

    assignee_ids = [a["member_id"] for a in data["assignments"]]
    assert m1_id in assignee_ids
    assert m2_id in assignee_ids
    for a in data["assignments"]:
        assert a["status"] == "awaiting_confirmation"


def test_reject_past_deadline(client, admin_user, sample_event, seed_members):
    """Test rejection when deadline is in the past."""
    event_id = sample_event.id
    past_deadline = utc_now() - timedelta(days=1)

    response = client.post(f"/api/v1/events/{event_id}/tasks", headers=admin_user["headers"], json={
        "title": "Past Task",
        "deadline": past_deadline.isoformat(),
        "member_ids": [seed_members["m1"].id],
    })
    assert response.status_code == 400
    assert "future" in response.get_json()["error"]["message"].lower()


def test_reject_inactive_member_assignment(client, admin_user, sample_event, seed_members):
    """Test rejection when attempting to assign task to inactive member."""
    event_id = sample_event.id
    inactive_id = seed_members["m4"].id  # inactive member

    response = client.post(f"/api/v1/events/{event_id}/tasks", headers=admin_user["headers"], json={
        "title": "Task for Inactive",
        "deadline": (utc_now() + timedelta(days=2)).isoformat(),
        "member_ids": [inactive_id],
    })
    assert response.status_code == 400
    assert "inactive" in response.get_json()["error"]["message"].lower()


def test_reject_nonexistent_member_assignment(client, admin_user, sample_event):
    """Test rejection when member ID does not exist."""
    event_id = sample_event.id

    response = client.post(f"/api/v1/events/{event_id}/tasks", headers=admin_user["headers"], json={
        "title": "Task for Ghost",
        "deadline": (utc_now() + timedelta(days=2)).isoformat(),
        "member_ids": [99999],
    })
    assert response.status_code == 404


def test_transactional_rollback_on_task_creation_failure(client, admin_user, sample_event, seed_members):
    """
    Test that if assignment validation fails (e.g. one valid member and one nonexistent member),
    the entire transaction rolls back and NO task is created.
    """
    initial_task_count = Task.query.count()
    event_id = sample_event.id
    valid_id = seed_members["m1"].id

    response = client.post(f"/api/v1/events/{event_id}/tasks", headers=admin_user["headers"], json={
        "title": "Rolled Back Task",
        "deadline": (utc_now() + timedelta(days=2)).isoformat(),
        "member_ids": [valid_id, 88888],  # 88888 doesn't exist
    })
    assert response.status_code == 404

    # Verify task was NOT created in DB
    final_task_count = Task.query.count()
    assert final_task_count == initial_task_count


def test_add_duplicate_assignment_rejected(client, admin_user, sample_event, seed_members):
    """Test rejection when attempting to assign a member who is already assigned."""
    event_id = sample_event.id
    m1_id = seed_members["m1"].id

    res1 = client.post(f"/api/v1/events/{event_id}/tasks", headers=admin_user["headers"], json={
        "title": "Unique Assignment Task",
        "deadline": (utc_now() + timedelta(days=2)).isoformat(),
        "member_ids": [m1_id],
    })
    assert res1.status_code == 201
    task_id = res1.get_json()["data"]["id"]

    # Now attempt to re-add m1 to the same task
    res2 = client.post(f"/api/v1/tasks/{task_id}/assignments", headers=admin_user["headers"], json={
        "member_ids": [m1_id],
    })
    assert res2.status_code == 409
    assert res2.get_json()["error"]["code"] == "CONFLICT"


def test_cancel_task(client, admin_user, sample_event, seed_members):
    """Test cancelling a task cascades cancellation to active assignments."""
    event_id = sample_event.id
    m1_id = seed_members["m1"].id

    res = client.post(f"/api/v1/events/{event_id}/tasks", headers=admin_user["headers"], json={
        "title": "Task To Cancel",
        "deadline": (utc_now() + timedelta(days=2)).isoformat(),
        "member_ids": [m1_id],
    })
    task_id = res.get_json()["data"]["id"]

    cancel_res = client.post(f"/api/v1/tasks/{task_id}/cancel", headers=admin_user["headers"])
    assert cancel_res.status_code == 200
    task_data = cancel_res.get_json()["data"]
    assert task_data["is_cancelled"] is True
    assert task_data["assignments"][0]["status"] == "cancelled"
