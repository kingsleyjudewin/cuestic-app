"""Mandatory password change: server-side enforcement, admin exemption, session handling.

The restriction is enforced in app/utils/permissions.token_required, so these tests call the API
directly (as an old app build or a hand-crafted client would) instead of relying on any UI.
"""
import os
import threading

import pytest
from click.testing import CliRunner

from app.extensions import db
from app.models.user import User, ApiToken
from app.utils.password_policy import password_problems

OLD_PW = "Leaked-Pass-2025!"
NEW_PW = "Brand#NewSecret2026"


def make_user(username, role, required=True, password=OLD_PW, active=True):
    user = User(username=username, email=f"{username}@test.edu", role=role, is_active=active)
    user.set_password(password)
    user.password_change_required = required
    db.session.add(user)
    db.session.commit()
    return user


def login(client, username, password=OLD_PW):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def change(client, token, current=OLD_PW, new=NEW_PW, confirm=None):
    return client.post(
        "/api/v1/auth/change-password",
        headers=bearer(token),
        json={"current_password": current, "new_password": new, "confirm_password": new if confirm is None else confirm},
    )


PROTECTED = [
    ("GET", "/api/v1/dashboard/summary"),            # dashboard
    ("GET", "/api/v1/teams"),                        # teams
    ("GET", "/api/v1/events"),                       # events
    ("GET", "/api/v1/members"),                      # members
    ("GET", "/api/v1/me/assignments"),               # tasks
    ("GET", "/api/v1/communities"),                  # chat
    ("GET", "/api/v1/reports/assignments"),          # reports
    ("GET", "/api/v1/documentation/folders"),        # documentation reports
    ("POST", "/api/v1/research/attachments/upload"), # research uploads
    ("GET", "/api/v1/research/student/overview"),
    ("POST", "/api/v1/members/account"),             # administrative operation
]

NON_ADMIN_ROLES = [
    User.ROLE_PRESIDENT,
    User.ROLE_TEAM_LEADER,
    User.ROLE_MEMBER,
    User.ROLE_FACULTY_COORDINATOR,
    User.ROLE_STUDENT_RESEARCHER,
]


# --------------------------------------------------------------------------- admin exemption

def test_admin_logs_in_normally_and_is_never_restricted(app, client):
    with app.app_context():
        make_user("theadmin", User.ROLE_ADMIN, required=True)  # even if the flag is set
    resp = login(client, "theadmin")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["password_change_required"] is False
    assert data["user"]["password_change_required"] is False
    assert data["user"]["must_change_password"] is False
    token = data["token"]
    for method, path in [("GET", "/api/v1/dashboard/summary"), ("GET", "/api/v1/teams"), ("GET", "/api/v1/members")]:
        r = client.open(path, method=method, headers=bearer(token))
        assert r.status_code == 200, (path, r.get_data(as_text=True))


def test_admin_can_still_change_own_password(app, client):
    with app.app_context():
        make_user("theadmin", User.ROLE_ADMIN, required=False)
    token = login(client, "theadmin").get_json()["data"]["token"]
    assert change(client, token).status_code == 200
    assert login(client, "theadmin", NEW_PW).status_code == 200


# --------------------------------------------------------------------------- restriction

@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_non_admin_roles_must_change_password(app, client, role):
    with app.app_context():
        make_user("u_" + role, role)
    resp = login(client, "u_" + role)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["password_change_required"] is True
    assert data["user"]["password_change_required"] is True
    assert data["user"]["must_change_password"] is True  # older app builds key off this field


@pytest.mark.parametrize("method,path", PROTECTED)
def test_restricted_user_blocked_from_protected_endpoints(app, client, method, path):
    with app.app_context():
        make_user("pres", User.ROLE_PRESIDENT)
    token = login(client, "pres").get_json()["data"]["token"]
    r = client.open(path, method=method, headers=bearer(token), json={})
    assert r.status_code == 403, (path, r.status_code)
    body = r.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"


def test_restricted_user_can_reach_allowed_endpoints(app, client):
    with app.app_context():
        make_user("vol", User.ROLE_MEMBER)
    token = login(client, "vol").get_json()["data"]["token"]
    me = client.get("/api/v1/auth/me", headers=bearer(token))
    assert me.status_code == 200
    assert me.get_json()["data"]["password_change_required"] is True
    assert client.get("/api/v1/auth/password-policy").status_code == 200
    assert client.post("/api/v1/auth/logout", headers=bearer(token)).status_code == 200


