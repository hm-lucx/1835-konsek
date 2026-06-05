"""Pydantic request/response models for the REST API (Phase 8)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class CreateGameRequest(BaseModel):
    num_players: int
    creator_email: str | None = None


class CreateGameResponse(BaseModel):
    game_id: int


class JoinGameRequest(BaseModel):
    user_email: str
    seat: int


class SubmitActionRequest(BaseModel):
    player_id: str
    expected_seq: int
    type: str
    payload: dict[str, Any] = {}


class SubmitActionResponse(BaseModel):
    sequence: int
    state: dict[str, Any]


class StateResponse(BaseModel):
    sequence: int
    state: dict[str, Any]


class LogEntry(BaseModel):
    sequence: int
    type: str
    player_id: str | None
    payload: dict[str, Any]


class LogResponse(BaseModel):
    events: list[LogEntry]


class MagicLinkRequest(BaseModel):
    email: str


class VerifyTokenRequest(BaseModel):
    token: str


class AuthenticatedUserResponse(BaseModel):
    user_id: int
    email: str
