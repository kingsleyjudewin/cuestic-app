"""Regression tests for production-readiness fixes (security, storage, reminders, limits)."""
import io
import os
import shutil
from datetime import timedelta

import pytest
from flask import Flask
from sqlalchemy import event

from app.extensions import db
from app.models.reminder import Reminder
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.user import ApiToken, User
from app.utils.datetime_utils import utc_now
from app.utils.errors import NotFoundError
from tests.conftest import create_user_with_token


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
def test_hardcoded_admin_passwords_no_longer_work(app, client):
    with app.app_context():
        user = User(username="clubadmin", email="clubadmin@test.edu", role=User.ROLE_PRESIDENT, is_active=True)
        user.set_password("A-Real-Unique-Passw0rd!")
        db.session.add(user)
        db.session.commit()
        assert user.check_password("A-Real-Unique-Passw0rd!")
        for leaked in ("AdminPass123!Secure", "clubadminsecure123"):
            assert not user.check_password(leaked)
            res = client.post("/api/v1/auth/login", json={"username": "clubadmin", "password": leaked})
            assert res.status_code == 401


def _profile(client, token):
    return client.get("/api/v1/me/profile", headers={"Authorization": f"Bearer {token}"})


def test_revocation_by_another_process_takes_effect_immediately(app, client):
    with app.app_context():
        user, token = create_user_with_token("rev_user", User.ROLE_MEMBER)
        assert _profile(client, token).status_code == 200  # now cached in this process

        # Simulate a logout handled by a different worker: DB updated, local cache untouched.
        db.session.query(ApiToken).filter_by(user_id=user.id).update({"is_revoked": True})
        db.session.commit()
        assert _profile(client, token).status_code == 401


def test_deactivation_by_another_process_takes_effect_immediately(app, client):
    with app.app_context():
        user, token = create_user_with_token("deact_user", User.ROLE_MEMBER)
        assert _profile(client, token).status_code == 200
        db.session.query(User).filter_by(id=user.id).update({"is_active": False})
        db.session.commit()
        assert _profile(client, token).status_code == 401


def test_logout_revokes_token(app, client):
    with app.app_context():
        _, token = create_user_with_token("logout_user", User.ROLE_MEMBER)
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/v1/me/profile", headers=headers).status_code == 200
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
        assert client.get("/api/v1/me/profile", headers=headers).status_code == 401


# ---------------------------------------------------------------------------
# Path traversal / file access
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_key", ["/etc/passwd", "../.env", "a/../../b", "documentation/../../x", "", "x\x00y"])
def test_storage_rejects_unsafe_keys(app, bad_key, tmp_path, monkeypatch):
    from app.services.firebase_storage_service import FirebaseStorageService
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path))
    monkeypatch.setattr(FirebaseStorageService, "initialize", classmethod(lambda cls, force_refresh=False: False))
    monkeypatch.setattr(FirebaseStorageService, "_bucket", None)
    with pytest.raises(NotFoundError):
        FirebaseStorageService.get_file_bytes(bad_key)


def test_report_image_resolver_only_reads_inside_storage(app, tmp_path, monkeypatch):
    from app.services.documentation_service import _resolve_safe_local_image_path
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path))
    inside = tmp_path / "media" / "photo.png"
    inside.parent.mkdir(parents=True)
    inside.write_bytes(b"\x89PNG fake")
    with app.app_context():
        assert _resolve_safe_local_image_path("media/photo.png") == os.path.realpath(inside)
        assert _resolve_safe_local_image_path(str(inside)) == os.path.realpath(inside)
        for evil in ("/etc/passwd", "../../../../etc/passwd", "media/../../" + "x"):
            assert _resolve_safe_local_image_path(evil) is None