def test_restriction_cannot_be_bypassed_with_cached_token_or_client_fields(app, client):
    """Client-sent role/flags are ignored; a warmed auth cache does not skip the check."""
    with app.app_context():
        make_user("sneaky", User.ROLE_MEMBER)
    token = login(client, "sneaky").get_json()["data"]["token"]
    # Token is now in the in-process cache (login caches it). Try repeatedly with forged hints.
    for _ in range(3):
        r = client.get(
            "/api/v1/teams?role=admin&password_change_required=false",
            headers={**bearer(token), "X-User-Role": "admin", "X-Password-Change-Required": "false"},
        )
        assert r.status_code == 403
    # Old app flow: changing the password through a non-allowed endpoint is impossible.
    r = client.put("/api/v1/me/profile", headers=bearer(token), json={"password_change_required": False})
    assert r.status_code in (403, 405)
    with app.app_context():
        assert User.query.filter_by(username="sneaky").one().password_change_required is True


def test_flag_set_by_another_process_applies_to_cached_sessions(app, client):
    with app.app_context():
        make_user("later", User.ROLE_TEAM_LEADER, required=False)
    token = login(client, "later").get_json()["data"]["token"]
    assert client.get("/api/v1/teams", headers=bearer(token)).status_code == 200
    # Simulate the CLI (a different process) flagging the account directly in the database.
    with app.app_context():
        db.session.execute(db.text("UPDATE users SET password_change_required = 1 WHERE username = 'later'"))
        db.session.commit()
    r = client.get("/api/v1/teams", headers=bearer(token))
    assert r.status_code == 403
    assert r.get_json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"


# --------------------------------------------------------------------------- change-password endpoint

def test_wrong_current_password_rejected_without_logging_out(app, client):
    with app.app_context():
        make_user("member1", User.ROLE_MEMBER)
    token = login(client, "member1").get_json()["data"]["token"]
    r = change(client, token, current="not-the-password")
    assert r.status_code == 400  # not 401: the client must not treat this as an expired session
    assert r.get_json()["error"]["code"] == "INVALID_CURRENT_PASSWORD"
    assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 200


def test_confirmation_mismatch_rejected(app, client):
    with app.app_context():
        make_user("member2", User.ROLE_MEMBER)
    token = login(client, "member2").get_json()["data"]["token"]
    r = change(client, token, confirm="Something#Else2026")
    assert r.status_code == 400
    assert r.get_json()["error"]["code"] == "PASSWORD_MISMATCH"


@pytest.mark.parametrize("weak", [
    "short#A1",               # too short
    "alllowercase#2026",      # no uppercase
    "ALLUPPERCASE#2026",      # no lowercase
    "NoDigitsHere#Abc",       # no number
    "NoSpecialChars2026",     # no special character
    "Password2026!",          # common
    OLD_PW,                   # reuse of the current password
])
def test_weak_or_reused_passwords_rejected(app, client, weak):
    with app.app_context():
        make_user("member3", User.ROLE_MEMBER)
    token = login(client, "member3").get_json()["data"]["token"]
    r = change(client, token, new=weak, confirm=weak)
    assert r.status_code == 400
    body = r.get_json()
    assert body["error"]["code"] == "WEAK_PASSWORD"
    assert weak not in r.get_data(as_text=True)  # never echo the password


def test_password_containing_username_rejected():
    assert any("username" in p for p in password_problems("Kingsley#Strong2026", username="kingsley.cu"))


def test_known_leaked_password_rejected_via_hash_file(app, client, tmp_path, monkeypatch):
    leaked = "Perfectly#Fine2026"
    with app.app_context():
        make_user("member4", User.ROLE_MEMBER)
    src = tmp_path / "leaked.txt"
    src.write_text(leaked + "\n")
    out = tmp_path / "hashes.txt"
    from app.cli import password_hashes_command
    res = CliRunner().invoke(password_hashes_command, ["--input", str(src), "--output", str(out)])
    assert res.exit_code == 0 and leaked not in out.read_text()
    monkeypatch.setenv("LEAKED_PASSWORD_HASHES_FILE", str(out))
    token = login(client, "member4").get_json()["data"]["token"]
    r = change(client, token, new=leaked)
    assert r.status_code == 400 and r.get_json()["error"]["code"] == "WEAK_PASSWORD"


