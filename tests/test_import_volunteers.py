import pytest
from app.extensions import db
from app.models.user import User
from app.models.team import Team
from app.models.member import Member
from app.services.volunteer_import_service import (
    VolunteerImportService,
    normalize_name_for_identifier,
    generate_proposed_email,
    generate_temporary_password,
    DEFAULT_VOLUNTEER_RECORDS,
)
from app.services.member_service import MemberService
from app.cli import import_volunteers_command


def test_name_and_identifier_generation():
    """Verify name normalization, proposed email, and temporary password generation."""
    cases = [
        ("Devananda Ajith", "devananda.ajith", "devananda.ajith@gmail.com", "devananda.ajith@123"),
        ("Jayani CU", "jayani.cu", "jayani.cu@gmail.com", "jayani.cu@123"),
        ("Pranavi Cuestic", "pranavi.cuestic", "pranavi.cuestic@gmail.com", "pranavi.cuestic@123"),
        ("Sagar CU", "sagar.cu", "sagar.cu@gmail.com", "sagar.cu@123"),
        ("Kanishk", "kanishk", "kanishk@gmail.com", "kanishk@123"),
        ("Sanjai", "sanjai", "sanjai@gmail.com", "sanjai@123"),
        ("Shohil Mathew", "shohil.mathew", "shohil.mathew@gmail.com", "shohil.mathew@123"),
        ("  Leading and Trailing  ", "leading.and.trailing", "leading.and.trailing@gmail.com", "leading.and.trailing@123"),
        ("Special!#$ Characters", "special.characters", "special.characters@gmail.com", "special.characters@123"),
    ]

    for raw, expected_user, expected_email, expected_pwd in cases:
        norm = normalize_name_for_identifier(raw)
        email = generate_proposed_email(norm)
        pwd = generate_temporary_password(norm)

        assert norm == expected_user, f"Failed for {raw}: got {norm}"
        assert email == expected_email, f"Failed for {raw}: got {email}"
        assert pwd == expected_pwd, f"Failed for {raw}: got {pwd}"


def test_preview_and_dry_run_does_not_modify_db(app, admin_user, seed_teams):
    """Dry run inspects records, reports status, and writes zero records to database."""
    preview = VolunteerImportService.inspect_and_preview(
        operator_identifier=admin_user["user"].username
    )

    assert preview["total_records"] == 7
    assert preview["ready_count"] == 5
    assert preview["ambiguous_count"] == 2
    assert preview["team"]["name"] == "Volunteering"
    assert preview["team"]["id"] == seed_teams["volunteering"].id

    # Dry-run execution
    dry_res = VolunteerImportService.execute_import(
        operator_identifier=admin_user["user"].username,
        dry_run=True,
        confirm=False,
    )
    assert dry_res["dry_run"] is True
    assert dry_res["confirmed"] is False
    assert len(dry_res["created"]) == 0

    # Verify no members or users were created
    new_users = User.query.filter(User.username.in_([r["username"] for r in preview["prepared_payloads"]])).all()
    assert len(new_users) == 0


def test_import_volunteers_creates_accounts_safely(app, admin_user, seed_teams):
    """
    President-authorized import creates all 7 accounts, assigns to Volunteering team,
    hashes passwords, and assigns strictly volunteer role.
    """
    vol_team = seed_teams["volunteering"]

    result = VolunteerImportService.execute_import(
        operator_identifier=admin_user["user"].username,
        dry_run=False,
        confirm=True,
        skip_ambiguous=False,
    )

    assert result["dry_run"] is False
    assert result["confirmed"] is True
    assert result["success"] is True
    assert len(result["created"]) == 7
    assert len(result["skipped"]) == 0
    assert len(result["failed"]) == 0

    # Verify each volunteer in database
    for rec in DEFAULT_VOLUNTEER_RECORDS:
        username = normalize_name_for_identifier(rec["full_name"])
        expected_pwd = generate_temporary_password(username)

        # 1. User checks
        user = User.query.filter_by(username=username).first()
        assert user is not None, f"User {username} not found"
        assert user.email == f"{username}@gmail.com"
        assert user.role == User.ROLE_MEMBER  # Volunteer role only, never elevated
        assert user.is_active is True
        # Password must be securely hashed, not plaintext
        assert user.password_hash != expected_pwd
        assert user.check_password(expected_pwd) is True

        # 2. Member checks
        member = user.linked_member
        assert member is not None, f"Member link missing for {username}"
        assert member.full_name == rec["full_name"]
        assert member.team_id == vol_team.id
        assert member.is_active is True
        assert member.whatsapp_opt_in is True
        assert member.country_code == "+91"
        assert member.phone_number.startswith("+91")
        assert member.class_name == rec["class_section"]


