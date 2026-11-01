import pytest
from app.models.user import User, ApiToken
from app.models.team import Team
from app.models.member import Member
from app.extensions import db


def test_president_create_member_account_across_all_teams(client, admin_user, seed_teams):
    """
    President can create member login accounts across all teams,
    including Volunteering, Documentation, Media, and a 4th team (e.g. Logistics).
    """
    # Create the 4th configurable team
    logistics_team = Team(name="Logistics", slug="logistics", description="Logistics and setup team")
    db.session.add(logistics_team)
    db.session.commit()

    teams_to_test = [
        ("Volunteering", seed_teams["volunteering"].id, "rahul_vol", "rahul@test.edu", "+919876543201", "REG2026-101"),
        ("Documentation", seed_teams["documentation"].id, "priya_doc", "priya@test.edu", "+919876543202", "REG2026-102"),
        ("Media", seed_teams["media"].id, "arjun_media", "arjun@test.edu", "+919876543203", "REG2026-103"),
        ("Logistics", logistics_team.id, "vikram_log", "vikram@test.edu", "+919876543204", "REG2026-104"),
    ]

    for team_name, team_id, username, email, phone, reg_no in teams_to_test:
        payload = {
            "full_name": f"{team_name} Lead Person",
            "registration_number": reg_no,
            "class_name": "3rd Year CSE",
            "section": "A",
            "phone_number": phone,
            "team_id": team_id,
            "username": username,
            "email": email,
            "password": "InitialPassword123!",
            "role": "member",
        }

        # Test POST /api/v1/members/account
        res = client.post("/api/v1/members/account", headers=admin_user["headers"], json=payload)
        assert res.status_code == 201, f"Failed for {team_name}: {res.get_json()}"
        data = res.get_json()["data"]

        member_data = data["member"]
        user_data = data["user"]

        assert member_data["full_name"] == f"{team_name} Lead Person"
        assert member_data["registration_number"] == reg_no
        assert member_data["team_id"] == team_id
        assert member_data["linked_user_id"] == user_data["id"]
        assert member_data["linked_user"] is not None
        assert member_data["linked_user"]["username"] == username

        assert user_data["username"] == username
        assert user_data["email"] == email
        assert user_data["role"] == "member"
        assert user_data["is_active"] is True

        # Verify password is NOT stored in plaintext
        created_user = db.session.get(User, user_data["id"])
        assert created_user is not None
        assert created_user.password_hash != "InitialPassword123!"
        assert created_user.check_password("InitialPassword123!") is True

        # Verify new user can successfully authenticate via /api/v1/auth/login
        login_res = client.post("/api/v1/auth/login", json={
            "username": username,
            "password": "InitialPassword123!",
        })
        assert login_res.status_code == 200
        login_data = login_res.get_json()["data"]
        assert login_data["user"]["username"] == username
        assert login_data["user"]["role"] == "member"
        assert "token" in login_data


def test_post_users_alias_endpoint(client, admin_user, seed_teams):
    """Verify POST /api/v1/users works as the standard user creation endpoint."""
    payload = {
        "full_name": "Kavita Rao",
        "registration_number": "REG2026-200",
        "class_name": "2nd Year IT",
        "section": "B",
        "phone_number": "+919876543205",
        "team_id": seed_teams["volunteering"].id,
        "username": "kavita_rao",
        "email": "kavita@test.edu",
        "password": "SecurePassword456!",
        "role": "team_leader",
    }
    res = client.post("/api/v1/users", headers=admin_user["headers"], json=payload)
    assert res.status_code == 201
    data = res.get_json()["data"]
    assert data["user"]["role"] == "team_leader"


def test_ordinary_member_cannot_create_account(client, member_user, seed_teams):
    """Ordinary members must be forbidden from creating accounts."""
    payload = {
        "full_name": "Unauthorized User",
        "registration_number": "REG2026-999",
        "class_name": "1st Year",
        "phone_number": "+919876543206",
        "team_id": seed_teams["volunteering"].id,
        "username": "unauth_user",
        "email": "unauth@test.edu",
        "password": "Password123!",
        "role": "member",
    }
    # Test /members/account
    res1 = client.post("/api/v1/members/account", headers=member_user["headers"], json=payload)
    assert res1.status_code == 403

    # Test /users
    res2 = client.post("/api/v1/users", headers=member_user["headers"], json=payload)
    assert res2.status_code == 403