def test_successful_change_clears_restriction_and_rotates_sessions(app, client):
    with app.app_context():
        make_user("member5", User.ROLE_MEMBER)
    first = login(client, "member5").get_json()["data"]["token"]
    second_device = login(client, "member5").get_json()["data"]["token"]

    r = change(client, first)
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert data["password_change_required"] is False
    assert data["user"]["password_change_required"] is False
    assert data["user"]["must_change_password"] is False
    new_token = data["token"]
    assert new_token and new_token not in (first, second_device)

    # Previous sessions (this device and others) are revoked.
    assert client.get("/api/v1/auth/me", headers=bearer(first)).status_code == 401
    assert client.get("/api/v1/auth/me", headers=bearer(second_device)).status_code == 401
    # New session has normal access.
    assert client.get("/api/v1/teams", headers=bearer(new_token)).status_code == 200
    # Old password no longer works; new one does and is unrestricted.
    assert login(client, "member5").status_code == 401
    relog = login(client, "member5", NEW_PW)
    assert relog.status_code == 200
    assert relog.get_json()["data"]["password_change_required"] is False
    with app.app_context():
        u = User.query.filter_by(username="member5").one()
        assert u.password_changed_at is not None
        assert NEW_PW not in u.password_hash and u.check_password(NEW_PW)


def test_replayed_change_request_cannot_change_password_twice(app, client):
    with app.app_context():
        make_user("member6", User.ROLE_MEMBER)
    token = login(client, "member6").get_json()["data"]["token"]
    assert change(client, token).status_code == 200
    replay = change(client, token, new="Another#Secret2026")
    assert replay.status_code == 401  # old token revoked by the first change
    assert login(client, "member6", NEW_PW).status_code == 200


def test_legacy_first_login_endpoint_used_by_old_app_versions(app, client):
    """Already-installed APKs call /research/auth/first-login-password and keep their token."""
    with app.app_context():
        make_user("oldapp", User.ROLE_MEMBER)
    token = login(client, "oldapp").get_json()["data"]["token"]
    other = login(client, "oldapp").get_json()["data"]["token"]
    weak = client.post("/api/v1/research/auth/first-login-password", headers=bearer(token),
                       json={"current_password": OLD_PW, "new_password": "abc123"})
    assert weak.status_code == 400  # same policy as the new endpoint
    r = client.post("/api/v1/research/auth/first-login-password", headers=bearer(token),
                    json={"current_password": OLD_PW, "new_password": NEW_PW})
    assert r.status_code == 200
    assert r.get_json()["data"]["user"]["must_change_password"] is False
    assert client.get("/api/v1/teams", headers=bearer(token)).status_code == 200  # same token, now unrestricted
    assert client.get("/api/v1/auth/me", headers=bearer(other)).status_code == 401  # other devices signed out


# --------------------------------------------------------------------------- new accounts

def test_admin_created_member_must_change_password(client, admin_user, seed_teams):
    payload = {
        "full_name": "New Volunteer", "registration_number": "REG-NEW-1", "class_name": "1st Year",
        "phone_number": "+919876500001", "team_id": seed_teams["volunteering"].id,
        "username": "new_vol", "email": "new_vol@test.edu", "password": "TempGiven#2026", "role": "member",
    }
    assert client.post("/api/v1/members/account", headers=admin_user["headers"], json=payload).status_code == 201
    data = login(client, "new_vol", "TempGiven#2026").get_json()["data"]
    assert data["password_change_required"] is True


def test_admin_reset_password_requires_change(client, app, admin_user, seed_teams):
    payload = {
        "full_name": "Reset Me", "registration_number": "REG-NEW-2", "class_name": "1st Year",
        "phone_number": "+919876500002", "team_id": seed_teams["volunteering"].id,
        "username": "reset_me", "email": "reset_me@test.edu", "password": "TempGiven#2026", "role": "member",
    }
    member_id = client.post("/api/v1/members/account", headers=admin_user["headers"], json=payload).get_json()["data"]["member"]["id"]
    token = login(client, "reset_me", "TempGiven#2026").get_json()["data"]["token"]
    token = change(client, token, current="TempGiven#2026").get_json()["data"]["token"]
    assert client.get("/api/v1/teams", headers=bearer(token)).status_code == 200
    client.post(f"/api/v1/members/{member_id}/reset-password", headers=admin_user["headers"],
                json={"new_password": "AdminReset#2026"})
    data = login(client, "reset_me", "AdminReset#2026").get_json()["data"]
    assert data["password_change_required"] is True


