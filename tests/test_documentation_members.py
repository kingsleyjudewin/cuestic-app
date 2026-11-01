import pytest
from app.extensions import db
from app.models.user import User, PasswordSetupToken
from app.models.team import Team
from app.models.member import Member
from app.services.documentation_import_service import (
    DocumentationImportService,
    DEFAULT_DOCUMENTATION_RECORDS,
    normalize_name_for_identifier,
    generate_proposed_email,
)
from app.utils.errors import PermissionDeniedError, NotFoundError


def test_documentation_team_lookup(app, seed_teams):
    """Verify that DocumentationImportService retrieves the existing Documentation team without duplicating."""
    with app.app_context():
        initial_team_count = Team.query.count()
        doc_team = DocumentationImportService.get_documentation_team()
        assert doc_team is not None
        assert doc_team.name == "Documentation"
        assert doc_team.slug == "documentation"
        assert Team.query.count() == initial_team_count


def test_identifier_and_email_generation():
    """Verify identifier normalization and email generation for all 5 documentation members."""
    expected = [
        ("John Victor", "john.victor", "john.victor@gmail.com"),
        ("Merrick", "merrick", "merrick@gmail.com"),
        ("Abishek Cu", "abishek.cu", "abishek.cu@gmail.com"),
        ("Afra", "afra", "afra@gmail.com"),
        ("Prarthana Venkatesh", "prarthana.venkatesh", "prarthana.venkatesh@gmail.com"),
    ]
    for full_name, expected_uname, expected_email in expected:
        uname = normalize_name_for_identifier(full_name)
        assert uname == expected_uname
        assert generate_proposed_email(uname) == expected_email


def test_operator_authorization_enforced(app, admin_user, member_user):
    """Verify that only President/Admin can authorize importing documentation members."""
    with app.app_context():
        # President should succeed
        op = DocumentationImportService.verify_operator("test_admin")
        assert op.username == "test_admin"

        # Ordinary member should fail
        with pytest.raises(PermissionDeniedError):
            DocumentationImportService.verify_operator("test_member")

        # Non-existent operator should fail
        with pytest.raises(NotFoundError):
            DocumentationImportService.verify_operator("non_existent_operator")


def test_preview_and_dry_run_does_not_modify_db(app, admin_user, seed_teams):
    """Verify preview and dry-run do not write records to the database."""
    with app.app_context():
        initial_member_count = Member.query.count()
        initial_user_count = User.query.count()

        preview = DocumentationImportService.inspect_and_preview(operator_identifier="test_admin")
        assert preview["total_records"] == 5
        assert preview["ready_count"] == 5
        assert preview["duplicate_count"] == 0
        assert Member.query.count() == initial_member_count
        assert User.query.count() == initial_user_count

        result = DocumentationImportService.execute_import(
            operator_identifier="test_admin",
            dry_run=True,
            confirm=False,
        )
        assert result["dry_run"] is True
        assert len(result["created"]) == 0
        assert Member.query.count() == initial_member_count
        assert User.query.count() == initial_user_count


