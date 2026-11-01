from datetime import timedelta
from app.utils.datetime_utils import utc_now


def test_create_event_success(client, admin_user):
    """Test creating an event with valid dates and location."""
    start_time = utc_now() + timedelta(days=10)
    end_time = start_time + timedelta(days=2)

    response = client.post("/api/v1/events", headers=admin_user["headers"], json={
        "name": "TECHFEST 2026",
        "description": "Annual technical symposium",
        "start_at": start_time.isoformat(),
        "end_at": end_time.isoformat(),
        "location": "Auditorium Block A",
        "status": "upcoming",
    })
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["name"] == "TECHFEST 2026"
    assert data["status"] == "upcoming"
    assert data["task_count"] == 0


def test_create_event_invalid_dates(client, admin_user):
    """Test rejection when end_at is earlier than start_at."""
    start_time = utc_now() + timedelta(days=10)
    end_time = start_time - timedelta(days=1)  # end before start

    response = client.post("/api/v1/events", headers=admin_user["headers"], json={
        "name": "Invalid Date Event",
        "start_at": start_time.isoformat(),
        "end_at": end_time.isoformat(),
    })
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_event_status_transitions(client, admin_user, sample_event):
    """Test allowed transitions and rejection of invalid status transitions."""
    event_id = sample_event.id

    # upcoming -> active (allowed)
    res1 = client.patch(f"/api/v1/events/{event_id}", headers=admin_user["headers"], json={
        "status": "active"
    })
    assert res1.status_code == 200
    assert res1.get_json()["data"]["status"] == "active"

    # active -> completed (allowed)
    res2 = client.patch(f"/api/v1/events/{event_id}", headers=admin_user["headers"], json={
        "status": "completed"
    })
    assert res2.status_code == 200
    assert res2.get_json()["data"]["status"] == "completed"

    # completed -> upcoming (disallowed)
    res3 = client.patch(f"/api/v1/events/{event_id}", headers=admin_user["headers"], json={
        "status": "upcoming"
    })
    assert res3.status_code == 400
    assert "cannot transition" in res3.get_json()["error"]["message"].lower()


def test_create_duplicate_event_name_rejected(client, admin_user, sample_event):
    """Test rejection when creating an event with duplicate name."""
    response = client.post("/api/v1/events", headers=admin_user["headers"], json={
        "name": sample_event.name,
        "start_at": (utc_now() + timedelta(days=20)).isoformat(),
    })
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "CONFLICT"
    assert "already exists" in response.get_json()["error"]["message"].lower()


def test_team_leader_can_create_event(client, team_leader_user):
    """Test team leader has authorized role to create event."""
    response = client.post("/api/v1/events", headers=team_leader_user["headers"], json={
        "name": "Leader Organized Hackathon",
        "description": "Organized by team leader",
        "start_at": (utc_now() + timedelta(days=5)).isoformat(),
        "location": "Seminar Hall 2",
    })
    assert response.status_code == 201
    assert response.get_json()["data"]["name"] == "Leader Organized Hackathon"


def test_member_cannot_create_event(client, member_user):
    """Test ordinary member role is rejected with 403 Forbidden."""
    response = client.post("/api/v1/events", headers=member_user["headers"], json={
        "name": "Unauthorized Member Event",
        "start_at": (utc_now() + timedelta(days=5)).isoformat(),
    })
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "FORBIDDEN"


def test_create_event_invalid_payload(client, admin_user):
    """Test validation errors on missing or invalid payload fields."""
    # Missing required start_at
    res1 = client.post("/api/v1/events", headers=admin_user["headers"], json={
        "name": "No Start Time Event",
    })
    assert res1.status_code == 400
    assert "start_at" in res1.get_json()["error"]["details"]

    # Name too short
    res2 = client.post("/api/v1/events", headers=admin_user["headers"], json={
        "name": "A",
        "start_at": (utc_now() + timedelta(days=1)).isoformat(),
    })
    assert res2.status_code == 400
    assert "name" in res2.get_json()["error"]["details"]

    # Invalid status value
    res3 = client.post("/api/v1/events", headers=admin_user["headers"], json={
        "name": "Invalid Status Event",
        "start_at": (utc_now() + timedelta(days=1)).isoformat(),
        "status": "non_existent_status",
    })
    assert res3.status_code == 400
    assert "status" in res3.get_json()["error"]["details"]


def test_create_event_persists_and_returns_in_list(client, admin_user):
    """Test created event is persisted to database and appears in listing."""
    create_res = client.post("/api/v1/events", headers=admin_user["headers"], json={
        "name": "Persisted Symposium 2026",
        "description": "Check persistence",
        "start_at": (utc_now() + timedelta(days=15)).isoformat(),
        "location": "Auditorium",
        "status": "upcoming",
    })
    assert create_res.status_code == 201
    created_id = create_res.get_json()["data"]["id"]

    # Fetch event by ID
    get_res = client.get(f"/api/v1/events/{created_id}", headers=admin_user["headers"])
    assert get_res.status_code == 200
    assert get_res.get_json()["data"]["name"] == "Persisted Symposium 2026"

    # List events
    list_res = client.get("/api/v1/events", headers=admin_user["headers"])
    assert list_res.status_code == 200
    event_ids = [e["id"] for e in list_res.get_json()["data"]]
    assert created_id in event_ids


def test_event_archive_endpoint(client, admin_user, sample_event):
    """Test archiving an event marks it completed."""
    event_id = sample_event.id
    response = client.post(f"/api/v1/events/{event_id}/archive", headers=admin_user["headers"])
    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == "completed"


def test_event_teams_endpoint(client, admin_user, sample_event, seed_teams):
    """Test loading teams available for an event without duplicating membership."""
    event_id = sample_event.id
    response = client.get(f"/api/v1/events/{event_id}/teams", headers=admin_user["headers"])
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["event_id"] == event_id
    assert len(data["teams"]) >= 3