def test_self_chosen_password_via_setup_token_is_not_forced_again(app, client):
    from app.services.auth_service import AuthService
    with app.app_context():
        u = make_user("invited", User.ROLE_MEMBER, required=True)
        _, raw = AuthService.create_setup_token(u.id)
    r = client.post("/api/v1/auth/setup-password", json={"token": raw, "new_password": NEW_PW})
    assert r.status_code == 200
    assert r.get_json()["data"]["user"]["password_change_required"] is False
    assert client.get("/api/v1/teams", headers=bearer(r.get_json()["data"]["token"])).status_code == 200


# --------------------------------------------------------------------------- bulk operation

def test_bulk_command_preview_apply_rerun_and_revert(app):
    with app.app_context():
        make_user("a", User.ROLE_ADMIN, required=False)
        make_user("p", User.ROLE_PRESIDENT, required=False)
        make_user("t", User.ROLE_TEAM_LEADER, required=False)
        make_user("v", User.ROLE_MEMBER, required=False)
        make_user("gone", User.ROLE_MEMBER, required=False, active=False)
        done = make_user("done", User.ROLE_MEMBER, required=False)
        from app.utils.datetime_utils import utc_now
        done.password_changed_at = utc_now()  # already completed the reset
        db.session.commit()
        hashes_before = {u.username: u.password_hash for u in User.query.all()}

    runner = app.test_cli_runner()
    preview = runner.invoke(args=["require-password-change"])
    assert preview.exit_code == 0
    assert "would be flagged: 4" in preview.output and "Dry run only" in preview.output
    with app.app_context():
        assert User.query.filter_by(password_change_required=True).count() == 0  # dry run changed nothing

    applied = runner.invoke(args=["require-password-change", "--confirm"])
    assert "4 accounts flagged" in applied.output
    with app.app_context():
        flagged = {u.username for u in User.query.filter_by(password_change_required=True)}
        assert flagged == {"p", "t", "v", "gone"}
        assert {u.username: u.password_hash for u in User.query.all()} == hashes_before  # passwords untouched

    rerun = runner.invoke(args=["require-password-change", "--confirm"])
    assert "would be flagged: 0" in rerun.output

    reverted = runner.invoke(args=["require-password-change", "--revert", "--confirm"])
    assert "4 accounts cleared" in reverted.output
    with app.app_context():
        assert User.query.filter_by(password_change_required=True).count() == 0


# --------------------------------------------------------------------------- concurrency (PostgreSQL)

@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="set TEST_POSTGRES_URL to run against PostgreSQL")
def test_concurrent_password_changes_are_serialised_on_postgres():
    """Several simultaneous change requests: exactly one succeeds, the rest fail cleanly."""
    from app import create_app
    from app.config import TestingConfig

    class PgConfig(TestingConfig):
        SQLALCHEMY_DATABASE_URI = os.environ["TEST_POSTGRES_URL"]
        SQLALCHEMY_ENGINE_OPTIONS = {"pool_size": 10}

    from app import config as config_module
    config_module.config_by_name["pgtest"] = PgConfig
    pg_app = create_app("pgtest")
    with pg_app.app_context():
        db.drop_all()
        db.create_all()
        make_user("racer", User.ROLE_MEMBER)
        db.session.remove()
    c = pg_app.test_client()
    tokens = [login(c, "racer").get_json()["data"]["token"] for _ in range(6)]
    results = []
    barrier = threading.Barrier(len(tokens))

    def worker(i, tok):
        cl = pg_app.test_client()
        barrier.wait()
        r = change(cl, tok, new=f"Swift#{i}Secret2026", confirm=f"Swift#{i}Secret2026")
        results.append((i, r.status_code))

    threads = [threading.Thread(target=worker, args=(i, t)) for i, t in enumerate(tokens)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    ok = [i for i, s in results if s == 200]
    assert len(ok) == 1, results
    assert all(s in (400, 401) for i, s in results if i not in ok), results
    with pg_app.app_context():
        u = User.query.filter_by(username="racer").one()
        assert u.check_password(f"Swift#{ok[0]}Secret2026")
        assert not u.password_change_required
        live = ApiToken.query.filter_by(user_id=u.id, is_revoked=False).count()
        assert live == 1  # only the session issued by the winning request
        db.session.remove()  # release the read transaction before dropping tables
        db.drop_all()
