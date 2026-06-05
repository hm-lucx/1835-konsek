"""Turn-change notification seam (Phase 10, Teil 2).

The game service emits a turn-change event whenever the acting player changes.
Concrete transports (Web Push via ``pywebpush``, email via Resend) implement
:class:`Notifier`; the default :class:`NullNotifier` does nothing and
:class:`RecordingNotifier` captures events for tests.  Wiring a live transport
is a deployment concern and intentionally left out of this layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class Notifier(Protocol):
    """Receives a notification when it becomes a player's turn."""

    def turn_changed(self, game_id: int, player_id: str, sequence: int) -> None: ...


class NullNotifier:
    """Default no-op notifier."""

    def turn_changed(self, game_id: int, player_id: str, sequence: int) -> None:
        return None


@dataclass
class TurnEvent:
    game_id: int
    player_id: str
    sequence: int


@dataclass
class RecordingNotifier:
    """Test/dev notifier that records every turn-change event."""

    events: list[TurnEvent] = field(default_factory=list)

    def turn_changed(self, game_id: int, player_id: str, sequence: int) -> None:
        self.events.append(TurnEvent(game_id, player_id, sequence))
