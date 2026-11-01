"""make_member_class_name_nullable

Revision ID: c1d2e3f4a5b6
Revises: b2c3d4e5f6a7
Create Date: 2026-11-01 12:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1d2e3f4a5b6'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('members', schema=None) as batch_op:
        batch_op.alter_column(
            'class_name',
            existing_type=sa.VARCHAR(length=50),
            nullable=True,
        )


def downgrade():
    with op.batch_alter_table('members', schema=None) as batch_op:
        batch_op.alter_column(
            'class_name',
            existing_type=sa.VARCHAR(length=50),
            nullable=False,
        )
