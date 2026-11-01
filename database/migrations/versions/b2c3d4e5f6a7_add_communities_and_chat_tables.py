"""add_communities_and_chat_tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-30 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'communities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('slug', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon', sa.String(length=255), nullable=True),
        sa.Column('color', sa.String(length=20), nullable=True),
        sa.Column('team_id', sa.Integer(), nullable=True),
        sa.Column('is_team_restricted', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_communities_name'), 'communities', ['name'], unique=False)
    op.create_index(op.f('ix_communities_slug'), 'communities', ['slug'], unique=True)
    op.create_index(op.f('ix_communities_team_id'), 'communities', ['team_id'], unique=False)
    op.create_index(op.f('ix_communities_created_by'), 'communities', ['created_by'], unique=False)

    op.create_table(
        'community_channels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('community_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('topic', sa.String(length=255), nullable=True),
        sa.Column('channel_type', sa.String(length=30), nullable=False, server_default='text'),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_private', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_community_channels_community_id'), 'community_channels', ['community_id'], unique=False)

    op.create_table(
        'community_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('community_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=30), nullable=False, server_default='member'),
        sa.Column('nickname', sa.String(length=100), nullable=True),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('community_id', 'user_id', name='uq_community_user')
    )
    op.create_index(op.f('ix_community_members_community_id'), 'community_members', ['community_id'], unique=False)
    op.create_index(op.f('ix_community_members_user_id'), 'community_members', ['user_id'], unique=False)

    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('community_id', sa.Integer(), nullable=False),
        sa.Column('channel_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('sender_name', sa.String(length=120), nullable=False),
        sa.Column('sender_role', sa.String(length=30), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('message_type', sa.String(length=30), nullable=False, server_default='text'),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('attachment_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['channel_id'], ['community_channels.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], ['chat_messages.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_messages_community_id'), 'chat_messages', ['community_id'], unique=False)
    op.create_index(op.f('ix_chat_messages_channel_id'), 'chat_messages', ['channel_id'], unique=False)
    op.create_index(op.f('ix_chat_messages_user_id'), 'chat_messages', ['user_id'], unique=False)
    op.create_index(op.f('ix_chat_messages_created_at'), 'chat_messages', ['created_at'], unique=False)


def downgrade():
    op.drop_table('chat_messages')
    op.drop_table('community_members')
    op.drop_table('community_channels')
    op.drop_table('communities')
