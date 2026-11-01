from datetime import timedelta
import pytest
from app.models.user import User
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.utils.datetime_utils import utc_now


def test_full_mobile_app_workflow_integration(client, app, seed_teams):
    """
    Simulates the exact end-to-end API calls made by the Flutter mobile application
    across all screens and actions.
    """
    # 0. Create admin user with known credentials for login
    with app.app_context():
        from app.extensions import db
        from app.models.member import Member
        from app.models.event import Event

        admin = User(
            username="testadmin",
            email="testadmin@club.edu",
            role=User.ROLE_PRESIDENT,
            is_active=True,
        )
        admin.set_password("AdminPass123!")
        db.session.add(admin)

        # Seed Member
        vol_team = seed_teams["volunteering"]
        m1 = Member(
            full_name="Ananya Sharma",
            registration_number="REG-001",
            class_name="3rd Year CSE",
            section="A",
            phone_number="+919876500001",
            team_id=vol_team.id,
            is_active=True,
            whatsapp_opt_in=True,
        )
        m2 = Member(
            full_name="Rohan Verma",
            registration_number="REG-002",
            class_name="3rd Year CSE",
            section="B",
            phone_number="+919876500002",
            team_id=vol_team.id,
            is_active=True,
            whatsapp_opt_in=True,
        )
        db.session.add_all([m1, m2])

        # Seed Event
        event = Event(
            name="MAGNOVITE 2026",
            start_at=utc_now() + timedelta(days=7),
            end_at=utc_now() + timedelta(days=9),
            status="upcoming",
            created_by=1,
        )
        db.session.add(event)
        db.session.commit()

        event_id = event.id
        team_id = vol_team.id
        member1_id = m1.id
        member2_id = m2.id

    # 1. Login Screen — POST /api/v1/auth/login
    login_res = client.post("/api/v1/auth/login", json={
        "username": "testadmin",
        "password": "AdminPass123!",
        "device_name": "Antigravity Pixel 8",
    })
    assert login_res.status_code == 200
    token = login_res.get_json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 2. Register Device Token — POST /api/v1/notifications/device-token
    fcm_res = client.post("/api/v1/notifications/device-token", json={
        "token": "fcm_mock_token_mobile_123",
        "device_type": "android",
        "device_name": "Antigravity Pixel 8",
    }, headers=headers)
    assert fcm_res.status_code == 200

    # 3. Screen 1: Select Event — GET /api/v1/events
    events_res = client.get("/api/v1/events", headers=headers)
    assert events_res.status_code == 200
    events_data = events_res.get_json()["data"]
    assert len(events_data) >= 1
    selected_event = next(e for e in events_data if e["id"] == event_id)
    assert selected_event["name"] == "MAGNOVITE 2026"

    # 4. Screen 2: Select Team — GET /api/v1/events/{event_id}/teams
    teams_res = client.get(f"/api/v1/events/{event_id}/teams", headers=headers)
    assert teams_res.status_code == 200
    teams_list = teams_res.get_json()["data"]["teams"]
    assert any(t["id"] == team_id for t in teams_list)

    # 5. Screen 3: Member Directory — GET /api/v1/teams/{team_id}/members
    members_res = client.get(f"/api/v1/teams/{team_id}/members", headers=headers)
    assert members_res.status_code == 200
    members_list = members_res.get_json()["data"]
    assert len(members_list) >= 2
    # Verify sensitive phone visible because admin is authenticated
    assert any(m["phone_number"] == "+919876500001" for m in members_list)

    # 6. Screen 4: Create Assignment — POST /api/v1/events/{event_id}/tasks
    task_res = client.post(f"/api/v1/events/{event_id}/tasks", json={
        "title": "Setup Main Auditorium Stage & AV Equipment",
        "description": "Coordinate audio mixers, projector, and guest seating",
        "priority": "high",
        "deadline": (utc_now() + timedelta(days=2)).isoformat(),
        "member_ids": [member1_id, member2_id],
    }, headers=headers)
    assert task_res.status_code == 201
    created_task = task_res.get_json()["data"]
    assert created_task["title"] == "Setup Main Auditorium Stage & AV Equipment"
    assignments = created_task["assignments"]
    assert len(assignments) == 2
    assignment1_id = assignments[0]["id"]
    assignment2_id = assignments[1]["id"]

    # 7. Screen 5: Assignment Message — POST /api/v1/assignments/{id}/whatsapp-link
    wa_res = client.post(f"/api/v1/assignments/{assignment1_id}/whatsapp-link", json={
        "message_type": "initial_assignment",
    }, headers=headers)
    assert wa_res.status_code == 200
    wa_data = wa_res.get_json()["data"]
    assert "whatsapp_url" in wa_data
    assert "wa.me" in wa_data["whatsapp_url"]
    message_log_id = wa_data["message_log_id"]

    # Record message actions: link_opened and marked_sent
    open_action_res = client.post(f"/api/v1/assignments/{assignment1_id}/message-action", json={
        "message_log_id": message_log_id,
        "action": "link_opened",
    }, headers=headers)
    assert open_action_res.status_code == 200

    sent_action_res = client.post(f"/api/v1/assignments/{assignment1_id}/message-action", json={
        "message_log_id": message_log_id,
        "action": "marked_sent",
    }, headers=headers)
    assert sent_action_res.status_code == 200

    # 8. Screen 6: Assignment Tracking — GET /api/v1/assignments
    track_res = client.get("/api/v1/assignments", headers=headers)
    assert track_res.status_code == 200
    all_assignments = track_res.get_json()["data"]
    assert any(a["id"] == assignment1_id for a in all_assignments)

    # Filter by status 'awaiting_confirmation'
    pending_res = client.get("/api/v1/assignments?status=awaiting_confirmation", headers=headers)
    assert pending_res.status_code == 200
    assert any(a["id"] == assignment1_id for a in pending_res.get_json()["data"])

    # 9. Assignment Details: Status Transition — PATCH /api/v1/assignments/{id}/status
    patch_res = client.patch(f"/api/v1/assignments/{assignment1_id}/status", json={
        "status": "in_progress",
        "note": "Member accepted and began procurement",
    }, headers=headers)
    assert patch_res.status_code == 200
    assert patch_res.get_json()["data"]["status"] == "in_progress"

    # 10. Logout Screen — POST /api/v1/auth/logout
    logout_res = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_res.status_code == 200