def test_import_idempotency_does_not_duplicate(app, admin_user, seed_teams):
    """Rerunning import must be completely idempotent and not create duplicate accounts."""
    # First run
    res1 = VolunteerImportService.execute_import(
        operator_identifier=admin_user["user"].username,
        dry_run=False,
        confirm=True,
    )
    assert len(res1["created"]) == 7

    # Count records before second run
    user_count_before = User.query.count()
    member_count_before = Member.query.count()

    # Second run
    res2 = VolunteerImportService.execute_import(
        operator_identifier=admin_user["user"].username,
        dry_run=False,
        confirm=True,
    )
    assert len(res2["created"]) == 0
    assert len(res2["skipped"]) == 7
    assert len(res2["failed"]) == 0

    # Verify no records were added
    assert User.query.count() == user_count_before
    assert Member.query.count() == member_count_before


def test_operator_authorization_enforced(app, member_user, seed_teams):
    """Non-president operator is strictly rejected from authorizing volunteer import."""
    with pytest.raises(Exception) as exc:
        VolunteerImportService.execute_import(
            operator_identifier=member_user["user"].username,
            dry_run=False,
            confirm=True,
        )
    assert "Only President/Admin" in str(exc.value) or "authorization" in str(exc.value).lower()


def test_skip_ambiguous_flag_works(app, admin_user, seed_teams):
    """When skip_ambiguous=True, records with ambiguity (e.g. Kanishk) are skipped."""
    result = VolunteerImportService.execute_import(
        operator_identifier=admin_user["user"].username,
        dry_run=False,
        confirm=True,
        skip_ambiguous=True,
    )

    assert result["success"] is True
    # Kanishk is flagged is_ambiguous=True in DEFAULT_VOLUNTEER_RECORDS
    assert len(result["created"]) == 6
    assert len(result["skipped"]) == 1
    assert result["skipped"][0]["name"] == "Kanishk"

    # Verify Kanishk was not created
    kanishk_user = User.query.filter_by(username="kanishk").first()
    assert kanishk_user is None


def test_volunteer_login_and_password_change_flow(client, admin_user, seed_teams):
    """
    Imported volunteer can log in with temporary password and change password securely.
    """
    # 1. Run import
    VolunteerImportService.execute_import(
        operator_identifier=admin_user["user"].username,
        dry_run=False,
        confirm=True,
    )

    # 2. Volunteer logs in using username + temp password
    login_res = client.post("/api/v1/auth/login", json={
        "username": "devananda.ajith",
        "password": "devananda.ajith@123",
    })
    assert login_res.status_code == 200
    login_data = login_res.get_json()["data"]
    token = login_data["token"]
    assert login_data["user"]["role"] == "member"
    assert "password_hash" not in login_data["user"]

    # Also verify login works using proposed placeholder email
    login_email_res = client.post("/api/v1/auth/login", json={
        "username": "devananda.ajith@gmail.com",
        "password": "devananda.ajith@123",
    })
    assert login_email_res.status_code == 200

    # 3. Volunteer cannot create member accounts (forbidden)
    forbidden_res = client.post("/api/v1/members/account", headers={"Authorization": f"Bearer {token}"}, json={
        "full_name": "Unauthorized Add",
        "class_name": "1st Year",
        "phone_number": "+919999900001",
        "team_id": seed_teams["volunteering"].id,
        "username": "unauth_add",
        "password": "Password123!",
    })
    assert forbidden_res.status_code == 403

    # 4. Volunteer changes password via self-service endpoint
    change_res = client.post("/api/v1/auth/change-password", headers={"Authorization": f"Bearer {token}"}, json={
        "current_password": "devananda.ajith@123",
        "new_password": "MyNewSecurePersonalPassword2026!",
    })
    assert change_res.status_code == 200
    assert change_res.get_json()["success"] is True

    # 5. Old temporary password fails
    old_login = client.post("/api/v1/auth/login", json={
        "username": "devananda.ajith",
        "password": "devananda.ajith@123",
    })
    assert old_login.status_code == 401

    # 6. New password succeeds
    new_login = client.post("/api/v1/auth/login", json={
        "username": "devananda.ajith",
        "password": "MyNewSecurePersonalPassword2026!",
    })
    assert new_login.status_code == 200


def test_flask_cli_runner(app, admin_user, seed_teams):
    """Test Flask CLI command integration via test_cli_runner."""
    runner = app.test_cli_runner()

    # Dry-run via CLI
    res_dry = runner.invoke(import_volunteers_command, ["--dry-run", "--operator", admin_user["user"].username])
    assert res_dry.exit_code == 0
    assert "DRY RUN — PREVIEW ONLY" in res_dry.output
    assert "devananda.ajith" in res_dry.output
    assert "0 accounts written to database" in res_dry.output

    # Confirm via CLI
    res_confirm = runner.invoke(import_volunteers_command, ["--confirm", "--operator", admin_user["user"].username])
    assert res_confirm.exit_code == 0
    assert "LIVE IMPORT EXECUTED" in res_confirm.output
    assert "7 created, 0 skipped, 0 failed" in res_confirm.output

    # Repeat via CLI (idempotency check)
    res_repeat = runner.invoke(import_volunteers_command, ["--confirm", "--operator", admin_user["user"].username])
    assert res_repeat.exit_code == 0
    assert "0 created, 7 skipped, 0 failed" in res_repeat.output
