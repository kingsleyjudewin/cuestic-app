from app.models.team import Team


def test_list_teams_with_member_counts(client, admin_user, seed_teams, seed_members):
    """Test retrieving teams includes member counts."""
    response = client.get("/api/v1/teams", headers=admin_user["headers"])
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert len(data) >= 3

    # Volunteering should have 2 active members (Ananya, Rohan)
    vol_team = next(t for t in data if t["slug"] == "volunteering")
    assert vol_team["member_count"] == 2


def test_create_fourth_team_configurable(client, admin_user):
    """Test creating the fourth team with custom name and description."""
    response = client.post("/api/v1/teams", headers=admin_user["headers"], json={
        "name": "Logistics & Operations",
        "description": "Handles venue setup, stage technicals and physical inventories",
    })
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["name"] == "Logistics & Operations"
    assert data["slug"] == "logistics-operations"
    assert data["member_count"] == 0


def test_rename_team(client, admin_user, seed_teams):
    """Test updating and renaming a team."""
    team_id = seed_teams["media"].id
    response = client.patch(f"/api/v1/teams/{team_id}", headers=admin_user["headers"], json={
        "name": "Media & Creative Design",
    })
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["name"] == "Media & Creative Design"
    assert data["slug"] == "media-creative-design"


def test_reject_duplicate_team_name(client, admin_user, seed_teams):
    """Test rejecting duplicate team names."""
    response = client.post("/api/v1/teams", headers=admin_user["headers"], json={
        "name": "Volunteering",  # already exists
    })
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "CONFLICT"


def test_get_team_members(client, admin_user, seed_teams, seed_members):
    """Test retrieving members belonging to a team."""
    team_id = seed_teams["volunteering"].id
    response = client.get(f"/api/v1/teams/{team_id}/members", headers=admin_user["headers"])
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert len(data) == 2
    names = [m["full_name"] for m in data]
    assert "Ananya Sharma" in names
    assert "Rohan Verma" in names
