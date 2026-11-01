import os
import sys
from dotenv import load_dotenv

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

from app import create_app
from app.extensions import db
from app.models.user import User, ApiToken
from app.models.team import Team
from app.models.member import Member
from app.models.event import Event
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.message_log import MessageLog
from app.models.reminder import Reminder
from app.models.activity_log import ActivityLog
from app.models.device_token import DeviceToken


def cleanup_simulated_data():
    """Safely remove all simulated/test data from the active database."""
    app = create_app()

    with app.app_context():
        print(f"Connecting to database: {db.engine.url}")
        
        # 1. Clean Reminders and Message Logs (cascade from assignments, but delete explicitly)
        deleted_reminders = Reminder.query.delete()
        print(f"  [-] Removed {deleted_reminders} Reminders")

        deleted_msg_logs = MessageLog.query.delete()
        print(f"  [-] Removed {deleted_msg_logs} Message Logs")

        # 2. Clean Task Assignments
        deleted_assignments = TaskAssignment.query.delete()
        print(f"  [-] Removed {deleted_assignments} Task Assignments")

        # 3. Clean Tasks
        deleted_tasks = Task.query.delete()
        print(f"  [-] Removed {deleted_tasks} Tasks")

        # 4. Clean Events (Demo events)
        demo_events = Event.query.filter(
            (Event.name.like("%Demo%")) | (Event.name.like("%MAGNOVITE%"))
        ).all()
        for evt in demo_events:
            db.session.delete(evt)
        print(f"  [-] Removed {len(demo_events)} Demo Events")

        # 5. Clean Members (Dummy test members)
        dummy_members = Member.query.filter(
            (Member.registration_number.like("TEST-%")) |
            (Member.full_name.like("%(Test Dummy)%"))
        ).all()
        for m in dummy_members:
            db.session.delete(m)
        print(f"  [-] Removed {len(dummy_members)} Test Dummy Members")

        # 6. Reset Team Leaders that point to simulated test users
        test_users = User.query.filter(
            User.username.in_(["doc_leader", "test_leader", "test_admin", "test_member"])
        ).all()
        test_user_ids = [u.id for u in test_users]

        teams_with_test_leader = Team.query.filter(Team.leader_user_id.in_(test_user_ids)).all()
        for t in teams_with_test_leader:
            print(f"  [~] Unlinking test leader from Team: {t.name}")
            t.leader_user_id = None

        db.session.flush()

        # 7. Remove simulated test users
        for u in test_users:
            print(f"  [-] Removed Test User: {u.username} (Role: {u.role})")
            db.session.delete(u)

        # 8. Clean test activity logs & test API tokens
        deleted_act_logs = ActivityLog.query.delete()
        print(f"  [-] Removed {deleted_act_logs} Activity Logs")

        deleted_api_tokens = ApiToken.query.delete()
        print(f"  [-] Removed {deleted_api_tokens} Api Tokens")

        deleted_device_tokens = DeviceToken.query.delete()
        print(f"  [-] Removed {deleted_device_tokens} Device Tokens")

        # 9. Verify Admin User is intact
        admin_username = os.environ.get("ADMIN_USERNAME", "clubadmin")
        admin = User.query.filter_by(username=admin_username).first()
        if admin:
            print(f"  [+] Confirmed Active Admin User preserved: '{admin.username}' ({admin.email})")
        else:
            print(f"  [!] Admin user '{admin_username}' not found - checking users in database:")
            for u in User.query.all():
                print(f"      User #{u.id}: {u.username} ({u.role})")

        # Commit all changes
        db.session.commit()
        print("[OK] All simulated data removed and changes committed.")

        # Integrity Check
        fk_check = db.session.execute(db.text("PRAGMA foreign_key_check")).fetchall()
        if fk_check:
            print(f"[!] Foreign key check warnings: {fk_check}")
        else:
            print("[OK] Foreign key integrity check passed (0 violations).")

        integrity = db.session.execute(db.text("PRAGMA integrity_check")).fetchone()
        print(f"[OK] Database integrity check: {integrity[0]}")


if __name__ == "__main__":
    cleanup_simulated_data()
