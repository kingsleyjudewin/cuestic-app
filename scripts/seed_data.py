import os
import sys
from datetime import timedelta
from dotenv import load_dotenv

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

load_dotenv()

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.team import Team, slugify
from app.models.member import Member
from app.models.event import Event
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.utils.datetime_utils import utc_now


def seed():
    """Idempotent database seeding script."""
    app = create_app()

    with app.app_context():
        print("Starting database seeding...")

        # 1. Seed Teams
        # Initial three confirmed teams: Volunteering, Documentation, Media
        # Fourth team configurable via FOURTH_TEAM_NAME env var or unseeded until admin specifies
        initial_teams = [
            ("Volunteering", "Coordinates student volunteers, stage setup, and attendee management."),
            ("Documentation", "Maintains minutes, formal event reports, feedback records, and archives."),
            ("Media", "Handles photography, video coverage, livestreaming, and social media releases."),
        ]

        fourth_team_name = os.environ.get("FOURTH_TEAM_NAME", "").strip()
        if fourth_team_name:
            initial_teams.append((fourth_team_name, "Configured departmental operational team."))

        teams_by_name = {}
        for name, desc in initial_teams:
            slug = slugify(name)
            team = Team.query.filter((Team.name == name) | (Team.slug == slug)).first()
            if not team:
                team = Team(name=name, slug=slug, description=desc, is_active=True)
                db.session.add(team)
                print(f"  [+] Created Team: {name}")
            else:
                print(f"  [.] Team exists: {name}")
            teams_by_name[name] = team

        db.session.flush()

        # 2. Seed Administrator User
        admin_username = os.environ.get("ADMIN_USERNAME", "clubadmin")
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@club.university.edu")
        admin_password = os.environ.get("ADMIN_PASSWORD")

        if not admin_password:
            # Check if admin already exists
            existing_admin = User.query.filter_by(username=admin_username).first()
            if not existing_admin:
                print("  [!] WARNING: ADMIN_PASSWORD environment variable not set.")
                print("      Using a generated secure password for local development only.")
                admin_password = "DevAdminPass2026!ChangeMe"
                print(f"      Development Credentials: {admin_username} / {admin_password}")

        admin = User.query.filter_by(username=admin_username).first()
        if not admin:
            admin = User(
                username=admin_username,
                email=admin_email,
                role=User.ROLE_PRESIDENT,
                is_active=True,
            )
            admin.set_password(admin_password)
            db.session.add(admin)
            print(f"  [+] Created President/Admin User: {admin_username}")
        else:
            print(f"  [.] Admin User exists: {admin_username}")

        # Seed a Team Leader for testing
        leader_user = User.query.filter_by(username="doc_leader").first()
        if not leader_user:
            leader_user = User(
                username="doc_leader",
                email="docleader@club.university.edu",
                role=User.ROLE_TEAM_LEADER,
                is_active=True,
            )
            leader_user.set_password("LeaderPass2026!Secure")
            db.session.add(leader_user)
            print("  [+] Created Team Leader User: doc_leader")
        else:
            print("  [.] Team Leader exists: doc_leader")

        db.session.flush()

        # Link Documentation team leader
        doc_team = teams_by_name.get("Documentation")
        if doc_team and not doc_team.leader_user_id:
            doc_team.leader_user_id = leader_user.id
            print("  [+] Assigned doc_leader as leader of Documentation team")

        # 3. Seed Dummy Members (clearly synthetic numbers conforming to E.164, not real people)
        # Using 555-prefix convention or Indian test series 987650000X
        dummy_members_data = [
            ("Ananya Sharma (Test Dummy)", "TEST-REG-001", "3rd Year CSE", "A", "+919876500001", "Volunteering"),
            ("Rohan Verma (Test Dummy)", "TEST-REG-002", "3rd Year CSE", "B", "+919876500002", "Volunteering"),
            ("Priya Patel (Test Dummy)", "TEST-REG-003", "2nd Year ECE", "A", "+919876500003", "Documentation"),
            ("Kavita Nair (Test Dummy)", "TEST-REG-004", "2nd Year IT", "C", "+919876500004", "Media"),
            ("Arjun Das (Test Dummy)", "TEST-REG-005", "4th Year ME", "A", "+919876500005", "Media"),
        ]

        members_by_name = {}
        for full_name, reg_no, class_name, sec, phone, team_name in dummy_members_data:
            member = Member.query.filter_by(registration_number=reg_no).first()
            team = teams_by_name.get(team_name) or teams_by_name["Volunteering"]
            if not member:
                member = Member(
                    full_name=full_name,
                    registration_number=reg_no,
                    class_name=class_name,
                    section=sec,
                    phone_number=phone,
                    country_code="+91",
                    team_id=team.id,
                    whatsapp_opt_in=True,
                    is_active=True,
                )
                db.session.add(member)
                print(f"  [+] Created Dummy Member: {full_name} ({reg_no})")
            else:
                print(f"  [.] Member exists: {full_name}")
            members_by_name[reg_no] = member

        db.session.flush()

        # 4. Seed Dummy Event
        event_name = "MAGNOVITE 2026 (Demo Event)"
        event = Event.query.filter_by(name=event_name).first()
        if not event:
            start_date = utc_now() + timedelta(days=7)
            end_date = start_date + timedelta(days=2)
            event = Event(
                name=event_name,
                description="Annual department symposium featuring coding hackathons, technical paper presentations and cultural night.",
                start_at=start_date,
                end_at=end_date,
                location="Main Auditorium & Lab Complex",
                status=Event.STATUS_UPCOMING,
                created_by=admin.id,
            )
            db.session.add(event)
            print(f"  [+] Created Demo Event: {event_name}")
        else:
            print(f"  [.] Demo Event exists: {event_name}")

        db.session.flush()

        # 5. Seed Sample Task and Assignments
        task_title = "Prepare Event Announcement Poster & Digital Banners"
        task = Task.query.filter_by(event_id=event.id, title=task_title).first()
        if not task:
            task_deadline = utc_now() + timedelta(days=3)
            task = Task(
                event_id=event.id,
                title=task_title,
                description="Design high-resolution announcement banners for Instagram, LinkedIn and department bulletin boards.",
                priority=Task.PRIORITY_HIGH,
                deadline=task_deadline,
                created_by=admin.id,
            )
            db.session.add(task)
            db.session.flush()

            # Assign to Media member and Volunteering member
            assigned_regs = ["TEST-REG-004", "TEST-REG-001"]
            for reg in assigned_regs:
                m = members_by_name.get(reg)
                if m:
                    assignment = TaskAssignment(
                        task_id=task.id,
                        member_id=m.id,
                        assigned_by=admin.id,
                        status=TaskAssignment.STATUS_AWAITING_CONFIRMATION,
                    )
                    db.session.add(assignment)
            print(f"  [+] Created Demo Task: '{task_title}' with {len(assigned_regs)} assignees")
        else:
            print(f"  [.] Demo Task exists: '{task_title}'")

        db.session.commit()
        print("Database seeding completed successfully!")


if __name__ == "__main__":
    seed()
