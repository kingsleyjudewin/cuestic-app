"""add_research_management_system

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-11-01 17:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e4f5a6b7c8d9'
down_revision = 'd3e4f5a6b7c8'
branch_labels = None
depends_on = None


def upgrade():
    # 1. faculty_profiles
    op.create_table(
        'faculty_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('full_name', sa.String(length=150), nullable=False),
        sa.Column('department', sa.String(length=150), nullable=False, server_default='Electronics and Communication Engineering'),
        sa.Column('designation', sa.String(length=100), nullable=True),
        sa.Column('specialization', sa.String(length=255), nullable=True),
        sa.Column('research_interests', sa.Text(), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('phone_number', sa.String(length=30), nullable=True),
        sa.Column('profile_image_url', sa.String(length=500), nullable=True),
        sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_faculty_profiles_full_name'), 'faculty_profiles', ['full_name'], unique=False)

    # 2. research_student_profiles
    op.create_table(
        'research_student_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=True),
        sa.Column('full_name', sa.String(length=150), nullable=False),
        sa.Column('registration_number', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('department', sa.String(length=150), nullable=False, server_default='Electronics and Communication Engineering'),
        sa.Column('programme', sa.String(length=100), nullable=False, server_default='B.Tech ECE'),
        sa.Column('semester', sa.String(length=30), nullable=False, server_default='Semester 5'),
        sa.Column('phone_number', sa.String(length=30), nullable=True),
        sa.Column('profile_image_url', sa.String(length=500), nullable=True),
        sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
        sa.UniqueConstraint('registration_number')
    )
    op.create_index(op.f('ix_research_student_profiles_full_name'), 'research_student_profiles', ['full_name'], unique=False)
    op.create_index(op.f('ix_research_student_profiles_email'), 'research_student_profiles', ['email'], unique=False)
    op.create_index(op.f('ix_research_student_profiles_member_id'), 'research_student_profiles', ['member_id'], unique=False)

    # 3. research_teams
    op.create_table(
        'research_teams',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('faculty_id', sa.Integer(), nullable=False),
        sa.Column('domain', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('objectives', sa.Text(), nullable=True),
        sa.Column('tags_json', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['faculty_id'], ['faculty_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_research_teams_name'), 'research_teams', ['name'], unique=False)
    op.create_index(op.f('ix_research_teams_faculty_id'), 'research_teams', ['faculty_id'], unique=False)
    op.create_index(op.f('ix_research_teams_domain'), 'research_teams', ['domain'], unique=False)

    # 4. research_team_members
    op.create_table(
        'research_team_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['team_id'], ['research_teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['research_student_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'student_id', name='uq_research_team_student')
    )
    op.create_index(op.f('ix_research_team_members_team_id'), 'research_team_members', ['team_id'], unique=False)
    op.create_index(op.f('ix_research_team_members_student_id'), 'research_team_members', ['student_id'], unique=False)

    # 5. research_projects
    op.create_table(
        'research_projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('faculty_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('research_problem', sa.Text(), nullable=True),
        sa.Column('objectives', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expected_completion_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='in_progress'),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['research_teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['faculty_id'], ['faculty_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_research_projects_team_id'), 'research_projects', ['team_id'], unique=False)
    op.create_index(op.f('ix_research_projects_faculty_id'), 'research_projects', ['faculty_id'], unique=False)
    op.create_index(op.f('ix_research_projects_status'), 'research_projects', ['status'], unique=False)
    op.create_index(op.f('ix_research_projects_is_archived'), 'research_projects', ['is_archived'], unique=False)

    # 6. research_project_members
    op.create_table(
        'research_project_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='Student Researcher'),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['research_projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['research_student_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'student_id', name='uq_research_project_student')
    )
    op.create_index(op.f('ix_research_project_members_project_id'), 'research_project_members', ['project_id'], unique=False)
    op.create_index(op.f('ix_research_project_members_student_id'), 'research_project_members', ['student_id'], unique=False)

    # 7. research_milestones
    op.create_table(
        'research_milestones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('target_criteria', sa.Text(), nullable=True),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('priority', sa.String(length=20), nullable=False, server_default='Medium'),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='not_started'),
        sa.Column('completion_percentage', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['research_projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_research_milestones_project_id'), 'research_milestones', ['project_id'], unique=False)
    op.create_index(op.f('ix_research_milestones_status'), 'research_milestones', ['status'], unique=False)

    # 8. research_milestone_assignees
    op.create_table(
        'research_milestone_assignees',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('milestone_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['milestone_id'], ['research_milestones.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['research_student_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('milestone_id', 'student_id', name='uq_research_milestone_student')
    )
    op.create_index(op.f('ix_research_milestone_assignees_milestone_id'), 'research_milestone_assignees', ['milestone_id'], unique=False)
    op.create_index(op.f('ix_research_milestone_assignees_student_id'), 'research_milestone_assignees', ['student_id'], unique=False)

    # 9. research_tasks
    op.create_table(
        'research_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('milestone_id', sa.Integer(), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('priority', sa.String(length=20), nullable=False, server_default='Medium'),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='not_started'),
        sa.Column('progress_percentage', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_criteria', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['milestone_id'], ['research_milestones.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['research_projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_research_tasks_milestone_id'), 'research_tasks', ['milestone_id'], unique=False)
    op.create_index(op.f('ix_research_tasks_project_id'), 'research_tasks', ['project_id'], unique=False)
    op.create_index(op.f('ix_research_tasks_status'), 'research_tasks', ['status'], unique=False)

    # 10. research_task_assignees
    op.create_table(
        'research_task_assignees',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['research_tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['research_student_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id', 'student_id', name='uq_research_task_student')
    )
    op.create_index(op.f('ix_research_task_assignees_task_id'), 'research_task_assignees', ['task_id'], unique=False)
    op.create_index(op.f('ix_research_task_assignees_student_id'), 'research_task_assignees', ['student_id'], unique=False)

    # 11. research_progress_submissions
    op.create_table(
        'research_progress_submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('milestone_id', sa.Integer(), nullable=True),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('progress_percentage', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('papers_reviewed', sa.Integer(), nullable=True),
        sa.Column('citations_prepared', sa.Integer(), nullable=True),
        sa.Column('work_completed', sa.Text(), nullable=False),
        sa.Column('challenges', sa.Text(), nullable=True),
        sa.Column('next_steps', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='submitted_for_review'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['research_tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['milestone_id'], ['research_milestones.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['student_id'], ['research_student_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_research_progress_submissions_task_id'), 'research_progress_submissions', ['task_id'], unique=False)
    op.create_index(op.f('ix_research_progress_submissions_student_id'), 'research_progress_submissions', ['student_id'], unique=False)
    op.create_index(op.f('ix_research_progress_submissions_status'), 'research_progress_submissions', ['status'], unique=False)

    # 12. research_feedback_threads
    op.create_table(
        'research_feedback_threads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('milestone_id', sa.Integer(), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('faculty_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['research_tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['milestone_id'], ['research_milestones.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['research_projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['research_student_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['faculty_id'], ['faculty_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_research_feedback_threads_task_id'), 'research_feedback_threads', ['task_id'], unique=False)
    op.create_index(op.f('ix_research_feedback_threads_project_id'), 'research_feedback_threads', ['project_id'], unique=False)
    op.create_index(op.f('ix_research_feedback_threads_student_id'), 'research_feedback_threads', ['student_id'], unique=False)
    op.create_index(op.f('ix_research_feedback_threads_faculty_id'), 'research_feedback_threads', ['faculty_id'], unique=False)

    # 13. research_feedback_messages
    op.create_table(
        'research_feedback_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('thread_id', sa.Integer(), nullable=False),
        sa.Column('sender_user_id', sa.Integer(), nullable=True),
        sa.Column('sender_role', sa.String(length=30), nullable=False),
        sa.Column('message_text', sa.Text(), nullable=False),
        sa.Column('message_type', sa.String(length=30), nullable=False, server_default='comment'),
        sa.Column('action_decision', sa.String(length=30), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['thread_id'], ['research_feedback_threads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_research_feedback_messages_thread_id'), 'research_feedback_messages', ['thread_id'], unique=False)

    # 14. research_attachments
    op.create_table(
        'research_attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=True),
        sa.Column('submission_id', sa.Integer(), nullable=True),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_type', sa.String(length=100), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('storage_path', sa.String(length=500), nullable=False),
        sa.Column('storage_provider', sa.String(length=50), nullable=False, server_default='local'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('uploaded_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['research_feedback_messages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['submission_id'], ['research_progress_submissions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['research_tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['research_projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_research_attachments_project_id'), 'research_attachments', ['project_id'], unique=False)
    op.create_index(op.f('ix_research_attachments_task_id'), 'research_attachments', ['task_id'], unique=False)
    op.create_index(op.f('ix_research_attachments_submission_id'), 'research_attachments', ['submission_id'], unique=False)
    op.create_index(op.f('ix_research_attachments_message_id'), 'research_attachments', ['message_id'], unique=False)

    # 15. research_meetings
    op.create_table(
        'research_meetings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('faculty_id', sa.Integer(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('agenda', sa.Text(), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('location_or_link', sa.Text(), nullable=True),
        sa.Column('meeting_notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='scheduled'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['faculty_id'], ['faculty_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['team_id'], ['research_teams.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['research_projects.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_research_meetings_faculty_id'), 'research_meetings', ['faculty_id'], unique=False)
    op.create_index(op.f('ix_research_meetings_scheduled_at'), 'research_meetings', ['scheduled_at'], unique=False)
    op.create_index(op.f('ix_research_meetings_status'), 'research_meetings', ['status'], unique=False)

    # 16. research_meeting_participants
    op.create_table(
        'research_meeting_participants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('attendance_status', sa.String(length=20), nullable=False, server_default='invited'),
        sa.ForeignKeyConstraint(['meeting_id'], ['research_meetings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['research_student_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('meeting_id', 'student_id', name='uq_research_meeting_student')
    )
    op.create_index(op.f('ix_research_meeting_participants_meeting_id'), 'research_meeting_participants', ['meeting_id'], unique=False)
    op.create_index(op.f('ix_research_meeting_participants_student_id'), 'research_meeting_participants', ['student_id'], unique=False)

    # 17. research_notifications
    op.create_table(
        'research_notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('notification_type', sa.String(length=50), nullable=False),
        sa.Column('reference_id', sa.Integer(), nullable=True),
        sa.Column('reference_type', sa.String(length=50), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_research_notifications_user_id'), 'research_notifications', ['user_id'], unique=False)
    op.create_index(op.f('ix_research_notifications_is_read'), 'research_notifications', ['is_read'], unique=False)

    # 18. research_email_logs
    op.create_table(
        'research_email_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recipient_email', sa.String(length=120), nullable=False),
        sa.Column('recipient_user_id', sa.Integer(), nullable=True),
        sa.Column('subject', sa.String(length=200), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='queued'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('deduplication_key', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['recipient_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('deduplication_key')
    )
    op.create_index(op.f('ix_research_email_logs_recipient_email'), 'research_email_logs', ['recipient_email'], unique=False)
    op.create_index(op.f('ix_research_email_logs_status'), 'research_email_logs', ['status'], unique=False)


def downgrade():
    op.drop_table('research_email_logs')
    op.drop_table('research_notifications')
    op.drop_table('research_meeting_participants')
    op.drop_table('research_meetings')
    op.drop_table('research_attachments')
    op.drop_table('research_feedback_messages')
    op.drop_table('research_feedback_threads')
    op.drop_table('research_progress_submissions')
    op.drop_table('research_task_assignees')
    op.drop_table('research_tasks')
    op.drop_table('research_milestone_assignees')
    op.drop_table('research_milestones')
    op.drop_table('research_project_members')
    op.drop_table('research_projects')
    op.drop_table('research_team_members')
    op.drop_table('research_teams')
    op.drop_table('research_student_profiles')
    op.drop_table('faculty_profiles')
