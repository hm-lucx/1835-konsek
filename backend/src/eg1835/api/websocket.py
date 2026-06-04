"""WebSocket connection manager for per-game state broadcasts (Phase 8)."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Tracks connected clients per game and broadcasts state deltas."""

    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, game_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.setdefault(game_id, set()).add(websocket)

    async def disconnect(self, game_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(game_id)
            if conns is not None:
                conns.discard(websocket)
                if not conns:
                    del self._connections[game_id]

    async def broadcast(self, game_id: int, message: dict[str, Any]) -> None:
        """Send ``message`` to every client connected to ``game_id``.

        Connections that fail to receive are dropped silently.
        """
        async with self._lock:
            targets = list(self._connections.get(game_id, set()))
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 - drop broken sockets
                dead.append(ws)
        for ws in dead:
            await self.disconnect(game_id, ws)

    def connection_count(self, game_id: int) -> int:
        return len(self._connections.get(game_id, set()))
