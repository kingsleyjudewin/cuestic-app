import pytest
from app.extensions import db
from app.models.user import User
from app.models.team import Team
from app.models.member import Member
from app.services.documentation_import_service import (
    DocumentationImportService,
    DEFAULT_DOCUMENTATION_RECORDS,
)
from app.services.member_service import MemberService
from app.utils.errors import PermissionDeniedError, NotFoundError, ConflictError
from tests.conftest import create_user_with_token


def test_documentation_team_lookup(app, seed_teams):
    """Verify that DocumentationImportService retrieves the existing Documentation team without duplicating."""
    with app.app_context():
        initial_team_count = Team.query.count()
        doc_team = DocumentationImportService.get_documentation_team()
        assert doc_team is not None
        assert doc_team.name == "Documentation"
        assert doc_team.slug == "documentation"
        # Verify no duplicate team was created
        assert Team.query.count() == initial_team_count


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

        preview = DocumentationImportService.inspect_and_preview(operator_identifier="test_admin")
        assert preview["total_records"] == 5
        assert preview["ready_count"] == 5
        assert preview["duplicate_count"] == 0
        assert Member.query.count() == initial_member_count

        result = DocumentationImportService.execute_import(
            operator_identifier="test_admin",
            dry_run=True,
            confirm=False,
        )
        assert result["dry_run"] is True
        assert len(result["created"]) == 0
        assert Member.query.count() == initial_member_count


def test_import_documentation_members_success(app, admin_user, seed_teams):
    """Verify that all five documentation members are created with accurate phone, class, and team."""
    with app.app_context():
        doc_team = seed_teams["documentation"]
        initial_user_count = User.query.count()

        result = DocumentationImportService.execute_import(
            operator_identifier="test_admin",
            dry_run=False,
            confirm=True,
        )

        assert result["success"] is True
        assert len(result["created"]) == 5
        assert len(result["skipped"]) == 0
        assert len(result["failed"]) == 0

        # Verify no new User accounts or login passwords were created (Requirement 8)
        assert User.query.count() == initial_user_count

        # Check each member in database
        members = Member.query.filter_by(team_id=doc_team.id).all()
        assert len(members) == 5

        members_by_name = {m.full_name: m for m in members}
        assert set(members_by_name.keys()) == {"Surasmita", "Salomi", "Kavin", "Manyatha", "Pooja"}

        # 1. Surasmita
        surasmita = members_by_name["Surasmita"]
        assert surasmita.phone_number == "+918078156512"
        assert surasmita.country_code == "+91"
        assert surasmita.class_name == "6BTELCS"
        assert surasmita.linked_user_id is None
        assert surasmita.is_active is True

        # 2. Salomi
        salomi = members_by_name["Salomi"]
        assert salomi.phone_number == "+918592088048"
        assert salomi.country_code == "+91"
        assert salomi.class_name == "6BTEC"
        assert salomi.linked_user_id is None

        # 3. Kavin
        kavin = members_by_name["Kavin"]
        assert kavin.phone_number == "+916379338335"
        assert kavin.country_code == "+91"
        assert kavin.class_name == "4BTEC"
        assert kavin.linked_user_id is None

        # 4. Manyatha
        manyatha = members_by_name["Manyatha"]
        assert manyatha.phone_number == "+916302212235"
        assert manyatha.country_code == "+91"
        assert manyatha.class_name == "4BTEC"
        assert manyatha.linked_user_id is None

        # 5. Pooja
        pooja = members_by_name["Pooja"]
        assert pooja.phone_number == "+918217806896"
        assert pooja.country_code == "+91"
        assert pooja.class_name == "4BTEC"
        assert pooja.linked_user_id is None


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

        # Total documentation members in DB should remain exactly 5
        doc_team = seed_teams["documentation"]
        assert Member.query.filter_by(team_id=doc_team.id).count() == 5


def test_existing_volunteers_and_other_teams_unaffected(app, admin_user, seed_teams, seed_members):
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
    assert "0 records written to database" in res_dry.output

    # 2. Confirm execution
    res_exec = runner.invoke(args=["import-documentation-members", "--confirm", "--operator", "test_admin"])
    assert res_exec.exit_code == 0
    assert "EXECUTION SUMMARY" in res_exec.output
    assert "5 created, 0 skipped, 0 failed" in res_exec.output
    assert "Surasmita" in res_exec.output
    assert "Salomi" in res_exec.output
    assert "Kavin" in res_exec.output
    assert "Manyatha" in res_exec.output
    assert "Pooja" in res_exec.output

    # 3. Re-run confirm (idempotent)
    res_repeat = runner.invoke(args=["import-documentation-members", "--confirm", "--operator", "test_admin"])
    assert res_repeat.exit_code == 0
    assert "0 created, 5 skipped, 0 failed" in res_repeat.output
