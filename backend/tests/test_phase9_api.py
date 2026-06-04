"""Phase 9 – view / legal-actions endpoints and snake_case action submission."""
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


def _create_game(client: TestClient) -> int:
    response = client.post("/games", json={"num_players": 3})
    assert response.status_code == 201
    game_id: int = response.json()["game_id"]
    return game_id


class TestViewEndpoint:
    def test_view_returns_board_and_companies(self, client: TestClient) -> None:
        game_id = _create_game(client)
        view = client.get(f"/games/{game_id}/view").json()
        assert view["board"]["positions"]["3,0"]["location_name"] == "Hamburg"
        company_ids = {c["id"] for c in view["companies"]}
        assert {"BY", "SA", "PR"} <= company_ids

    def test_view_unknown_game_404(self, client: TestClient) -> None:
        assert client.get("/games/999/view").status_code == 404


class TestLegalActionsEndpoint:
    def test_legal_actions_lists_buy_start_item(self, client: TestClient) -> None:
        game_id = _create_game(client)
        response = client.get(
            f"/games/{game_id}/legal_actions", params={"player_id": "Player 1"}
        )
        assert response.status_code == 200
        types = {a["type"] for a in response.json()["actions"]}
        assert "buy_start_item" in types


class TestSnakeCaseSubmission:
    def test_submit_accepts_snake_case_type(self, client: TestClient) -> None:
        game_id = _create_game(client)
        response = client.post(
            f"/games/{game_id}/actions",
            json={
                "player_id": "Player 1",
                "expected_seq": 0,
                "type": "buy_start_item",  # snake_case from the frontend
                "payload": {"player_id": "Player 1", "item_id": "NF"},
            },
        )
        assert response.status_code == 200
        assert response.json()["sequence"] == 1
        # The view reflects the purchase.
        view = client.get(f"/games/{game_id}/view").json()
        player1 = next(p for p in view["players"] if p["player_id"] == "Player 1")
        assert player1["cash"] == 500  # 600 − 100 (NF)
