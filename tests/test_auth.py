from datetime import timedelta
from app.extensions import db
from app.models.user import User, ApiToken
from app.utils.datetime_utils import utc_now


def test_login_success(client, admin_user):
    """Test login with valid credentials returns Bearer token."""
    response = client.post("/api/v1/auth/login", json={
        "username": "test_admin",
        "password": "Password123!",
        "device_name": "Test iPhone"
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "token" in data["data"]
    assert data["data"]["token_type"] == "Bearer"
    assert data["data"]["user"]["username"] == "test_admin"
    assert data["data"]["user"]["role"] == User.ROLE_PRESIDENT


def test_login_invalid_password(client, admin_user):
    """Test login with wrong password is rejected."""
    response = client.post("/api/v1/auth/login", json={
        "username": "test_admin",
        "password": "WrongPassword!"
    })
    assert response.status_code == 401
    data = response.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "AUTHENTICATION_ERROR"


def test_login_inactive_user(client):
    """Test inactive account cannot log in."""
    user = User(username="inactive_guy", role=User.ROLE_MEMBER, is_active=False)
    user.set_password("Password123!")
    db.session.add(user)
    db.session.commit()

    response = client.post("/api/v1/auth/login", json={
        "username": "inactive_guy",
        "password": "Password123!"
    })
    assert response.status_code == 401
    assert "inactive" in response.get_json()["error"]["message"].lower()


def test_auth_me_success(client, admin_user):
    """Test /me endpoint with valid token."""
    response = client.get("/api/v1/auth/me", headers=admin_user["headers"])
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["username"] == "test_admin"


def test_auth_me_unauthorized(client):
    """Test /me endpoint without token is rejected."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    data = response.get_json()
    assert data["success"] is False


def test_logout_revokes_token(client, admin_user):
    """Test logout successfully revokes token preventing further access."""
    # First verify token works
    res1 = client.get("/api/v1/auth/me", headers=admin_user["headers"])
    assert res1.status_code == 200

    # Logout
    logout_res = client.post("/api/v1/auth/logout", headers=admin_user["headers"])
    assert logout_res.status_code == 200

    # Verify same token is now rejected
    res2 = client.get("/api/v1/auth/me", headers=admin_user["headers"])
    assert res2.status_code == 401
    assert "revoked" in res2.get_json()["error"]["message"].lower()


def test_expired_token_rejected(client, admin_user):
    """Test that expired token is rejected."""
    token_rec = ApiToken.query.filter_by(token_hash=ApiToken.hash_token(admin_user["token"])).first()
    # Manually expire the token in the past
    token_rec.expires_at = utc_now() - timedelta(days=1)
    db.session.commit()

    response = client.get("/api/v1/auth/me", headers=admin_user["headers"])
    assert response.status_code == 401
    assert "expired" in response.get_json()["error"]["message"].lower()
