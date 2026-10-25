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
