import pytest
from datetime import timedelta
from app import create_app
from app.extensions import db
from app.models.user import User, ApiToken
from app.models.team import Team, slugify
from app.models.member import Member
from app.models.event import Event
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.utils.datetime_utils import utc_now


@pytest.fixture(scope="session")
def app():
    """Create test application using TestingConfig (in-memory SQLite)."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture(autouse=True)
def clean_db(app):
    """Clean all tables and in-memory caches between tests."""
    with app.app_context():
        from app.utils.permissions import invalidate_token_cache
        from app.api.members import invalidate_members_cache, invalidate_assignment_members_cache
        from app.api.teams import invalidate_teams_cache
        from app.services.documentation_service import DocumentationService
        invalidate_token_cache()
        invalidate_members_cache()
        invalidate_assignment_members_cache()
        invalidate_teams_cache()
        DocumentationService.invalidate_cache()
        db.session.remove()
        db.drop_all()
        db.create_all()
        yield
        invalidate_token_cache()
        invalidate_members_cache()
        invalidate_assignment_members_cache()
        invalidate_teams_cache()
        DocumentationService.invalidate_cache()
        db.session.rollback()
        db.session.remove()


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Flask test CLI runner."""
    return app.test_cli_runner()


def create_user_with_token(username: str, role: str, email: str = None) -> tuple[User, str]:
    """Helper to create user and active Bearer token."""
    user = User(
        username=username,
        email=email or f"{username}@test.edu",
        role=role,
        is_active=True,
    )
    user.set_password("Password123!")
    db.session.add(user)
    db.session.flush()

    expires_at = utc_now() + timedelta(days=30)
    token_obj, raw_token = ApiToken.create_token(
        user_id=user.id,
        expires_at=expires_at,
        name="Test Suite Token"
    )
    db.session.add(token_obj)
    db.session.commit()
    return user, raw_token


@pytest.fixture
def admin_user(app):
    """Fixture providing president/admin user and auth header."""
    user, token = create_user_with_token("test_admin", User.ROLE_PRESIDENT)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    return {"user": user, "token": token, "headers": headers}


@pytest.fixture
def team_leader_user(app, seed_teams):
    """Fixture providing team leader user and auth header."""
    user, token = create_user_with_token("test_leader", User.ROLE_TEAM_LEADER)
    # Assign leader to Volunteering team
    vol_team = seed_teams["volunteering"]
    vol_team.leader_user_id = user.id
    db.session.commit()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    return {"user": user, "token": token, "headers": headers, "team": vol_team}


@pytest.fixture
def member_user(app):
    """Fixture providing ordinary member user and auth header."""
    user, token = create_user_with_token("test_member", User.ROLE_MEMBER)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    return {"user": user, "token": token, "headers": headers}


@pytest.fixture
def seed_teams(app):
    """Fixture seeding standard teams."""
    t1 = Team(name="Volunteering", slug="volunteering", description="Volunteers team")
    t2 = Team(name="Documentation", slug="documentation", description="Docs team")
    t3 = Team(name="Media", slug="media", description="Media team")
    db.session.add_all([t1, t2, t3])
    db.session.commit()
    return {"volunteering": t1, "documentation": t2, "media": t3}


@pytest.fixture
def seed_members(app, seed_teams, member_user):
    """Fixture seeding sample active members."""
    m1 = Member(
        full_name="Ananya Sharma",
        registration_number="REG2026-001",
        class_name="3rd Year CSE",
        section="A",
        phone_number="+919876500001",
        country_code="+91",
        team_id=seed_teams["volunteering"].id,
        linked_user_id=member_user["user"].id,
        whatsapp_opt_in=True,
        is_active=True,
    )
    m2 = Member(
        full_name="Rohan Verma",
        registration_number="REG2026-002",
        class_name="3rd Year CSE",
        section="B",
        phone_number="+919876500002",
        country_code="+91",
        team_id=seed_teams["volunteering"].id,
        whatsapp_opt_in=True,
        is_active=True,
    )
    m3 = Member(
        full_name="Priya Patel",
        registration_number="REG2026-003",
        class_name="2nd Year ECE",
        section="A",
        phone_number="+919876500003",
        country_code="+91",
        team_id=seed_teams["documentation"].id,
        whatsapp_opt_in=False,  # opted out for testing
        is_active=True,
    )
    m4 = Member(
        full_name="Inactive Member",
        registration_number="REG2026-004",
        class_name="4th Year ME",
        section="A",
        phone_number="+919876500004",
        country_code="+91",
        team_id=seed_teams["media"].id,
        whatsapp_opt_in=True,
        is_active=False,  # inactive member for testing
    )
    db.session.add_all([m1, m2, m3, m4])
    db.session.commit()
    return {"m1": m1, "m2": m2, "m3": m3, "m4": m4}


@pytest.fixture
def sample_event(app, admin_user):
    """Fixture providing a sample event."""
    event = Event(
        name="MAGNOVITE 2026",
        description="Department Annual Symposium",
        start_at=utc_now() + timedelta(days=5),
        end_at=utc_now() + timedelta(days=7),
        location="Campus Auditorium",
        status=Event.STATUS_UPCOMING,
        created_by=admin_user["user"].id,
    )
    db.session.add(event)
    db.session.commit()
    return event
