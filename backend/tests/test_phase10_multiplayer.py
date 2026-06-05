"""Phase 10 (Teil 2) – multiplayer enablement: auth, lobby, pause, export, notify."""
from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import cast

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from eg1835.api.app import create_app
from eg1835.application.auth_service import AuthError, AuthService, RecordingEmailSender
from eg1835.application.game_service import GamePausedError, GameService
from eg1835.application.notifier import RecordingNotifier
from eg1835.domain.actions import BuyStartItem
from eg1835.infrastructure.db import Base, create_session_factory

Env = tuple[GameService, AuthService, RecordingNotifier, RecordingEmailSender]


@pytest_asyncio.fixture
async def env() -> AsyncIterator[Env]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sf = create_session_factory(engine)
    notifier = RecordingNotifier()
    email = RecordingEmailSender()
    yield GameService(sf, notifier=notifier), AuthService(sf, email_sender=email), notifier, email
    await engine.dispose()


class TestMagicLinkAuth:
    async def test_request_then_verify_returns_user(self, env: Env) -> None:
        _, auth, _, email = env
        await auth.request_magic_link("alice@example.com")
        assert len(email.sent) == 1
        sent_email, token = email.sent[0]
        assert sent_email == "alice@example.com"

        user = await auth.verify(token)
        assert user.email == "alice@example.com"
        assert user.user_id > 0

    async def test_token_is_single_use(self, env: Env) -> None:
        _, auth, _, email = env
        await auth.request_magic_link("bob@example.com")
        token = email.sent[0][1]
        await auth.verify(token)
        with pytest.raises(AuthError):
            await auth.verify(token)

    async def test_unknown_token_rejected(self, env: Env) -> None:
        _, auth, _, _ = env
        with pytest.raises(AuthError):
            await auth.verify("not-a-real-token")


class TestNotifier:
    async def test_turn_change_notifies_next_actor(self, env: Env) -> None:
        service, _, notifier, _ = env
        game_id = await service.create_game(3)
        await service.submit_action(
            game_id, "Player 1", BuyStartItem(player_id="Player 1", item_id="NF"), 0
        )
        # After Player 1 acts the turn passes to Player 2.
        assert notifier.events[-1].game_id == game_id
        assert notifier.events[-1].player_id == "Player 2"


class TestPauseResume:
    async def test_paused_game_rejects_actions(self, env: Env) -> None:
        service, _, _, _ = env
        game_id = await service.create_game(3)
        await service.set_status(game_id, "paused")
        with pytest.raises(GamePausedError):
            await service.submit_action(
                game_id, "Player 1", BuyStartItem(player_id="Player 1", item_id="NF"), 0
            )
        # Resuming re-enables play.
        await service.set_status(game_id, "active")
        result = await service.submit_action(
            game_id, "Player 1", BuyStartItem(player_id="Player 1", item_id="NF"), 0
        )
        assert result.sequence == 1


class TestLobbyAndExport:
    async def test_lobby_lists_games_with_open_seats(self, env: Env) -> None:
        service, _, _, _ = env
        game_id = await service.create_game(3, creator_email="host@example.com")
        games = await service.list_games()
        entry = next(g for g in games if g["game_id"] == game_id)
        assert entry["seats_taken"] == 1
        assert entry["open"] is True

    async def test_export_contains_events(self, env: Env) -> None:
        service, _, _, _ = env
        game_id = await service.create_game(3)
        await service.submit_action(
            game_id, "Player 1", BuyStartItem(player_id="Player 1", item_id="NF"), 0
        )
        export = await service.export_game(game_id)
        game = cast("dict[str, object]", export["game"])
        events = cast("list[object]", export["events"])
        assert game["id"] == game_id
        assert len(events) == 1


# --- API-level: spectator WebSocket + auth/lobby endpoints -------------------


@pytest.fixture
def client(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/mp.db")
    with TestClient(create_app()) as test_client:
        yield test_client


class TestApi:
    def test_lobby_endpoint(self, client: TestClient) -> None:
        client.post("/games", json={"num_players": 3})
        body = client.get("/games").json()
        assert len(body["games"]) >= 1

    def test_auth_endpoints_round_trip(self, client: TestClient) -> None:
        assert client.post("/auth/magic-link", json={"email": "c@d.e"}).status_code == 202
        # Without a real email transport the token is not exposed; verifying a
        # bogus token must fail cleanly.
        assert client.post("/auth/verify", json={"token": "bogus"}).status_code == 401

    def test_pause_blocks_actions_via_api(self, client: TestClient) -> None:
        game_id = client.post("/games", json={"num_players": 3}).json()["game_id"]
        assert client.post(f"/games/{game_id}/pause").status_code == 204
        response = client.post(
            f"/games/{game_id}/actions",
            json={
                "player_id": "Player 1",
                "expected_seq": 0,
                "type": "buy_start_item",
                "payload": {"player_id": "Player 1", "item_id": "NF"},
            },
        )
        assert response.status_code == 409

    def test_spectator_receives_broadcast(self, client: TestClient) -> None:
        game_id = client.post("/games", json={"num_players": 3}).json()["game_id"]
        # A read-only spectator just connects to the game socket.
        with client.websocket_connect(f"/ws/games/{game_id}") as spectator:
            client.post(
                f"/games/{game_id}/actions",
                json={
                    "player_id": "Player 1",
                    "expected_seq": 0,
                    "type": "buy_start_item",
                    "payload": {"player_id": "Player 1", "item_id": "NF"},
                },
            )
            message = spectator.receive_json()
            assert message["event"] == "state_delta"
