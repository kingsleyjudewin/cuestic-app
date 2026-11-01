import pytest
from datetime import timedelta
from app.extensions import db
from app.models.user import User, PasswordSetupToken
from app.models.team import Team
from app.models.member import Member
from app.services.media_import_service import (
    MediaImportService,
    DEFAULT_MEDIA_RECORDS,
    normalize_name_for_identifier,
    generate_proposed_email,
)
from app.utils.errors import PermissionDeniedError, NotFoundError, ValidationError
from app.utils.datetime_utils import utc_now
from app.cli import import_media_members_command


def test_name_and_identifier_normalization():
    """Verify deterministic normalization for usernames and proposed emails."""
    expected_mappings = [
        ("Arpitha CU", "arpitha.cu", "arpitha.cu@gmail.com"),
        ("Nivin CU", "nivin.cu", "nivin.cu@gmail.com"),
        ("Aleena Cuestic", "aleena.cuestic", "aleena.cuestic@gmail.com"),
        ("Amilthini", "amilthini", "amilthini@gmail.com"),
        ("Priyal Poovamma", "priyal.poovamma", "priyal.poovamma@gmail.com"),
        ("Abijith", "abijith", "abijith@gmail.com"),
        ("George Sebastian", "george.sebastian", "george.sebastian@gmail.com"),
        ("Rehan", "rehan", "rehan@gmail.com"),
        ("Vishnu Karunakaran", "vishnu.karunakaran", "vishnu.karunakaran@gmail.com"),
        ("Srishti", "srishti", "srishti@gmail.com"),
    ]

    for name, exp_username, exp_email in expected_mappings:
        u = normalize_name_for_identifier(name)
        e = generate_proposed_email(u)
        assert u == exp_username, f"Failed for {name}: got {u}, expected {exp_username}"
        assert e == exp_email, f"Failed email for {name}: got {e}, expected {exp_email}"


def test_media_team_lookup(app, seed_teams):
    """Verify MediaImportService reuses existing Media team without creating duplicates."""
    with app.app_context():
        initial_team_count = Team.query.count()
        media_team = MediaImportService.get_media_team()
        assert media_team is not None
        assert media_team.name == "Media"
        assert media_team.slug == "media"
        # No extra or separate design team was created
        assert Team.query.count() == initial_team_count


def test_operator_authorization_enforced(app, admin_user, member_user):
    """Verify that only President or Administrator can authorize Media account imports."""
    with app.app_context():
        # President should pass
        op = MediaImportService.verify_operator("test_admin")
        assert op.username == "test_admin"

        # Regular member should be rejected
        with pytest.raises(PermissionDeniedError):
            MediaImportService.verify_operator("test_member")

        # Non-existent user should be rejected
        with pytest.raises(NotFoundError):
            MediaImportService.verify_operator("non_existent_user")


def test_preview_and_dry_run_does_not_modify_db(app, admin_user, seed_teams):
    """Verify dry run inspects records without committing any accounts to the database."""
    with app.app_context():
        initial_member_count = Member.query.count()
        initial_user_count = User.query.count()

        preview = MediaImportService.inspect_and_preview(operator_identifier="test_admin")
        assert preview["total_records"] == 10
        assert preview["ready_count"] == 10
        assert preview["duplicate_count"] == 0
        assert preview["invalid_count"] == 0

        # Execute in dry run
        result = MediaImportService.execute_import(
            operator_identifier="test_admin",
            dry_run=True,
            confirm=False,
        )
        assert result["dry_run"] is True
        assert len(result["created"]) == 0
        assert Member.query.count() == initial_member_count
        assert User.query.count() == initial_user_count


