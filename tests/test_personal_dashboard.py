import pytest
from datetime import timedelta
from app.extensions import db
from app.models.user import User
from app.models.member import Member
from app.models.event import Event
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.utils.datetime_utils import utc_now
from tests.conftest import create_user_with_token


def test_volunteer_personal_assignments_endpoint(client, app, admin_user, seed_teams):
    """Verify GET /api/v1/me/assignments returns only the authenticated member's assignments."""
    with app.app_context():
        # Create volunteer user and member
        vol_user, vol_token = create_user_with_token("sagar.cu", User.ROLE_MEMBER, "sagar.cu@gmail.com")
        vol_member = Member(
            full_name="Sagar CU",
            registration_number="REG-SAGAR",
            class_name="6BTEC",
            section="A",
            phone_number="+919008762143",
            team_id=seed_teams["volunteering"].id,
            linked_user_id=vol_user.id,
            is_active=True,
        )
        db.session.add(vol_member)

        # Create second volunteer user and member
        vol2_user, vol2_token = create_user_with_token("jayani.cu", User.ROLE_MEMBER, "jayani.cu@gmail.com")
        vol2_member = Member(
            full_name="Jayani CU",
            registration_number="REG-JAYANI",
            class_name="4BTELCS",
            section="B",
            phone_number="+918148311354",
            team_id=seed_teams["volunteering"].id,
            linked_user_id=vol2_user.id,
            is_active=True,
        )
        db.session.add(vol2_member)

        # Create event
        event = Event(
            name="MAGNOVITE 2026",
            start_at=utc_now() + timedelta(days=5),
            location="Auditorium",
            status=Event.STATUS_ACTIVE,
            created_by=admin_user["user"].id,
        )
        db.session.add(event)
        db.session.flush()

        # Create task 1: Crowd Control (assigned to Sagar CU)
        task1 = Task(
            event_id=event.id,
            title="Crowd Control",
            description="Manage crowd flow at the auditorium entrance.",
            priority=Task.PRIORITY_HIGH,
            deadline=utc_now() + timedelta(days=2),
            created_by=admin_user["user"].id,
        )
        db.session.add(task1)
        db.session.flush()

        assignment1 = TaskAssignment(
            task_id=task1.id,
            member_id=vol_member.id,
            assigned_by=admin_user["user"].id,
            status=TaskAssignment.STATUS_AWAITING_CONFIRMATION,
        )
        db.session.add(assignment1)

        # Create task 2: Stage Decoration (assigned to Jayani CU)
        task2 = Task(
            event_id=event.id,
            title="Stage Decoration",
            description="Set up podium banners.",
            priority=Task.PRIORITY_MEDIUM,
            deadline=utc_now() + timedelta(days=3),
            created_by=admin_user["user"].id,
        )
        db.session.add(task2)
        db.session.flush()

        assignment2 = TaskAssignment(
            task_id=task2.id,
            member_id=vol2_member.id,
            assigned_by=admin_user["user"].id,
            status=TaskAssignment.STATUS_AWAITING_CONFIRMATION,
        )
        db.session.add(assignment2)
        db.session.commit()

        vol1_headers = {"Authorization": f"Bearer {vol_token}", "Content-Type": "application/json"}
        vol2_headers = {"Authorization": f"Bearer {vol2_token}", "Content-Type": "application/json"}
        vol_assignment1_id = assignment1.id
        vol_assignment2_id = assignment2.id

    # 1. Sagar queries /api/v1/me/assignments -> sees ONLY Task 1 ("Crowd Control")
    res1 = client.get("/api/v1/me/assignments", headers=vol1_headers)
    assert res1.status_code == 200
    data1 = res1.get_json()["data"]
    assert len(data1) == 1
    assert data1[0]["id"] == vol_assignment1_id
    assert data1[0]["task_title"] == "Crowd Control"
    assert data1[0]["task_description"] == "Manage crowd flow at the auditorium entrance."
    assert data1[0]["event_name"] == "MAGNOVITE 2026"
    assert data1[0]["member_name"] == "Sagar CU"
    assert data1[0]["status"] == "awaiting_confirmation"

    # 2. Jayani queries /api/v1/me/assignments -> sees ONLY Task 2 ("Stage Decoration")
    res2 = client.get("/api/v1/me/assignments", headers=vol2_headers)
    assert res2.status_code == 200
    data2 = res2.get_json()["data"]
    assert len(data2) == 1
    assert data2[0]["id"] == vol_assignment2_id
    assert data2[0]["task_title"] == "Stage Decoration"
    assert data2[0]["task_description"] == "Set up podium banners."
    assert data2[0]["member_name"] == "Jayani CU"

    # 3. Query parameter spoofing attempt: Sagar queries with ?member_id=<Jayani's ID>
    res_spoof = client.get(f"/api/v1/me/assignments?member_id={data2[0]['member_id']}", headers=vol1_headers)
    assert res_spoof.status_code == 200
    spoof_data = res_spoof.get_json()["data"]
    # Still only returns Sagar's assignments, strictly ignoring query param!
    assert len(spoof_data) == 1
    assert spoof_data[0]["id"] == vol_assignment1_id
    assert spoof_data[0]["task_title"] == "Crowd Control"

    # 4. Check alias endpoint /api/v1/assignments/me works identically
    res_alias = client.get("/api/v1/assignments/me", headers=vol1_headers)
    assert res_alias.status_code == 200
    assert len(res_alias.get_json()["data"]) == 1
    assert res_alias.get_json()["data"][0]["task_title"] == "Crowd Control"