def test_import_documentation_members_success(app, admin_user, seed_teams):
    """Verify that all five documentation members and their accounts are created accurately."""
    with app.app_context():
        doc_team = seed_teams["documentation"]
        initial_user_count = User.query.count()
        initial_member_count = Member.query.filter_by(team_id=doc_team.id).count()

        result = DocumentationImportService.execute_import(
            operator_identifier="test_admin",
            dry_run=False,
            confirm=True,
        )

        assert result["success"] is True
        assert len(result["created"]) == 5
        assert len(result["skipped"]) == 0
        assert len(result["failed"]) == 0

        # Verify 5 new User accounts created with 'member' role (no admin escalation)
        assert User.query.count() == initial_user_count + 5

        # Check all 5 members exist in Documentation team
        members = Member.query.filter_by(team_id=doc_team.id).all()
        assert len(members) == initial_member_count + 5

        members_by_name = {m.full_name: m for m in members}
        assert "John Victor" in members_by_name
        assert "Merrick" in members_by_name
        assert "Abishek Cu" in members_by_name
        assert "Afra" in members_by_name
        assert "Prarthana Venkatesh" in members_by_name

        # Verify details of each member and user account
        expected_records = {
            "John Victor": ("+919986383984", "john.victor", "john.victor@gmail.com"),
            "Merrick": ("+919022469808", "merrick", "merrick@gmail.com"),
            "Abishek Cu": ("+917338796125", "abishek.cu", "abishek.cu@gmail.com"),
            "Afra": ("+919845314703", "afra", "afra@gmail.com"),
            "Prarthana Venkatesh": ("+919964697363", "prarthana.venkatesh", "prarthana.venkatesh@gmail.com"),
        }

        for name, (phone, uname, email) in expected_records.items():
            m = members_by_name[name]
            assert m.phone_number == phone
            assert m.country_code == "+91"
            assert m.class_name is None  # Not provided, remains nullable
            assert m.team_id == doc_team.id
            assert m.is_active is True
            assert m.linked_user_id is not None

            # Verify associated User account
            user = db.session.get(User, m.linked_user_id)
            assert user is not None
            assert user.username == uname
            assert user.email == email
            assert user.role == User.ROLE_MEMBER
            assert user.is_admin() is False
            assert user.credential_setup_status == "pending"
            assert user.password_hash is not None
            # Verify single-use setup token generated
            token = PasswordSetupToken.query.filter_by(user_id=user.id, is_used=False).first()
            assert token is not None


def test_import_idempotency_does_not_duplicate(app, admin_user, seed_teams):
    """Verify that re-running the import skips existing records as duplicates without error."""
    with app.app_context():
        # First import
        result1 = DocumentationImportService.execute_import(
            operator_identifier="test_admin",
            dry_run=False,
            confirm=True,
        )
        assert len(result1["created"]) == 5
        assert len(result1["skipped"]) == 0

        # Second import (idempotent run)
        result2 = DocumentationImportService.execute_import(
            operator_identifier="test_admin",
            dry_run=False,
            confirm=True,
        )
        assert len(result2["created"]) == 0
        assert len(result2["skipped"]) == 5
        assert len(result2["failed"]) == 0


def test_existing_teams_unaffected(app, admin_user, seed_teams, seed_members):
    """Verify existing members in other teams (e.g. Volunteering) remain completely unchanged."""
    with app.app_context():
        vol_team = seed_teams["volunteering"]
        initial_vol_count = Member.query.filter_by(team_id=vol_team.id).count()

        DocumentationImportService.execute_import(
            operator_identifier="test_admin",
            dry_run=False,
            confirm=True,
        )

        # Volunteering team member count unchanged
        assert Member.query.filter_by(team_id=vol_team.id).count() == initial_vol_count


def test_flask_cli_runner(app, admin_user, seed_teams):
    """Test flask import-documentation-members CLI command."""
    runner = app.test_cli_runner()
    # 1. Dry run
    res_dry = runner.invoke(args=["import-documentation-members", "--operator", "test_admin"])
    assert res_dry.exit_code == 0
    assert "DRY RUN SUMMARY" in res_dry.output
    assert "0 accounts written to database" in res_dry.output

    # 2. Confirm execution
    res_exec = runner.invoke(args=["import-documentation-members", "--confirm", "--operator", "test_admin"])
    assert res_exec.exit_code == 0
    assert "EXECUTION SUMMARY" in res_exec.output
    assert "5 created, 0 skipped, 0 failed" in res_exec.output
    assert "John Victor" in res_exec.output
    assert "Merrick" in res_exec.output
    assert "Abishek Cu" in res_exec.output
    assert "Afra" in res_exec.output
    assert "Prarthana Venkatesh" in res_exec.output

    # 3. Re-run confirm (idempotent)
    res_repeat = runner.invoke(args=["import-documentation-members", "--confirm", "--operator", "test_admin"])
    assert res_repeat.exit_code == 0
    assert "0 created, 5 skipped, 0 failed" in res_repeat.output