def test_research_attachment_requires_auth_and_ownership(app, client, tmp_path, monkeypatch):
    from app.services.firebase_storage_service import FirebaseStorageService
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path))
    monkeypatch.setenv("STRICT_CLOUD_STORAGE", "false")
    monkeypatch.setattr(FirebaseStorageService, "initialize", classmethod(lambda cls, force_refresh=False: False))
    monkeypatch.setattr(FirebaseStorageService, "_bucket", None)
    with app.app_context():
        _, owner_token = create_user_with_token("res_owner", User.ROLE_STUDENT_RESEARCHER)
        _, other_token = create_user_with_token("res_other", User.ROLE_MEMBER)

        up = client.post(
            "/api/v1/research/attachments/upload",
            data={"file": (io.BytesIO(b"paper contents"), "paper.pdf")},
            content_type="multipart/form-data",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert up.status_code == 201, up.get_json()
        data = up.get_json()["data"]
        assert data["storage_path"].startswith("research/")
        assert (tmp_path / data["storage_path"]).is_file()  # persisted in the storage root
        url = data["file_url"]

        assert client.get(url).status_code == 401
        assert client.get(url, headers={"Authorization": f"Bearer {other_token}"}).status_code == 403
        ok = client.get(url, headers={"Authorization": f"Bearer {owner_token}"})
        assert ok.status_code == 200 and ok.data == b"paper contents"

        bad = client.post(
            "/api/v1/research/attachments/upload",
            data={"file": (io.BytesIO(b"<script>"), "evil.html")},
            content_type="multipart/form-data",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert bad.status_code == 400


def test_strict_storage_refuses_ephemeral_disk_in_production(app, monkeypatch):
    from app.services.firebase_storage_service import FirebaseStorageService, StorageUnavailableError
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("STORAGE_LOCAL_ROOT", raising=False)
    monkeypatch.delenv("STRICT_CLOUD_STORAGE", raising=False)
    monkeypatch.setattr(FirebaseStorageService, "initialize", classmethod(lambda cls, force_refresh=False: False))
    monkeypatch.setattr(FirebaseStorageService, "_bucket", None)
    with pytest.raises(StorageUnavailableError) as exc:
        FirebaseStorageService.put_object("documentation/1/1/x.pdf", io.BytesIO(b"data"))
    assert exc.value.status_code == 503


# ---------------------------------------------------------------------------
# OAuth state, API keys
# ---------------------------------------------------------------------------
def test_google_oauth_state_is_signed(app, monkeypatch):
    from app.services import google_drive_service as gds
    from app.utils.errors import ValidationError
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")

    class _Resp:
        status_code = 400
        text = '{"error": "invalid_grant"}'

    monkeypatch.setattr(gds.requests, "post", lambda *a, **k: _Resp())
    with app.app_context():
        with pytest.raises(ValidationError, match="state"):
            gds.GoogleDriveService.handle_oauth_callback("code", '{"user_id": 1, "timestamp": 0}')

        url = gds.GoogleDriveService.get_auth_url(user_id=42)
        state = gds.requests.utils.unquote(url.split("state=")[1].split("&")[0])
        assert "user_id" not in state  # opaque, signed token
        # A valid state passes verification and fails later, at the (mocked) token exchange.
        with pytest.raises(ValidationError, match="exchange"):
            gds.GoogleDriveService.handle_oauth_callback("code", state)


def test_gemini_key_never_in_url_or_error(app, monkeypatch):
    from app.services import ai_service
    from app.utils.errors import ValidationError
    seen = {}

    def fake_post(url, **kwargs):
        seen["url"] = url
        seen["headers"] = kwargs.get("headers") or {}
        raise ai_service.requests.ConnectionError(f"Max retries exceeded with url: {url}")

    monkeypatch.setattr(ai_service.requests, "post", fake_post)
    provider = ai_service.GeminiProvider(api_key="AIzaSECRETKEY123", model_name="gemini-test")
    with app.app_context():
        with pytest.raises(ValidationError) as exc:
            provider.generate("hello")
    assert "AIzaSECRETKEY123" not in seen["url"]
    assert seen["headers"].get("x-goog-api-key") == "AIzaSECRETKEY123"
    assert "AIzaSECRETKEY123" not in str(exc.value.message)


# ---------------------------------------------------------------------------
# CORS, headers, production config
# ---------------------------------------------------------------------------
def _checker(**config):
    from app import _build_origin_checker
    fake = Flask("cors-test")
    fake.config.update({"DEBUG": False, "FLASK_ENV": "production", **config})
    return _build_origin_checker(fake)


def test_cors_allow_list():
    allowed = _checker(CORS_ORIGINS=["https://cuestic.vercel.app"],
                       CORS_ORIGIN_REGEX=r"^https://cuestic-[a-z0-9-]+\.vercel\.app$")
    assert allowed("https://cuestic.vercel.app")
    assert allowed("https://cuestic-git-feature-x.vercel.app")
    assert not allowed("https://evil.example.com")
    assert not allowed("http://localhost:8080")  # dev hosts are not allowed in production
    assert not allowed("")
    dev = _checker(CORS_ORIGINS=["https://cuestic.vercel.app"], DEBUG=True, FLASK_ENV="development")
    assert dev("http://localhost:8080")


def test_disallowed_origin_gets_no_cors_headers(client):
    res = client.get("/health", headers={"Origin": "https://evil.example.com"})
    # Test config allows "*"; the response must still never reflect credentials support.
    assert res.headers.get("Access-Control-Allow-Credentials") is None
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"


def test_production_config_rejects_insecure_settings(monkeypatch):
    from app.config import ProductionConfig
    fake = Flask("prod-test")
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "dev-insecure-key-replace-in-production")
    with pytest.raises(ValueError, match="SECRET_KEY"):
        ProductionConfig.init_app(fake)
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "x" * 48)
    monkeypatch.setattr(ProductionConfig, "DATABASE_URL", "sqlite:///prod.db")
    with pytest.raises(ValueError, match="PostgreSQL"):
        ProductionConfig.init_app(fake)


