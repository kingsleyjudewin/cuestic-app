"""Visitor (demo) account: explores the admin UI on an empty, read-only workspace."""
import re

import pytest

from app.extensions import db
from app.models.event import Event
from app.models.member import Member
from app.models.team import Team
from app.models.user import User
from tests.conftest import create_user_with_token

# Strings from the real (seeded) data that must never appear in a visitor response.
REAL_DATA_MARKERS = ("Ananya", "Rohan", "Priya", "MAGNOVITE", "REG2026", "test_admin", "test_member", "9876500")


@pytest.fixture
def visitor(app):
    user, token = create_user_with_token("visitor", User.ROLE_ADMIN)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    return {"user": user, "token": token, "headers": headers}


@pytest.fixture
def real_data(seed_members, sample_event, admin_user, client):
    # Warm the shared in-memory caches with real data, as a real admin would in production.
    for path in ("/api/v1/events", "/api/v1/members", "/api/v1/teams", "/api/v1/communities",
                 "/api/v1/mc/events", "/api/v1/documentation/folders", "/api/v1/documentation/reports"):
        client.get(path, headers=admin_user["headers"])
    # Production uses a fresh session per request; drop the test's shared identity map so the
    # visitor's queries really reach the database.
    db.session.remove()
    return {"admin": admin_user}


def _items(resp):
    data = resp.get_json()["data"]
    return data.get("items", data) if isinstance(data, dict) else data


def test_visitor_profile_looks_like_admin(client, visitor):
    resp = client.get("/api/v1/auth/me", headers=visitor["headers"])
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["role"] == "admin"
    assert data["is_visitor"] is True
    assert data["password_change_required"] is False


def test_real_admin_is_not_visitor(client, admin_user):
    data = client.get("/api/v1/auth/me", headers=admin_user["headers"]).get_json()["data"]
    assert data["is_visitor"] is False


def test_visitor_login_returns_visitor_flag(client, visitor):
    resp = client.post("/api/v1/auth/login", json={"username": "visitor", "password": "Password123!"})
    assert resp.status_code == 200
    assert resp.get_json()["data"]["user"]["is_visitor"] is True


def test_visitor_sees_empty_workspace(client, visitor, real_data):
    for path in ("/api/v1/events", "/api/v1/members", "/api/v1/mc/events", "/api/v1/communities"):
        resp = client.get(path, headers=visitor["headers"])
        assert resp.status_code == 200, (path, resp.get_json())
        assert _items(resp) == [], path

    # Team names are visible (screens look their team up), but nothing inside them is.
    teams = client.get("/api/v1/teams", headers=visitor["headers"])
    assert teams.status_code == 200
    for team in _items(teams):
        assert team.get("member_count", 0) == 0
        assert team.get("leader_name") is None

    dash = client.get("/api/v1/dashboard/summary", headers=visitor["headers"])
    assert dash.status_code == 200
    body = dash.get_data(as_text=True)
    assert not any(m in body for m in REAL_DATA_MARKERS)


def test_visitor_cannot_open_real_records(client, visitor, real_data, sample_event, seed_members):
    event_id = db.session.query(Event.id).scalar()
    member_id = db.session.query(Member.id).filter(Member.full_name == "Ananya Sharma").scalar()
    db.session.remove()
    assert client.get(f"/api/v1/events/{event_id}", headers=visitor["headers"]).status_code == 404
    assert client.get(f"/api/v1/members/{member_id}", headers=visitor["headers"]).status_code == 404


def test_visitor_writes_are_blocked_and_nothing_is_saved(client, visitor, real_data):
    before = (Event.query.count(), Team.query.count(), Member.query.count())
    db.session.remove()
    attempts = [
        ("post", "/api/v1/events", {"name": "Visitor Event", "start_at": "2030-01-01T10:00:00Z",
                                    "end_at": "2030-01-02T10:00:00Z"}),
        ("post", "/api/v1/teams", {"name": "Visitor Team"}),
        ("post", "/api/v1/members", {"full_name": "Visitor Member", "phone_number": "+919999999999"}),
        ("post", "/api/v1/auth/change-password", {"current_password": "Password123!",
                                                  "new_password": "AnotherPass123!",
                                                  "confirm_password": "AnotherPass123!"}),
        ("patch", "/api/v1/events/1", {"name": "Hijacked"}),
    ]
    for method, path, payload in attempts:
        resp = getattr(client, method)(path, json=payload, headers=visitor["headers"])
        assert resp.status_code == 403, (path, resp.get_json())
        assert resp.get_json()["error"]["code"] == "VISITOR_READ_ONLY"
    assert (Event.query.count(), Team.query.count(), Member.query.count()) == before


