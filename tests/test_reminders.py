from datetime import timedelta
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.reminder import Reminder
from app.services.reminder_service import ReminderService
from app.utils.datetime_utils import utc_now
from app.extensions import db


def test_generate_unconfirmed_reminder(app, sample_event, seed_members, admin_user):
    """Test creating confirmation reminder for assignments older than 24h."""
    with app.app_context():
        task = Task(
            event_id=sample_event.id,
            title="Unconfirmed Assignment Task",
            deadline=utc_now() + timedelta(days=5),
            created_by=admin_user["user"].id,
        )
        db.session.add(task)
        db.session.flush()

        assignment = TaskAssignment(
            task_id=task.id,
            member_id=seed_members["m1"].id,
            assigned_by=admin_user["user"].id,
            status=TaskAssignment.STATUS_AWAITING_CONFIRMATION,
            assigned_at=utc_now() - timedelta(hours=25),  # 25 hours old
        )
        db.session.add(assignment)
        db.session.commit()

        stats = ReminderService.scan_and_generate_reminders()
        assert stats["confirmation_reminders_created"] >= 1

        reminders = Reminder.query.filter_by(
            assignment_id=assignment.id,
            reminder_type=Reminder.TYPE_CONFIRMATION
        ).all()
        assert len(reminders) == 1
        assert reminders[0].status == Reminder.STATUS_DUE


def test_generate_approaching_deadline_reminder(app, sample_event, seed_members, admin_user):
    """Test generating deadline reminder within 24h of deadline."""
    with app.app_context():
        # Deadline 12 hours from now
        task = Task(
            event_id=sample_event.id,
            title="Urgent Deadline Task",
            deadline=utc_now() + timedelta(hours=12),
            created_by=admin_user["user"].id,
        )
        db.session.add(task)
        db.session.flush()

        assignment = TaskAssignment(
            task_id=task.id,
            member_id=seed_members["m2"].id,
            assigned_by=admin_user["user"].id,
            status=TaskAssignment.STATUS_ACCEPTED,
        )
        db.session.add(assignment)
        db.session.commit()

        stats = ReminderService.scan_and_generate_reminders()
        assert stats["deadline_reminders_created"] >= 1

        r = Reminder.query.filter_by(
            assignment_id=assignment.id,
            reminder_type=Reminder.TYPE_DEADLINE
        ).first()
        assert r is not None


def test_flag_overdue_and_generate_reminder(app, sample_event, seed_members, admin_user):
    """Test flagging overdue assignments and generating overdue reminder."""
    with app.app_context():
        task = Task(
            event_id=sample_event.id,
            title="Overdue Task",
            deadline=utc_now() - timedelta(hours=2),  # deadline passed 2h ago
            created_by=admin_user["user"].id,
        )
        db.session.add(task)
        db.session.flush()

        assignment = TaskAssignment(
            task_id=task.id,
            member_id=seed_members["m1"].id,
            assigned_by=admin_user["user"].id,
            status=TaskAssignment.STATUS_IN_PROGRESS,
        )
        db.session.add(assignment)
        db.session.commit()

        assert assignment.is_overdue() is True

        stats = ReminderService.scan_and_generate_reminders()
        assert stats["overdue_reminders_created"] >= 1

        r = Reminder.query.filter_by(
            assignment_id=assignment.id,
            reminder_type=Reminder.TYPE_OVERDUE
        ).first()
        assert r is not None


def test_avoid_duplicate_reminders_on_repeated_runs(app, sample_event, seed_members, admin_user):
    """Test that running the scheduler multiple times does NOT generate duplicate reminders."""
    with app.app_context():
        task = Task(
            event_id=sample_event.id,
            title="Repeat Scan Task",
            deadline=utc_now() + timedelta(hours=10),
            created_by=admin_user["user"].id,
        )
        db.session.add(task)
        db.session.flush()

        assignment = TaskAssignment(
            task_id=task.id,
            member_id=seed_members["m1"].id,
            assigned_by=admin_user["user"].id,
            status=TaskAssignment.STATUS_ACCEPTED,
        )
        db.session.add(assignment)
        db.session.commit()

        # Run 1
        stats1 = ReminderService.scan_and_generate_reminders()
        count1 = Reminder.query.filter_by(assignment_id=assignment.id).count()
        assert count1 == 1

        # Run 2 immediately
        stats2 = ReminderService.scan_and_generate_reminders()
        count2 = Reminder.query.filter_by(assignment_id=assignment.id).count()
        assert count2 == 1  # count unchanged!
        assert stats2["deadline_reminders_created"] == 0
        assert stats2["total_skipped_duplicates"] >= 1


def test_skip_completed_and_cancelled_assignments(app, sample_event, seed_members, admin_user):
    """Test that completed and cancelled assignments are skipped from receiving new reminders."""
    with app.app_context():
        task = Task(
            event_id=sample_event.id,
            title="Completed Task",
            deadline=utc_now() + timedelta(hours=5),
            created_by=admin_user["user"].id,
        )
        db.session.add(task)
        db.session.flush()

        # Completed assignment
        a1 = TaskAssignment(
            task_id=task.id,
            member_id=seed_members["m1"].id,
            assigned_by=admin_user["user"].id,
            status=TaskAssignment.STATUS_COMPLETED,
        )
        # Cancelled assignment
        a2 = TaskAssignment(
            task_id=task.id,
            member_id=seed_members["m2"].id,
            assigned_by=admin_user["user"].id,
            status=TaskAssignment.STATUS_CANCELLED,
        )
        db.session.add_all([a1, a2])
        db.session.commit()

        ReminderService.scan_and_generate_reminders()
        reminders_a1 = Reminder.query.filter_by(assignment_id=a1.id).count()
        reminders_a2 = Reminder.query.filter_by(assignment_id=a2.id).count()
        assert reminders_a1 == 0
        assert reminders_a2 == 0


def test_recover_missed_reminders_after_restart(app, sample_event, seed_members, admin_user):
    """
    Test that if an app was offline and restarts, missed reminders are identified
    and marked due.
    """
    with app.app_context():
        task = Task(
            event_id=sample_event.id,
            title="Restart Recovery Task",
            deadline=utc_now() + timedelta(days=2),
            created_by=admin_user["user"].id,
        )
        db.session.add(task)
        db.session.flush()

        assignment = TaskAssignment(
            task_id=task.id,
            member_id=seed_members["m1"].id,
            assigned_by=admin_user["user"].id,
            status=TaskAssignment.STATUS_ACCEPTED,
        )
        db.session.add(assignment)
        db.session.flush()

        # Simulate a scheduled reminder that fell due while offline
        offline_scheduled_time = utc_now() - timedelta(hours=3)
        reminder = Reminder(
            assignment_id=assignment.id,
            reminder_type=Reminder.TYPE_DEADLINE,
            scheduled_at=offline_scheduled_time,
            status=Reminder.STATUS_SCHEDULED,
            deduplication_key=f"offline_test:{assignment.id}",
        )
        db.session.add(reminder)
        db.session.commit()

        # Run scheduler
        stats = ReminderService.scan_and_generate_reminders()
        assert stats["reminders_marked_due"] >= 1

        refreshed = db.session.get(Reminder, reminder.id)
        assert refreshed.status == Reminder.STATUS_DUE
