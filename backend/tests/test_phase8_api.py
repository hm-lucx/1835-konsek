"""Phase 8 – REST + WebSocket API.

The app builds its own engine inside the lifespan (same event loop as the
requests), backed by a temporary SQLite file.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from eg1835.api.app import create_app


@pytest.fixture
def client(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/api.db")
    with TestClient(create_app()) as test_client:
        yield test_client


def _create_game(client: TestClient, num_players: int = 3) -> int:
    response = client.post("/games", json={"num_players": num_players})
    assert response.status_code == 201
    game_id: int = response.json()["game_id"]
    return game_id


class TestRestEndpoints:
    def test_health_still_works(self, client: TestClient) -> None:
        assert client.get("/health").json()["status"] == "ok"

    def test_create_and_get_state(self, client: TestClient) -> None:
        game_id = _create_game(client)
        response = client.get(f"/games/{game_id}/state")
        assert response.status_code == 200
        body = response.json()
        assert body["sequence"] == 0
        assert body["state"]["game_loop_phase"] == "start_packet_ar"

    def test_unknown_game_returns_404(self, client: TestClient) -> None:
        assert client.get("/games/999/state").status_code == 404

    def test_join_game(self, client: TestClient) -> None:
        game_id = _create_game(client)
        response = client.post(
            f"/games/{game_id}/join", json={"user_email": "p2@example.com", "seat": 1}
        )
        assert response.status_code == 204

    def test_submit_action_and_log(self, client: TestClient) -> None:
        game_id = _create_game(client)
        response = client.post(
            f"/games/{game_id}/actions",
            json={
                "player_id": "Player 1",
                "expected_seq": 0,
                "type": "BuyStartItem",
                "payload": {"player_id": "Player 1", "item_id": "NF"},
            },
        )
        assert response.status_code == 200
        assert response.json()["sequence"] == 1

        log = client.get(f"/games/{game_id}/log").json()
        assert len(log["events"]) == 1
        assert log["events"][0]["type"] == "BuyStartItem"

    def test_idempotent_submit_returns_409(self, client: TestClient) -> None:
        game_id = _create_game(client)
        body = {
            "player_id": "Player 1",
            "expected_seq": 0,
            "type": "BuyStartItem",
            "payload": {"player_id": "Player 1", "item_id": "NF"},
        }
        assert client.post(f"/games/{game_id}/actions", json=body).status_code == 200
        # Same expected_seq again → conflict.
        assert client.post(f"/games/{game_id}/actions", json=body).status_code == 409

    def test_invalid_action_returns_422(self, client: TestClient) -> None:
        game_id = _create_game(client)
        # Buying a train during the start-packet AR is illegal.
        response = client.post(
            f"/games/{game_id}/actions",
            json={
                "player_id": "Player 1",
                "expected_seq": 0,
                "type": "BuyTrainFromBank",
                "payload": {"player_id": "Player 1", "company_id": "BY", "tier": 1},
            },
        )
        assert response.status_code == 422


class TestWebSocket:
    def test_action_broadcasts_state_delta(self, client: TestClient) -> None:
        game_id = _create_game(client)
        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            client.post(
                f"/games/{game_id}/actions",
                json={
                    "player_id": "Player 1",
                    "expected_seq": 0,
                    "type": "BuyStartItem",
                    "payload": {"player_id": "Player 1", "item_id": "NF"},
                },
            )
            message = ws.receive_json()
            assert message["event"] == "state_delta"
            assert message["sequence"] == 1
            assert message["state"]["game_loop_phase"] == "start_packet_ar"
