"""Magic-link auth tokens (Phase 10, Teil 2).

Revision ID: 0002_magic_tokens
Revises: 0001_initial
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_magic_tokens"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "magic_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("token", sa.String(length=64), nullable=False, unique=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table("magic_tokens")