def test_live_import_creates_media_accounts_safely(app, client, admin_user, seed_teams):
    """
    Verify live import creates all 10 Media team members and user accounts
    with single-use setup tokens and secure status.
    """
    with app.app_context():
        initial_doc_count = Member.query.filter_by(team_id=seed_teams["documentation"].id).count()
        initial_vol_count = Member.query.filter_by(team_id=seed_teams["volunteering"].id).count()

        result = MediaImportService.execute_import(
            operator_identifier="test_admin",
            dry_run=False,
            confirm=True,
        )

        assert result["dry_run"] is False
        assert result["confirmed"] is True
        assert result["success"] is True
        assert len(result["created"]) == 10
        assert len(result["skipped"]) == 0
        assert len(result["failed"]) == 0

        media_team = seed_teams["media"]

        # Verify all 10 members in database
        for created in result["created"]:
            member = db.session.get(Member, created["member_id"])
            user = db.session.get(User, created["user_id"])

            assert member is not None
            assert user is not None
            assert member.team_id == media_team.id
            assert member.linked_user_id == user.id
            assert user.role == User.ROLE_MEMBER
            assert user.is_active is True
            assert user.credential_setup_status == "pending"

            # Check phone number E.164 formatting
            assert member.phone_number.startswith("+91")
            assert " " not in member.phone_number

            # Check that password is NOT plaintext or default name@123
            assert user.password_hash is not None
            assert user.password_hash != f"{user.username}@123"
            assert user.check_password(f"{user.username}@123") is False

            # Verify setup token was generated
            raw_token = created["setup_token"]
            assert raw_token is not None
            token_hash = PasswordSetupToken.hash_token(raw_token)
            token_record = PasswordSetupToken.query.filter_by(token_hash=token_hash).first()
            assert token_record is not None
            assert token_record.user_id == user.id
            assert token_record.is_used is False
            assert token_record.is_valid() is True

        # Verify existing Documentation and Volunteering members remain unaffected
        assert Member.query.filter_by(team_id=seed_teams["documentation"].id).count() == initial_doc_count
        assert Member.query.filter_by(team_id=seed_teams["volunteering"].id).count() == initial_vol_count

        # Test setup-password workflow for the first member
        first_created = result["created"][0]
        raw_setup_token = first_created["setup_token"]
        first_username = first_created["username"]

        # 1. Verify setup token endpoint
        verify_res = client.get(f"/api/v1/auth/verify-setup-token?token={raw_setup_token}")
        assert verify_res.status_code == 200
        assert verify_res.get_json()["data"]["username"] == first_username

        # 2. Establish custom password
        setup_res = client.post("/api/v1/auth/setup-password", json={
            "token": raw_setup_token,
            "new_password": "MySuperSecretPass2026!",
        })
        assert setup_res.status_code == 200
        setup_data = setup_res.get_json()["data"]
        assert "token" in setup_data
        assert setup_data["user"]["credential_setup_status"] == "completed"

        # 3. Setup token cannot be consumed a second time
        repeat_res = client.post("/api/v1/auth/setup-password", json={
            "token": raw_setup_token,
            "new_password": "AnotherPassword123!",
        })
        assert repeat_res.status_code == 400

        # 4. Member can log in with new password
        login_res = client.post("/api/v1/auth/login", json={
            "username": first_username,
            "password": "MySuperSecretPass2026!",
        })
        assert login_res.status_code == 200
        member_token = login_res.get_json()["data"]["token"]

        # 5. Verify member has member role and belongs to Media team
        me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {member_token}"})
        assert me_res.status_code == 200
        me_data = me_res.get_json()["data"]
        assert me_data["role"] == "member"
        assert me_data["team_name"] == "Media"
        assert me_data["credential_setup_status"] == "completed"

        # 6. Verify permission boundaries: Media member cannot create events or access admin endpoints
        evt_res = client.post("/api/v1/events", json={"name": "Unauthorized Event"}, headers={"Authorization": f"Bearer {member_token}"})
        assert evt_res.status_code == 403


def test_import_idempotency_does_not_duplicate(app, admin_user, seed_teams):
    """Verify running the import a second time safely skips already existing members."""
    with app.app_context():
        # First import
        res1 = MediaImportService.execute_import(
            operator_identifier="test_admin",
            dry_run=False,
            confirm=True,
        )
        assert len(res1["created"]) == 10

        count_after_first = Member.query.filter_by(team_id=seed_teams["media"].id).count()

        # Second import rerun
        res2 = MediaImportService.execute_import(
            operator_identifier="test_admin",
            dry_run=False,
            confirm=True,
        )
        assert len(res2["created"]) == 0
        assert len(res2["skipped"]) == 10
        assert len(res2["failed"]) == 0

        # Member count must not have changed
        count_after_second = Member.query.filter_by(team_id=seed_teams["media"].id).count()
        assert count_after_second == count_after_first


def test_setup_token_expiration(app, client, admin_user, seed_teams):
    """Verify expired setup tokens cannot be consumed."""
    with app.app_context():
        result = MediaImportService.execute_import(
            operator_identifier="test_admin",
            dry_run=False,
            confirm=True,
        )
        account = result["created"][0]
        raw_token = account["setup_token"]

        # Manually expire the token
        token_hash = PasswordSetupToken.hash_token(raw_token)
        token_record = PasswordSetupToken.query.filter_by(token_hash=token_hash).first()
        token_record.expires_at = utc_now() - timedelta(hours=1)
        db.session.commit()

        # Attempting to use expired token must fail
        setup_res = client.post("/api/v1/auth/setup-password", json={
            "token": raw_token,
            "new_password": "ExpiredTokenPassword123!",
        })
        assert setup_res.status_code == 400


def test_flask_cli_runner(app, runner, admin_user, seed_teams):
    """Verify flask CLI import-media-members command works properly."""
    # Test dry run
    result_dry = runner.invoke(
        import_media_members_command,
        ["--dry-run", "--operator", "test_admin"]
    )
    assert result_dry.exit_code == 0
    assert "DRY RUN" in result_dry.output
    assert "Arpitha CU" in result_dry.output
    assert "Srishti" in result_dry.output

    # Test JSON output dry run
    result_json = runner.invoke(
        import_media_members_command,
        ["--dry-run", "--json-output", "--operator", "test_admin"]
    )
    assert result_json.exit_code == 0
    assert '"mode": "dry_run"' in result_json.output