def test_visitor_does_not_poison_shared_caches(client, visitor, real_data):
    admin = real_data["admin"]
    for path in ("/api/v1/events", "/api/v1/members", "/api/v1/teams", "/api/v1/mc/events"):
        client.get(path, headers=visitor["headers"])
    db.session.remove()
    r = client.get("/api/v1/events", headers=admin["headers"])
    assert r.status_code == 200, r.get_json()
    assert len(_items(r)) == 1
    assert len(_items(client.get("/api/v1/members", headers=admin["headers"]))) >= 3
    assert len(_items(client.get("/api/v1/teams", headers=admin["headers"]))) == 3
    assert len(_items(client.get("/api/v1/mc/events", headers=admin["headers"]))) == 1


def test_visitor_can_log_out(client, visitor):
    resp = client.post("/api/v1/auth/logout", headers=visitor["headers"])
    assert resp.status_code == 200
    assert client.get("/api/v1/auth/me", headers=visitor["headers"]).status_code == 401


def test_every_get_endpoint_is_safe_for_visitor(app, client, visitor, real_data):
    """Crawl every GET route: no server errors and no real data in any response."""
    failures = []
    for rule in app.url_map.iter_rules():
        if "GET" not in rule.methods or not rule.rule.startswith("/api/v1/") or "docs" in rule.rule:
            continue
        path = re.sub(r"<(?:int:)?[^>]+>", "1", rule.rule)
        db.session.remove()
        resp = client.get(path, headers=visitor["headers"])
        body = resp.get_data(as_text=True)
        if resp.status_code >= 500:
            failures.append(f"{path}: HTTP {resp.status_code}")
        leaked = [m for m in REAL_DATA_MARKERS if m in body]
        if leaked:
            failures.append(f"{path}: leaked {leaked}")
    assert not failures, "\n".join(failures)


def test_create_visitor_cli(app, runner):
    result = runner.invoke(args=["create-visitor", "--password", "VisitorPass1!"])
    assert result.exit_code == 0, result.output
    user = User.query.filter_by(username="visitor").one()
    assert user.role == User.ROLE_ADMIN and user.check_password("VisitorPass1!")

    bad = runner.invoke(args=["create-visitor", "--username", "realadmin", "--password", "VisitorPass1!"])
    assert bad.exit_code != 0
    assert User.query.filter_by(username="realadmin").first() is None


@pytest.fixture
def templates(app, admin_user):
    from app.models.mc_script import McTemplate, McTemplateSegment
    from app.services.mc_template_service import McTemplateService
    McTemplateService.seed_default_templates()
    custom = McTemplate(name="Rohan Private Flow", event_type="Workshop", created_by=admin_user["user"].id,
                        is_public_to_team=True, is_default=False)
    db.session.add(custom)
    db.session.flush()
    db.session.add(McTemplateSegment(template_id=custom.id, title="Rohan secret segment",
                                     segment_type="welcome", sequence_order=1))
    db.session.commit()
    ids = {"custom": custom.id, "default": McTemplate.query.filter_by(is_default=True).first().id}
    McTemplateService._TEMPLATES_CACHE.clear()
    db.session.remove()
    return ids


@pytest.fixture(autouse=True)
def _reset_ai_quota():
    from app.utils import visitor_mode
    visitor_mode._ai_calls.clear()
    yield
    visitor_mode._ai_calls.clear()


def test_visitor_sees_builtin_templates_only(client, visitor, templates):
    resp = client.get("/api/v1/mc/templates", headers=visitor["headers"])
    assert resp.status_code == 200, resp.get_json()
    items = _items(resp)
    assert items and all(t["is_default"] for t in items)
    assert "Rohan" not in resp.get_data(as_text=True)

    detail = client.get(f"/api/v1/mc/templates/{templates['default']}", headers=visitor["headers"])
    assert detail.status_code == 200
    assert detail.get_json()["data"]["segments"]
    assert client.get(f"/api/v1/mc/templates/{templates['custom']}",
                      headers=visitor["headers"]).status_code == 404