def test_me_profile_endpoint(client, app, seed_teams):
    """Verify GET /api/v1/me/profile returns member details and team name."""
    with app.app_context():
        user, token = create_user_with_token("devananda.ajith", User.ROLE_MEMBER, "devananda.ajith@gmail.com")
        member = Member(
            full_name="Devananda Ajith",
            registration_number="REG-DEVA",
            class_name="6BTEC",
            phone_number="+918289829614",
            team_id=seed_teams["volunteering"].id,
            linked_user_id=user.id,
            is_active=True,
        )
        db.session.add(member)
        db.session.commit()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    res = client.get("/api/v1/me/profile", headers=headers)
    assert res.status_code == 200
    body = res.get_json()["data"]
    assert body["username"] == "devananda.ajith"
    assert body["role"] == "member"
    assert body["member_name"] == "Devananda Ajith"
    assert body["team_name"] == "Volunteering"


def test_unlinked_user_me_assignments_returns_404(client, app):
    """Verify user without a linked member record returns 404 error on /me/assignments."""
    with app.app_context():
        user, token = create_user_with_token("unlinked_user", User.ROLE_MEMBER)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    res = client.get("/api/v1/me/assignments", headers=headers)
    assert res.status_code == 404
    body = res.get_json()
    assert "error" in body
    assert "not associated with any club member record" in body["error"]["message"]