# ---------------------------------------------------------------------------
# Reminders: exactly-once delivery
# ---------------------------------------------------------------------------
def _deadline_assignment(sample_event, seed_members, admin_user, member_key="m2", hours=12):
    task = Task(event_id=sample_event.id, title=f"Deadline {member_key}",
                deadline=utc_now() + timedelta(hours=hours), created_by=admin_user["user"].id)
    db.session.add(task)
    db.session.flush()
    a = TaskAssignment(task_id=task.id, member_id=seed_members[member_key].id,
                       assigned_by=admin_user["user"].id, status=TaskAssignment.STATUS_ACCEPTED)
    db.session.add(a)
    db.session.commit()
    return a


def test_reminder_notifications_sent_once_after_commit(app, sample_event, seed_members, admin_user, monkeypatch):
    from app.services.reminder_service import ReminderService
    from app.services.notification_service import NotificationService
    sent = []
    monkeypatch.setattr(NotificationService, "notify_deadline_reminder",
                        staticmethod(lambda assignment: sent.append((assignment.id, Reminder.query.count()))))
    with app.app_context():
        a = _deadline_assignment(sample_event, seed_members, admin_user)
        ReminderService.scan_and_generate_reminders()
        ReminderService.scan_and_generate_reminders()
        ReminderService.scan_and_generate_reminders(acquire_lock=True)  # no-op lock on SQLite
        assert [s[0] for s in sent] == [a.id]
        assert sent[0][1] >= 1  # row already committed when the notification went out


def test_duplicate_reminder_does_not_roll_back_others(app, sample_event, seed_members, admin_user, monkeypatch):
    """A concurrent duplicate (unique-key race) must only discard that one row."""
    from app.services.reminder_service import ReminderService
    from app.services.notification_service import NotificationService
    sent = []
    monkeypatch.setattr(NotificationService, "notify_deadline_reminder",
                        staticmethod(lambda assignment: sent.append(assignment.id)))
    with app.app_context():
        a1 = _deadline_assignment(sample_event, seed_members, admin_user, "m2")
        a2 = _deadline_assignment(sample_event, seed_members, admin_user, "m3")
        dup_key = f"deadline:{a1.id}:{a1.task.deadline.strftime('%Y%m%d%H%M')}"
        # Another process already committed a1's reminder...
        db.session.add(Reminder(assignment_id=a1.id, reminder_type=Reminder.TYPE_DEADLINE,
                                scheduled_at=utc_now(), status=Reminder.STATUS_DUE, deduplication_key=dup_key))
        db.session.commit()
        # ...but this process's existence check has not seen it yet (race window).
        real_filter_by = Reminder.query.filter_by
        class _Blind:
            def __init__(self, q): self.q = q
            def first(self): return None
        monkeypatch.setattr(Reminder, "query", type("Q", (), {
            "filter_by": staticmethod(lambda **kw: _Blind(None) if kw.get("deduplication_key") == dup_key else real_filter_by(**kw)),
            "filter": staticmethod(lambda *a, **k: db.session.query(Reminder).filter(*a, **k)),
        })())
        stats = ReminderService.scan_and_generate_reminders()
        monkeypatch.undo()
        assert stats["deadline_reminders_created"] == 1
        assert sent == [a2.id]
        assert db.session.query(Reminder).filter_by(assignment_id=a2.id).count() == 1