def test_reject_privilege_escalation_role(client, admin_user, seed_teams):
    """Ensure users cannot assign themselves or others elevated roles (president, admin)."""
    payload = {
        "full_name": "Fake President",
        "registration_number": "REG2026-998",
        "class_name": "1st Year",
        "phone_number": "+919876543207",
        "team_id": seed_teams["volunteering"].id,
        "username": "fake_pres",
        "email": "fakepres@test.edu",
        "password": "Password123!",
        "role": "president",
    }
    res = client.post("/api/v1/members/account", headers=admin_user["headers"], json=payload)
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_duplicate_identifiers_rejected(client, admin_user, seed_teams):
    """Check that duplicate username, email, registration number, or phone are rejected."""
    base_payload = {
        "full_name": "Original Member",
        "registration_number": "REG2026-301",
        "class_name": "3rd Year",
        "phone_number": "+919876543210",
        "team_id": seed_teams["volunteering"].id,
        "username": "orig_user",
        "email": "orig@test.edu",
        "password": "Password123!",
        "role": "member",
    }
    res = client.post("/api/v1/members/account", headers=admin_user["headers"], json=base_payload)
    assert res.status_code == 201

    # 1. Duplicate username
    dup_username = dict(base_payload, registration_number="REG2026-302", phone_number="+919876543211", email="other1@test.edu")
    res_dup_u = client.post("/api/v1/members/account", headers=admin_user["headers"], json=dup_username)
    assert res_dup_u.status_code == 409
    assert res_dup_u.get_json()["error"]["code"] == "CONFLICT"

    # 2. Duplicate email
    dup_email = dict(base_payload, username="other_u2", registration_number="REG2026-303", phone_number="+919876543212")
    res_dup_e = client.post("/api/v1/members/account", headers=admin_user["headers"], json=dup_email)
    assert res_dup_e.status_code == 409
    assert res_dup_e.get_json()["error"]["code"] == "CONFLICT"

    # 3. Duplicate registration number
    dup_reg = dict(base_payload, username="other_u3", email="other3@test.edu", phone_number="+919876543213")
    res_dup_r = client.post("/api/v1/members/account", headers=admin_user["headers"], json=dup_reg)
    assert res_dup_r.status_code == 409
    assert res_dup_r.get_json()["error"]["code"] == "CONFLICT"

    # 4. Duplicate phone number
    dup_phone = dict(base_payload, username="other_u4", email="other4@test.edu", registration_number="REG2026-304")
    res_dup_p = client.post("/api/v1/members/account", headers=admin_user["headers"], json=dup_phone)
    assert res_dup_p.status_code == 409
    assert res_dup_p.get_json()["error"]["code"] == "CONFLICT"


def test_invalid_team_id_rejected(client, admin_user):
    """Reject account creation with non-existent team."""
    payload = {
        "full_name": "No Team Member",
        "registration_number": "REG2026-401",
        "class_name": "2nd Year",
        "phone_number": "+919876543215",
        "team_id": 99999,
        "username": "noteam_user",
        "email": "noteam@test.edu",
        "password": "Password123!",
        "role": "member",
    }
    res = client.post("/api/v1/members/account", headers=admin_user["headers"], json=payload)
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_deactivated_account_cannot_login(client, admin_user, seed_teams):
    """Deactivating a member also disables their linked user account and prevents login."""
    payload = {
        "full_name": "Deactivate Me",
        "registration_number": "REG2026-501",
        "class_name": "4th Year",
        "phone_number": "+919876543216",
        "team_id": seed_teams["volunteering"].id,
        "username": "deactivate_user",
        "email": "deactivate@test.edu",
        "password": "Password123!",
        "role": "member",
    }
    create_res = client.post("/api/v1/members/account", headers=admin_user["headers"], json=payload)
    assert create_res.status_code == 201
    member_id = create_res.get_json()["data"]["member"]["id"]

    # Member can initially log in
    login_res1 = client.post("/api/v1/auth/login", json={
        "username": "deactivate_user",
        "password": "Password123!",
    })
    assert login_res1.status_code == 200

    # Deactivate the member via PATCH
    deactivate_res = client.patch(f"/api/v1/members/{member_id}", headers=admin_user["headers"], json={
        "is_active": False,
    })
    assert deactivate_res.status_code == 200
    assert deactivate_res.get_json()["data"]["is_active"] is False

    # Login should now fail with 401
    login_res2 = client.post("/api/v1/auth/login", json={
        "username": "deactivate_user",
        "password": "Password123!",
    })
    assert login_res2.status_code == 401
    assert "disabled" in login_res2.get_json()["error"]["message"].lower() or "inactive" in login_res2.get_json()["error"]["message"].lower() or "invalid" in login_res2.get_json()["error"]["message"].lower()


def test_password_reset_flow_and_session_invalidation(client, admin_user, seed_teams):
    """
    President can reset a member's password.
    This revokes active session tokens and allows logging in with the new password.
    """
    payload = {
        "full_name": "Reset Password Test",
        "registration_number": "REG2026-601",
        "class_name": "2nd Year",
        "phone_number": "+919876543217",
        "team_id": seed_teams["volunteering"].id,
        "username": "reset_user",
        "email": "reset@test.edu",
        "password": "OldPassword123!",
        "role": "member",
    }
    create_res = client.post("/api/v1/members/account", headers=admin_user["headers"], json=payload)
    assert create_res.status_code == 201
    member_id = create_res.get_json()["data"]["member"]["id"]

    # Log in to get active session token
    login1 = client.post("/api/v1/auth/login", json={
        "username": "reset_user",
        "password": "OldPassword123!",
    })
    assert login1.status_code == 200
    old_token = login1.get_json()["data"]["token"]

    # Verify old token works on /api/v1/auth/me
    me1 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"})
    assert me1.status_code == 200

    # President resets the password
    reset_res = client.post(f"/api/v1/members/{member_id}/reset-password", headers=admin_user["headers"], json={
        "new_password": "NewBrandNewPassword789!",
    })
    assert reset_res.status_code == 200
    assert reset_res.get_json()["success"] is True

    # Verify old session token is revoked immediately
    me2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"})
    assert me2.status_code == 401

    # Verify old password no longer works
    bad_login = client.post("/api/v1/auth/login", json={
        "username": "reset_user",
        "password": "OldPassword123!",
    })
    assert bad_login.status_code == 401

    # Verify new password works
    new_login = client.post("/api/v1/auth/login", json={
        "username": "reset_user",
        "password": "NewBrandNewPassword789!",
    })
    assert new_login.status_code == 200
