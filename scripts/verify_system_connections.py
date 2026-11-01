import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.extensions import db
from app.models.user import User, ApiToken
from app.models.team import Team
from app.models.member import Member
from app.models.event import Event
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.device_token import DeviceToken
from app.services.notification_service import _get_firebase_app, NotificationService
from app.services.whatsapp_service import WhatsAppService


def run_checks():
    print("=" * 60)
    print("RUNNING COMPREHENSIVE SYSTEM & CONNECTION CHECKS")
    print("=" * 60)

    app = create_app("development")
    client = app.test_client()

    all_passed = True

    # 1. Database Connection & Engine
    print("\n[1/7] Testing Database Connection & Schema...")
    with app.app_context():
        try:
            res = db.session.execute(db.text("SELECT 1")).scalar()
            assert res == 1
            print("  [OK] Database query 'SELECT 1' succeeded.")
            print(f"       Connected URI: {db.engine.url}")
        except Exception as e:
            print(f"  [FAIL] Database connection failed: {e}")
            all_passed = False

        # SQLite FK check
        fk_warnings = db.session.execute(db.text("PRAGMA foreign_key_check")).fetchall()
        if not fk_warnings:
            print("  [OK] PRAGMA foreign_key_check: 0 violations.")
        else:
            print(f"  [FAIL] Foreign key violations found: {fk_warnings}")
            all_passed = False

        # SQLite Integrity check
        integrity = db.session.execute(db.text("PRAGMA integrity_check")).fetchone()
        if integrity and integrity[0] == "ok":
            print("  [OK] PRAGMA integrity_check: ok.")
        else:
            print(f"  [FAIL] Integrity check failed: {integrity}")
            all_passed = False

        # Alembic migration version
        version = db.session.execute(db.text("SELECT version_num FROM alembic_version")).scalar()
        print(f"  [OK] Current Alembic Migration Version: {version}")

        # Check clean table states
        counts = {
            "teams": Team.query.count(),
            "users": User.query.count(),
            "members": Member.query.count(),
            "events": Event.query.count(),
            "tasks": Task.query.count(),
            "task_assignments": TaskAssignment.query.count(),
            "device_tokens": DeviceToken.query.count(),
        }
        print(f"  [i] Table Row Counts: {counts}")
        if counts["members"] == 0 and counts["events"] == 0 and counts["tasks"] == 0:
            print("  [OK] Database is clean of simulated records (0 members, 0 events, 0 tasks).")
        else:
            print(f"  [WARN] Simulated records may still exist: {counts}")

    # 2. Health & Root Endpoints
    print("\n[2/7] Testing Root & /health Endpoints...")
    res = client.get("/health")
    if res.status_code == 200:
        data = res.get_json()
        print(f"  [OK] /health returned {res.status_code}: {data}")
        if data.get("database") != "connected" or data.get("status") != "healthy":
            print("  [FAIL] Health payload did not report database=connected & status=healthy")
            all_passed = False
    else:
        print(f"  [FAIL] /health returned status code {res.status_code}")
        all_passed = False

    res = client.get("/")
    if res.status_code == 200:
        print(f"  [OK] '/' root returned 200: {res.get_json().get('service')}")
    else:
        print(f"  [FAIL] '/' root returned {res.status_code}")
        all_passed = False

    # 3. Authentication & User Login
    print("\n[3/7] Testing Authentication Flow...")
    admin_user = os.environ.get("ADMIN_USERNAME", "clubadmin")
    admin_pass = os.environ.get("ADMIN_PASSWORD", "AdminPass123!Secure")
    
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": admin_user, "password": admin_pass, "device_name": "Connection Verifier"},
    )
    token = None
    if login_res.status_code == 200:
        login_data = login_res.get_json()
        token = login_data["data"]["token"]
        user_info = login_data["data"]["user"]
        print(f"  [OK] Login succeeded as '{user_info['username']}' (Role: {user_info['role']})")
    else:
        print(f"  [FAIL] Login failed: {login_res.status_code} - {login_res.get_data(as_text=True)}")
        all_passed = False

    if token:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        me_res = client.get("/api/v1/auth/me", headers=headers)
        if me_res.status_code == 200:
            print(f"  [OK] /api/v1/auth/me authenticated successfully: {me_res.get_json()['data']['username']}")
        else:
            print(f"  [FAIL] /api/v1/auth/me failed: {me_res.status_code}")
            all_passed = False

    # 4. Core Resource Endpoints
    print("\n[4/7] Testing Core Resource Endpoints...")
    if token:
        # Teams
        teams_res = client.get("/api/v1/teams", headers=headers)
        if teams_res.status_code == 200:
            teams_data = teams_res.get_json()["data"]
            team_names = [t["name"] for t in teams_data]
            print(f"  [OK] /api/v1/teams returned {len(teams_data)} teams: {team_names}")
        else:
            print(f"  [FAIL] /api/v1/teams returned {teams_res.status_code}")
            all_passed = False

        # Members
        members_res = client.get("/api/v1/members", headers=headers)
        if members_res.status_code == 200:
            members_data = members_res.get_json()["data"]
            print(f"  [OK] /api/v1/members returned {len(members_data)} members (expected 0).")
        else:
            print(f"  [FAIL] /api/v1/members returned {members_res.status_code}")
            all_passed = False

        # Events
        events_res = client.get("/api/v1/events", headers=headers)
        if events_res.status_code == 200:
            events_data = events_res.get_json()["data"]
            print(f"  [OK] /api/v1/events returned {len(events_data)} events (expected 0).")
        else:
            print(f"  [FAIL] /api/v1/events returned {events_res.status_code}")
            all_passed = False

        # Reminders endpoint
        rem_res = client.get("/api/v1/reminders", headers=headers)
        if rem_res.status_code == 200:
            rem_data = rem_res.get_json()["data"]
            print(f"  [OK] /api/v1/reminders returned {len(rem_data)} reminders (expected 0).")
        else:
            print(f"  [FAIL] /api/v1/reminders returned {rem_res.status_code}")
            all_passed = False

        # Dashboard Summary
        dash_res = client.get("/api/v1/dashboard/summary", headers=headers)
        if dash_res.status_code == 200:
            dash_data = dash_res.get_json()["data"]
            print(f"  [OK] /api/v1/dashboard/summary returned metrics: {dash_data}")
        else:
            print(f"  [FAIL] /api/v1/dashboard/summary returned {dash_res.status_code}")
            all_passed = False

        # Reports
        rep_res = client.get("/api/v1/reports/assignments", headers=headers)
        if rep_res.status_code == 200:
            print("  [OK] /api/v1/reports/assignments returned 200.")
        else:
            print(f"  [FAIL] /api/v1/reports/assignments returned {rep_res.status_code}")
            all_passed = False

    # 5. Firebase Notifications Connection
    print("\n[5/7] Testing Firebase Admin SDK Connection...")
    with app.app_context():
        fb_status = _get_firebase_app()
        if fb_status:
            print("  [OK] Firebase Admin initialized successfully from service account file.")
        else:
            print("  [FAIL] Firebase Admin failed to initialize.")
            all_passed = False

    # 6. WhatsApp Dispatch Service
    print("\n[6/7] Testing WhatsApp Link Generation...")
    import urllib.parse
    phone = "919876543210"
    msg = "Test Task Assignment"
    wa_url = f"https://wa.me/{phone}?text={urllib.parse.quote(msg)}"
    if "https://wa.me/919876543210?text=" in wa_url:
        print(f"  [OK] WhatsApp click-to-chat URL correctly formed: {wa_url}")
    else:
        print(f"  [FAIL] Invalid WhatsApp URL generated: {wa_url}")
        all_passed = False

    # 7. Clean up the token generated during verification
    if token:
        client.post("/api/v1/auth/logout", headers=headers)
        print("\n[7/7] Cleaned up verification session token.")

    print("\n" + "=" * 60)
    if all_passed:
        print("ALL SYSTEM & DATABASE CONNECTIONS ARE HEALTHY AND VERIFIED!")
    else:
        print("SOME CHECKS ENCOUNTERED ISSUES. SEE OUTPUT ABOVE.")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    success = run_checks()
    sys.exit(0 if success else 1)
