from datetime import timedelta
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.utils.datetime_utils import utc_now
from app.extensions import db


def test_public_unauthenticated_request_rejected(client):
    """Test that protected endpoints reject requests without token."""
    res1 = client.get("/api/v1/teams")
    assert res1.status_code == 401
    res2 = client.get("/api/v1/members")
    assert res2.status_code == 401
    res3 = client.get("/api/v1/events")
    assert res3.status_code == 401
    res4 = client.get("/api/v1/dashboard/summary")
    assert res4.status_code == 401


def test_member_cannot_create_teams_or_events(client, member_user):
    """Test ordinary members cannot create teams or events."""
    res1 = client.post("/api/v1/teams", headers=member_user["headers"], json={"name": "Hacking Team"})
    assert res1.status_code == 403

    res2 = client.post("/api/v1/events", headers=member_user["headers"], json={
        "name": "Member Event",
        "start_at": (utc_now() + timedelta(days=2)).isoformat(),
    })
    assert res2.status_code == 403


def test_team_leader_cannot_assign_other_team_members(client, team_leader_user, sample_event, seed_members):
    """
    Test team leader cannot assign tasks to members outside their own led teams.
    team_leader_user leads Volunteering. m3 belongs to Documentation.
    """
    event_id = sample_event.id
    m3_id = seed_members["m3"].id  # Documentation team

    response = client.post(f"/api/v1/events/{event_id}/tasks", headers=team_leader_user["headers"], json={
        "title": "Unauthorized Task Assignment",
        "deadline": (utc_now() + timedelta(days=2)).isoformat(),
        "member_ids": [m3_id],
    })
    assert response.status_code == 403
    assert "own teams" in response.get_json()["error"]["message"].lower()


def test_team_leader_can_assign_own_team_members(client, team_leader_user, sample_event, seed_members):
    """
    Test team leader CAN assign tasks to members in their led team (Volunteering).
    m1 and m2 belong to Volunteering.
    """
    event_id = sample_event.id
    m1_id = seed_members["m1"].id

    response = client.post(f"/api/v1/events/{event_id}/tasks", headers=team_leader_user["headers"], json={
        "title": "Authorized Volunteering Task",
        "deadline": (utc_now() + timedelta(days=2)).isoformat(),
        "member_ids": [m1_id],
    })
    assert response.status_code == 201
    assert response.get_json()["data"]["title"] == "Authorized Volunteering Task"


def test_reports_access_control(client, member_user, admin_user, sample_event):
    """Test that reports endpoint is restricted to leaders/admins and forbidden for ordinary members."""
    # Member forbidden
    res1 = client.get("/api/v1/reports/assignments", headers=member_user["headers"])
    assert res1.status_code == 403

    # Admin allowed
    res2 = client.get("/api/v1/reports/assignments", headers=admin_user["headers"])
    assert res2.status_code == 200
    assert "metrics" in res2.get_json()["data"]
