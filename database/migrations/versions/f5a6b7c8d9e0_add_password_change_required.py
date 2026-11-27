"""Add users.password_change_required and users.password_changed_at.

Schema only. Additive and non-destructive: both columns are added with safe defaults
(false / NULL), so every existing account keeps working exactly as before after this upgrade.

Marking existing accounts as requiring a new password is a separate, explicit step that an
operator runs after checking the preview:
    flask require-password-change            # dry run: counts per role
    flask require-password-change --confirm  # apply

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-11-27
"""
from alembic import op
import sqlalchemy as sa


revision = "f5a6b7c8d9e0"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("password_change_required", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    # Removes only the two columns added above; no other data is touched.
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("password_changed_at")
        batch_op.drop_column("password_change_required")