def test_volunteer_workflow_status_transitions(client, app, admin_user, seed_teams):
    """Test volunteer accepting, starting, and submitting task, while completed/cancelled are forbidden."""
    with app.app_context():
        user, token = create_user_with_token("kanishk", User.ROLE_MEMBER, "kanishk@gmail.com")
        member = Member(
            full_name="Kanishk",
            registration_number="REG-KANISHK",
            class_name="6BTELCS",
            phone_number="+918089281159",
            team_id=seed_teams["volunteering"].id,
            linked_user_id=user.id,
            is_active=True,
        )
        db.session.add(member)

        # Another member's assignment
        other_user, other_token = create_user_with_token("other_vol", User.ROLE_MEMBER)
        other_member = Member(
            full_name="Other Member",
            registration_number="REG-OTHER",
            class_name="6BTEC",
            phone_number="+919999999999",
            team_id=seed_teams["volunteering"].id,
            linked_user_id=other_user.id,
            is_active=True,
        )
        db.session.add(other_member)

        event = Event(
            name="College Fest 2026",
            start_at=utc_now() + timedelta(days=2),
            status=Event.STATUS_ACTIVE,
            created_by=admin_user["user"].id,
        )
        db.session.add(event)
        db.session.flush()

        task = Task(
            event_id=event.id,
            title="Logistics Setup",
            description="Arrange chairs and sound system.",
            priority=Task.PRIORITY_MEDIUM,
            deadline=utc_now() + timedelta(days=1),
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

        other_assignment = TaskAssignment(
            task_id=task.id,
            member_id=other_member.id,
            assigned_by=admin_user["user"].id,
            status=TaskAssignment.STATUS_AWAITING_CONFIRMATION,
        )
        db.session.add(other_assignment)
        db.session.commit()

        aid = assignment.id
        other_aid = other_assignment.id
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 1. Step 1: Accept task -> status becomes 'accepted'
    res_accept = client.patch(
        f"/api/v1/assignments/{aid}/status",
        headers=headers,
        json={"status": "accepted"}
    )
    assert res_accept.status_code == 200
    assert res_accept.get_json()["data"]["status"] == "accepted"

    # 2. Step 2: Start task -> status becomes 'in_progress'
    res_start = client.patch(
        f"/api/v1/assignments/{aid}/status",
        headers=headers,
        json={"status": "in_progress"}
    )
    assert res_start.status_code == 200
    assert res_start.get_json()["data"]["status"] == "in_progress"

    # 3. Step 3: Try to mark 'completed' -> should be forbidden (403)
    res_complete = client.patch(
        f"/api/v1/assignments/{aid}/status",
        headers=headers,
        json={"status": "completed"}
    )
    assert res_complete.status_code == 403

    # 4. Step 4: Submit work with completion note -> status becomes 'submitted'
    res_submit = client.patch(
        f"/api/v1/assignments/{aid}/status",
        headers=headers,
        json={"status": "submitted", "completion_note": "Chairs and sound system all set."}
    )
    assert res_submit.status_code == 200
    assert res_submit.get_json()["data"]["status"] == "submitted"
    assert res_submit.get_json()["data"]["completion_note"] == "Chairs and sound system all set."

    # 5. Volunteer cannot modify another member's assignment -> should be 403 Forbidden
    res_other = client.patch(
        f"/api/v1/assignments/{other_aid}/status",
        headers=headers,
        json={"status": "accepted"}
    )
    assert res_other.status_code == 403


def test_volunteer_cannot_access_administrative_endpoints(client, app, seed_teams):
    """Verify volunteers cannot create events, tasks, teams, or member accounts."""
    with app.app_context():
        user, token = create_user_with_token("shohil.mathew", User.ROLE_MEMBER, "shohil.mathew@gmail.com")
        member = Member(
            full_name="Shohil Mathew",
            registration_number="REG-SHOHIL",
            class_name="6BTEC",
            phone_number="+919487449346",
            team_id=seed_teams["volunteering"].id,
            linked_user_id=user.id,
            is_active=True,
        )
        db.session.add(member)
        db.session.commit()
        member_id = member.id
        team_id = seed_teams["volunteering"].id
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Attempt to create an event
    res_event = client.post("/api/v1/events", headers=headers, json={
        "name": "Rogue Event",
        "start_at": "2026-11-01T10:00:00Z",
    })
    assert res_event.status_code == 403

    # Attempt to create a member account
    res_account = client.post("/api/v1/users", headers=headers, json={
        "full_name": "Fake Member",
        "team_id": team_id,
        "class_name": "6BTEC",
        "phone_number": "+919999988888",
    })
    assert res_account.status_code == 403

    # Attempt to create a task for an event
    res_task = client.post("/api/v1/events/1/tasks", headers=headers, json={
        "title": "Rogue Task",
        "deadline": "2026-11-01T10:00:00Z",
        "member_ids": [member_id],
    })
    assert res_task.status_code == 403
