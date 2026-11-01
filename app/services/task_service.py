from datetime import timezone
from app.extensions import db
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.event import Event
from app.models.member import Member
from app.models.user import User
from app.models.reminder import Reminder
from app.utils.datetime_utils import utc_now
from app.utils.errors import ValidationError, NotFoundError, ConflictError, PermissionDeniedError
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService



class TaskService:
    @staticmethod
    def get_task_by_id(task_id: int) -> Task:
        """Get task by ID or raise NotFoundError."""
        task = db.session.get(Task, task_id)
        if not task:
            raise NotFoundError(f"Task with ID {task_id} not found.")
        return task

    @staticmethod
    def get_assignment_by_id(assignment_id: int) -> TaskAssignment:
        """Get task assignment by ID or raise NotFoundError."""
        assignment = db.session.get(TaskAssignment, assignment_id)
        if not assignment:
            raise NotFoundError(f"Assignment with ID {assignment_id} not found.")
        return assignment

    @staticmethod
    def create_task_with_assignments(event_id: int, data: dict, member_ids: list[int], actor_user: User) -> Task:
        """
        Create a task and assign it to multiple members transactionally.
        Rolls back all changes if any validation or insertion fails.
        """
        event = db.session.get(Event, event_id)
        if not event:
            raise NotFoundError(f"Event with ID {event_id} not found.")

        if event.status in (Event.STATUS_COMPLETED, Event.STATUS_CANCELLED):
            raise ValidationError(
                f"Cannot create tasks for event in '{event.status}' status.",
                details={"event_status": event.status}
            )

        deadline = data["deadline"]
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)

        if deadline <= utc_now():
            raise ValidationError("Task deadline must be in the future.", details={"deadline": deadline.isoformat()})

        if not member_ids:
            raise ValidationError("At least one member must be selected for assignment.")

        # Deduplicate member_ids if client sent duplicates
        unique_member_ids = list(dict.fromkeys(member_ids))

        # Validate all members
        members = Member.query.filter(Member.id.in_(unique_member_ids)).all()
        found_ids = {m.id for m in members}
        missing_ids = set(unique_member_ids) - found_ids
        if missing_ids:
            raise NotFoundError(
                f"One or more members were not found: {list(missing_ids)}.",
                details={"missing_member_ids": list(missing_ids)}
            )

        # Check all active
        inactive_members = [m for m in members if not m.is_active]
        if inactive_members:
            raise ValidationError(
                "Cannot assign tasks to inactive members.",
                details={"inactive_member_ids": [m.id for m in inactive_members]}
            )

        # Role-based restriction: team leaders can only assign members of teams they lead
        if actor_user.is_team_leader() and not actor_user.is_admin():
            led_team_ids = {t.id for t in actor_user.led_teams.all()}
            invalid_teams = [m for m in members if m.team_id not in led_team_ids]
            if invalid_teams:
                raise PermissionDeniedError(
                    "Team leaders can only assign tasks to members in their own teams.",
                    details={"unauthorized_member_ids": [m.id for m in invalid_teams]}
                )

        try:
            task = Task(
                event_id=event.id,
                title=data["title"].strip(),
                description=data.get("description", "").strip() if data.get("description") else None,
                priority=data.get("priority", Task.PRIORITY_MEDIUM),
                deadline=deadline,
                created_by=actor_user.id,
            )
            db.session.add(task)
            db.session.flush()

            for member in members:
                assignment = TaskAssignment(
                    task_id=task.id,
                    member_id=member.id,
                    assigned_by=actor_user.id,
                    status=TaskAssignment.STATUS_AWAITING_CONFIRMATION,
                )
                db.session.add(assignment)

            AuditService.log_action(
                action="TASK_CREATED",
                entity_type="Task",
                entity_id=task.id,
                actor_user_id=actor_user.id,
                details={"assigned_count": len(members), "event_id": event.id}
            )
            db.session.commit()

            for a in task.assignments:
                try:
                    NotificationService.notify_new_assignment(a, actor_user)
                except Exception:
                    pass

            return task


        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def add_assignments_to_task(task_id: int, member_ids: list[int], actor_user: User) -> list[TaskAssignment]:
        """Add more member assignments to an existing active task."""
        task = TaskService.get_task_by_id(task_id)
        if task.is_cancelled:
            raise ValidationError("Cannot assign members to a cancelled task.")

        unique_member_ids = list(dict.fromkeys(member_ids))
        members = Member.query.filter(Member.id.in_(unique_member_ids)).all()
        found_ids = {m.id for m in members}
        missing_ids = set(unique_member_ids) - found_ids
        if missing_ids:
            raise NotFoundError(f"Members not found: {list(missing_ids)}.")

        # Check inactive
        inactive = [m for m in members if not m.is_active]
        if inactive:
            raise ValidationError("Cannot assign inactive members.")

        # Check team leader permissions
        if actor_user.is_team_leader() and not actor_user.is_admin():
            led_team_ids = {t.id for t in actor_user.led_teams.all()}
            unauthorized = [m for m in members if m.team_id not in led_team_ids]
            if unauthorized:
                raise PermissionDeniedError("Cannot assign members from other teams.")

        # Check duplicate assignments
        existing_assignee_ids = {a.member_id for a in task.assignments.all()}
        duplicates = set(unique_member_ids).intersection(existing_assignee_ids)
        if duplicates:
            raise ConflictError(
                f"Members already assigned to this task: {list(duplicates)}.",
                details={"duplicate_member_ids": list(duplicates)}
            )

        new_assignments = []
        for member in members:
            assignment = TaskAssignment(
                task_id=task.id,
                member_id=member.id,
                assigned_by=actor_user.id,
                status=TaskAssignment.STATUS_AWAITING_CONFIRMATION,
            )
            db.session.add(assignment)
            new_assignments.append(assignment)

        AuditService.log_action(
            action="TASK_ASSIGNMENTS_ADDED",
            entity_type="Task",
            entity_id=task.id,
            actor_user_id=actor_user.id,
            details={"new_assigned_count": len(new_assignments)}
        )
        db.session.commit()
        return new_assignments

    @staticmethod
    def cancel_task(task: Task, actor_user: User) -> Task:
        """Cancel a task and all associated active assignments and reminders."""
        task.is_cancelled = True
        for a in task.assignments.all():
            if a.status not in (TaskAssignment.STATUS_COMPLETED, TaskAssignment.STATUS_CANCELLED):
                a.status = TaskAssignment.STATUS_CANCELLED
            for r in a.reminders.filter_by(status=Reminder.STATUS_SCHEDULED).all():
                r.status = Reminder.STATUS_CANCELLED

        AuditService.log_action(
            action="TASK_CANCELLED",
            entity_type="Task",
            entity_id=task.id,
            actor_user_id=actor_user.id,
        )
        db.session.commit()
        return task

    @staticmethod
    def update_assignment_status(assignment: TaskAssignment, new_status: str, actor_user: User, note: str = None) -> TaskAssignment:
        """
        Transition assignment status with role-based validation.
        """
        # Determine if actor is assigned member
        is_self = (
            assignment.member
            and assignment.member.linked_user_id
            and assignment.member.linked_user_id == actor_user.id
        )
        is_leader_or_admin = actor_user.is_admin() or (
            actor_user.is_team_leader()
            and assignment.member
            and assignment.member.team_id in [t.id for t in actor_user.led_teams.all()]
        )

        if not is_self and not is_leader_or_admin:
            raise PermissionDeniedError("You do not have permission to update this assignment.")

        # Permissions check per status:
        # A member can only mark: accepted, declined, in_progress, submitted, blocked
        # Only leader or admin can approve / mark 'completed'
        if new_status == TaskAssignment.STATUS_COMPLETED and not is_leader_or_admin:
            raise PermissionDeniedError(
                "Only an authorized team leader or club administrator can mark an assignment as completed."
            )

        if new_status == TaskAssignment.STATUS_CANCELLED and not is_leader_or_admin:
            raise PermissionDeniedError(
                "Only an authorized team leader or club administrator can cancel an assignment."
            )

        prev_status = assignment.status
        assignment.transition_to(new_status, note=note)

        # Cancel any pending reminders if assignment reached terminal state
        if new_status in (TaskAssignment.STATUS_COMPLETED, TaskAssignment.STATUS_CANCELLED):
            for r in assignment.reminders.filter_by(status=Reminder.STATUS_SCHEDULED).all():
                r.status = Reminder.STATUS_CANCELLED

        AuditService.log_action(
            action="ASSIGNMENT_STATUS_CHANGED",
            entity_type="TaskAssignment",
            entity_id=assignment.id,
            actor_user_id=actor_user.id,
            details={"previous_status": prev_status, "new_status": new_status, "note": note}
        )
        db.session.commit()

        try:
            NotificationService.notify_assignment_update(assignment, new_status)
        except Exception:
            pass

        return assignment
