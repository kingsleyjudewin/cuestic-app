"""add_email_to_members

Revision ID: a1b2c3d4e5f6
Revises: 9c460919d32c
Create Date: 2026-10-30 21:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '9c460919d32c'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = [c['name'] for c in inspector.get_columns('members')]
    existing_indexes = [i['name'] for i in inspector.get_indexes('members')]

    with op.batch_alter_table('members', schema=None) as batch_op:
        if 'email' not in existing_cols:
            batch_op.add_column(sa.Column('email', sa.String(length=120), nullable=True))
        if 'ix_members_email' not in existing_indexes:
            batch_op.create_index(batch_op.f('ix_members_email'), ['email'], unique=False)


def downgrade():
    with op.batch_alter_table('members', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_members_email'))
        batch_op.drop_column('email')
