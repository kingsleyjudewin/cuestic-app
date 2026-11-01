"""add_mc_team_and_scripts

Revision ID: d3e4f5a6b7c8
Revises: c1d2e3f4a5b6
Create Date: 2026-11-01 12:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3e4f5a6b7c8'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    # 1. mc_scripts table
    op.create_table(
        'mc_scripts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=True),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='draft'),
        sa.Column('event_type', sa.String(length=100), nullable=True),
        sa.Column('venue', sa.String(length=200), nullable=True),
        sa.Column('event_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration', sa.String(length=50), nullable=True),
        sa.Column('language', sa.String(length=50), nullable=False, server_default='English'),
        sa.Column('tone', sa.String(length=50), nullable=False, server_default='Formal'),
        sa.Column('number_of_anchors', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('anchors_json', sa.Text(), nullable=True),
        sa.Column('chief_guest_details', sa.Text(), nullable=True),
        sa.Column('faculty_speaker_details', sa.Text(), nullable=True),
        sa.Column('event_schedule', sa.Text(), nullable=True),
        sa.Column('segments_json', sa.Text(), nullable=True),
        sa.Column('full_script_content', sa.Text(), nullable=True),
        sa.Column('generated_docx_path', sa.String(length=500), nullable=True),
        sa.Column('drive_file_id', sa.String(length=255), nullable=True),
        sa.Column('drive_folder_id', sa.String(length=255), nullable=True),
        sa.Column('drive_web_view_link', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mc_scripts_created_by'), 'mc_scripts', ['created_by'], unique=False)
    op.create_index(op.f('ix_mc_scripts_event_id'), 'mc_scripts', ['event_id'], unique=False)
    op.create_index(op.f('ix_mc_scripts_task_id'), 'mc_scripts', ['task_id'], unique=False)
    op.create_index(op.f('ix_mc_scripts_status'), 'mc_scripts', ['status'], unique=False)
    op.create_index(op.f('ix_mc_scripts_drive_file_id'), 'mc_scripts', ['drive_file_id'], unique=False)

    # 2. mc_script_reviews table
    op.create_table(
        'mc_script_reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('script_id', sa.Integer(), nullable=False),
        sa.Column('reviewer_id', sa.Integer(), nullable=True),
        sa.Column('decision', sa.String(length=30), nullable=False),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['script_id'], ['mc_scripts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mc_script_reviews_script_id'), 'mc_script_reviews', ['script_id'], unique=False)
    op.create_index(op.f('ix_mc_script_reviews_reviewer_id'), 'mc_script_reviews', ['reviewer_id'], unique=False)

    # 3. mc_drive_folder_mappings table
    op.create_table(
        'mc_drive_folder_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=60), nullable=False),
        sa.Column('drive_folder_id', sa.String(length=255), nullable=True),
        sa.Column('drive_folder_name', sa.String(length=255), nullable=True),
        sa.Column('configured_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['configured_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('category')
    )


def downgrade():
    op.drop_table('mc_drive_folder_mappings')
    op.drop_table('mc_script_reviews')
    op.drop_table('mc_scripts')