# ---------------------------------------------------------------------------
# Heavy job limiter, PDF errors, dashboard queries
# ---------------------------------------------------------------------------
def test_heavy_job_limiter_returns_503_when_saturated():
    from app.utils import heavy_jobs
    fake = Flask("busy-test")
    fake.config.update(TESTING=False, MAX_CONCURRENT_HEAVY_JOBS=1, HEAVY_JOB_QUEUE_TIMEOUT=0)
    heavy_jobs._pools.pop("cpu", None)

    @heavy_jobs.heavy_job("cpu")
    def work():
        return "done"

    with fake.app_context():
        assert work() == "done"
        sem = heavy_jobs._pool("cpu")
        sem.acquire()
        try:
            with pytest.raises(heavy_jobs.ServerBusyError) as exc:
                work()
            assert exc.value.status_code == 503
        finally:
            sem.release()
    heavy_jobs._pools.pop("cpu", None)


def test_pdf_conversion_errors_are_explicit(monkeypatch):
    from app.utils import pdf_tools
    real_which = shutil.which
    monkeypatch.setattr(pdf_tools.shutil, "which", lambda name: None)
    with pytest.raises(pdf_tools.PdfConversionError) as exc:
        pdf_tools.pdf_to_png_pages(b"%PDF-1.4 x")
    assert exc.value.status_code == 503 and exc.value.code == "PDF_TOOL_MISSING"
    monkeypatch.setattr(pdf_tools.shutil, "which", real_which)
    if real_which("pdftoppm"):
        with pytest.raises(pdf_tools.PdfConversionError) as exc2:
            pdf_tools.pdf_to_png_pages(b"%PDF-1.4 corrupt")
        assert exc2.value.status_code == 422


def test_dashboard_summary_uses_constant_number_of_queries(app, client, admin_user, sample_event):
    with app.app_context():
        for i in range(6):
            db.session.add(Task(event_id=sample_event.id, title=f"Soon {i}",
                                deadline=utc_now() + timedelta(hours=5 + i), created_by=admin_user["user"].id))
        db.session.commit()
        client.get("/api/v1/dashboard/summary", headers=admin_user["headers"])  # warm token cache

        statements = []
        listener = lambda conn, cursor, stmt, params, ctx, many: statements.append(stmt)
        event.listen(db.engine, "before_cursor_execute", listener)
        try:
            res = client.get("/api/v1/dashboard/summary", headers=admin_user["headers"])
        finally:
            event.remove(db.engine, "before_cursor_execute", listener)
        assert res.status_code == 200
        assert len(res.get_json()["data"]["upcoming_deadlines"]) == 6
        # token revalidation + counters + upcoming tasks (with events) — independent of task count
        assert len(statements) <= 4, statements


def test_baseline_scan_records_without_notifying(app, sample_event, seed_members, admin_user, monkeypatch):
    from app.services.reminder_service import ReminderService
    from app.services.notification_service import NotificationService
    sent = []
    monkeypatch.setattr(NotificationService, "notify_deadline_reminder",
                        staticmethod(lambda assignment: sent.append(assignment.id)))
    with app.app_context():
        _deadline_assignment(sample_event, seed_members, admin_user)
        stats = ReminderService.scan_and_generate_reminders(notify=False)
        assert stats["deadline_reminders_created"] == 1 and sent == []
        ReminderService.scan_and_generate_reminders()  # later scans do not re-announce it
        assert sent == []
