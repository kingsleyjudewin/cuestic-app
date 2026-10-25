from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.member import Member
from app.utils.datetime_utils import utc_now
from datetime import timedelta
from app.extensions import db


def test_create_member_success(client, admin_user, seed_teams):
    """Test creating a valid member normalizes phone number."""
    response = client.post("/api/v1/members", headers=admin_user["headers"], json={
        "full_name": "Dev Sharma",
        "registration_number": "REG2026-999",
        "class_name": "3rd Year CSE",
        "section": "A",
        "phone_number": "9876543210",  # Raw Indian number without country code
        "country_code": "+91",
        "team_id": seed_teams["volunteering"].id,
        "whatsapp_opt_in": True,
    })
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["full_name"] == "Dev Sharma"
    assert data["registration_number"] == "REG2026-999"
    # Verify phone was normalized to E.164
    assert data["phone_number"] == "+919876543210"
    assert data["whatsapp_opt_in"] is True
    assert data["is_active"] is True


def test_create_member_invalid_phone(client, admin_user, seed_teams):
    """Test rejection of invalid phone numbers."""
    response = client.post("/api/v1/members", headers=admin_user["headers"], json={
        "full_name": "Bad Phone Person",
        "class_name": "1st Year",
        "phone_number": "12345",  # Invalid number
        "team_id": seed_teams["volunteering"].id,
    })
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_create_member_duplicate_registration_number(client, admin_user, seed_members, seed_teams):
    """Test rejection of duplicate registration number."""
    response = client.post("/api/v1/members", headers=admin_user["headers"], json={
        "full_name": "Duplicate Person",
        "registration_number": "REG2026-001",  # Same as Ananya Sharma
        "class_name": "2nd Year",
        "phone_number": "+919876500099",
        "team_id": seed_teams["volunteering"].id,
    })
    assert response.status_code == 409
    data = response.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "CONFLICT"


def test_list_members_by_team(client, admin_user, seed_members, seed_teams):
    """Test filtering members by team."""
    vol_team_id = seed_teams["volunteering"].id
    response = client.get(f"/api/v1/members?team_id={vol_team_id}", headers=admin_user["headers"])
    assert response.status_code == 200
    data = response.get_json()["data"]
    # Should only return Ananya and Rohan (Volunteering)
    assert len(data) == 2
    for m in data:
        assert m["team_id"] == vol_team_id


def test_search_members_by_name_and_reg(client, admin_user, seed_members):
    """Test search functionality matching name and registration number."""
    # Search by partial name
    res1 = client.get("/api/v1/members?search=Ananya", headers=admin_user["headers"])
    assert res1.status_code == 200
    assert len(res1.get_json()["data"]) == 1
    assert res1.get_json()["data"][0]["registration_number"] == "REG2026-001"

    # Search by registration number
    res2 = client.get("/api/v1/members?search=REG2026-002", headers=admin_user["headers"])
    assert res2.status_code == 200
    assert len(res2.get_json()["data"]) == 1
    assert res2.get_json()["data"][0]["full_name"] == "Rohan Verma"


def test_prevent_unauthorized_access_to_phone_numbers(client, member_user, seed_members):
    """Test that ordinary member cannot see unmasked phone numbers of other members."""
    response = client.get("/api/v1/members", headers=member_user["headers"])
    assert response.status_code == 200
    data = response.get_json()["data"]
    for m in data:
        if m["id"] == seed_members["m1"].id:
            # Linked user is member_user, so own phone is visible
            assert m["phone_number"] == "+919876500001"
        else:
            # Other members' phone numbers MUST be masked
            assert "*****" in m["phone_number"]


def test_deactivate_member_preserves_assignment_history(client, admin_user, seed_members, sample_event):
    """
    Test that deleting a member who has historical assignments soft-deactivates
    them rather than destroying history or failing.
    """
    m = seed_members["m1"]

    # Assign task to m1
    task = Task(
        event_id=sample_event.id,
        title="Sample Task for History",
        deadline=utc_now() + timedelta(days=2),
        created_by=admin_user["user"].id,
    )
    db.session.add(task)
    db.session.flush()

    assignment = TaskAssignment(
        task_id=task.id,
        member_id=m.id,
        assigned_by=admin_user["user"].id,
        status=TaskAssignment.STATUS_AWAITING_CONFIRMATION,
    )
    db.session.add(assignment)
    db.session.commit()

    # Now attempt deletion
    response = client.delete(f"/api/v1/members/{m.id}", headers=admin_user["headers"])
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["hard_deleted"] is False
    assert data["is_active"] is False

    # Verify member is still in database but marked inactive
    refreshed_member = db.session.get(Member, m.id)
    assert refreshed_member is not None
    assert refreshed_member.is_active is False
    # Verify assignment history was preserved!
    assert refreshed_member.assignments.count() == 1