def test_visitor_can_use_ai_tools_without_saving(client, visitor, real_data):
    before = (Event.query.count(), Team.query.count(), Member.query.count())
    db.session.remove()
    calls = [
        ("/api/v1/mc/ai/generate-script", {"title": "Tech Talk", "event_type": "Technical Talk"}),
        ("/api/v1/mc/ai/generate-segment", {"segment_type": "welcome", "event_info": {"title": "Tech Talk"}}),
        ("/api/v1/mc/ai-assist", {"instruction": "Welcome speech"}),
        ("/api/v1/documentation/ai-assist", {"field_key": "summary", "instruction": "Draft"}),
    ]
    for path, payload in calls:
        resp = client.post(path, json=payload, headers=visitor["headers"])
        assert resp.status_code != 403, (path, resp.get_json())
        assert resp.status_code < 500, (path, resp.get_json())
    assert (Event.query.count(), Team.query.count(), Member.query.count()) == before


def test_visitor_ai_calls_are_rate_limited(app, client, visitor):
    app.config["VISITOR_AI_CALLS_PER_HOUR"] = 2
    try:
        for _ in range(2):
            r = client.post("/api/v1/mc/ai-assist", json={"instruction": "x"}, headers=visitor["headers"])
            assert r.status_code == 200, r.get_json()
        r = client.post("/api/v1/mc/ai-assist", json={"instruction": "x"}, headers=visitor["headers"])
        assert r.status_code == 429
        assert r.get_json()["error"]["code"] == "VISITOR_AI_LIMIT"
    finally:
        app.config["VISITOR_AI_CALLS_PER_HOUR"] = 20


def test_visitor_still_cannot_create_scripts_or_templates(client, visitor, templates):
    for path, payload in (("/api/v1/mc/scripts", {"title": "x", "template_id": templates["default"]}),
                          ("/api/v1/mc/templates", {"name": "x", "event_type": "Workshop"}),
                          ("/api/v1/documentation/reports", {"title": "x"})):
        r = client.post(path, json=payload, headers=visitor["headers"])
        assert r.status_code == 403, (path, r.get_json())


# Parameterless GET endpoints that legitimately refuse a visitor for the same reason they refuse a
# real admin (role-specific portals, OAuth callbacks, query parameters that weren't supplied).
_EXPECTED_REFUSALS = {
    "auth.verify_setup_token", "media.drive_auth_url", "media.drive_oauth_callback",
    "research.student_overview", "research.get_student_directory", "research.list_teams",
    "assignments.list_my_assignments", "me.get_my_assignments",
}


def test_visitor_screens_load_without_errors(app, client, visitor, real_data, templates):
    """Every screen's list endpoint answers a visitor normally (no 'team not found' or read-only errors)."""
    failures = []
    for rule in app.url_map.iter_rules():
        if ("GET" not in rule.methods or not rule.rule.startswith("/api/v1/") or "<" in rule.rule
                or "docs" in rule.rule or rule.endpoint in _EXPECTED_REFUSALS):
            continue
        db.session.remove()
        resp = client.get(rule.rule, headers=visitor["headers"])
        if resp.status_code >= 400:
            failures.append(f"{rule.rule}: HTTP {resp.status_code} {resp.get_data(as_text=True)[:120]}")
    assert not failures, "\n".join(failures)


def test_visitor_never_sees_cached_mc_folders(client, visitor, real_data, admin_user):
    from app.models.documentation import EventFolder
    from app.services.mc_script_service import McScriptService
    team = McScriptService.get_or_create_mc_team()
    db.session.add(EventFolder(name="Rohan MC Folder", team_id=team.id, created_by=admin_user["user"].id))
    db.session.commit()
    db.session.remove()
    McScriptService._FOLDERS_CACHE.clear()
    assert client.get("/api/v1/mc/folders", headers=admin_user["headers"]).status_code == 200  # warms cache
    db.session.remove()
    resp = client.get("/api/v1/mc/folders", headers=visitor["headers"])
    assert resp.status_code == 200
    assert "Rohan" not in resp.get_data(as_text=True)
