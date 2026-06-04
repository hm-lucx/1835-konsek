"""Initial schema: users, games, players, events, snapshots.

Revision ID: 0001_initial
Revises:
Create Date: Phase 8 (issue #9).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

_JSON = JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=320), nullable=False, unique=True),
    )
    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("num_players", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "game_id",
            sa.Integer(),
            sa.ForeignKey("games.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seat", sa.Integer(), nullable=False),
        sa.UniqueConstraint("game_id", "seat", name="uq_player_seat"),
    )
    op.create_index("ix_players_game_id", "players", ["game_id"])
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "game_id",
            sa.Integer(),
            sa.ForeignKey("games.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("payload", _JSON, nullable=False),
        sa.Column("player_id", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("game_id", "sequence", name="uq_event_sequence"),
    )
    op.create_index("ix_events_game_id", "events", ["game_id"])
    op.create_table(
        "snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "game_id",
            sa.Integer(),
            sa.ForeignKey("games.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("state_blob", sa.LargeBinary(), nullable=False),
        sa.UniqueConstraint("game_id", "sequence", name="uq_snapshot_sequence"),
    )
    op.create_index("ix_snapshots_game_id", "snapshots", ["game_id"])


def downgrade() -> None:
    op.drop_table("snapshots")
    op.drop_table("events")
    op.drop_table("players")
    op.drop_table("games")
    op.drop_table("users")
