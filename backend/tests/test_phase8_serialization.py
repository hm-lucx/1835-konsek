"""Phase 8 – (de)serialization round-trips for events, snapshots and API view."""
from __future__ import annotations

import dataclasses
import json

from eg1835.domain.actions import BuyTrainFromBank, RunTrains
from eg1835.domain.game_state import GameState
from eg1835.domain.serialization import (
    ACTION_REGISTRY,
    action_from_payload,
    action_to_payload,
    dump_snapshot,
    load_snapshot,
    state_to_jsonable,
)


class TestActionPayload:
    def test_round_trip_simple_action(self) -> None:
        action = BuyTrainFromBank(player_id="Player 1", company_id="BY", train="4+4")
        payload = action_to_payload(action)
        assert payload["type"] == "BuyTrainFromBank"
        assert payload["payload"]["train"] == "4+4"
        rebuilt = action_from_payload(payload)
        assert rebuilt == action

    def test_round_trip_list_field(self) -> None:
        action = RunTrains(player_id="Player 2", company_id="SA", route_values=[30, 60])
        rebuilt = action_from_payload(action_to_payload(action))
        assert rebuilt == action

    def test_payload_is_json_serializable(self) -> None:
        action = BuyTrainFromBank(player_id="Player 1", company_id="BY", tier=2)
        json.dumps(action_to_payload(action))  # must not raise

    def test_every_registry_entry_round_trips_its_name(self) -> None:
        for name, cls in ACTION_REGISTRY.items():
            assert cls.__name__ == name


class TestSnapshotBlob:
    def test_snapshot_round_trip_is_exact(self) -> None:
        state = GameState.initial(4)
        restored = load_snapshot(dump_snapshot(state))
        assert restored == state

    def test_snapshot_preserves_phase_6_7_fields(self) -> None:
        state = dataclasses.replace(
            GameState.initial(3),
            colored_phase=3,
            closed_privates=frozenset({"NF", "OB"}),
            bank_owed={"Player 1": 250},
        )
        restored = load_snapshot(dump_snapshot(state))
        assert restored.colored_phase == 3
        assert restored.closed_privates == frozenset({"NF", "OB"})
        assert restored.bank_owed == {"Player 1": 250}


class TestStateJson:
    def test_jsonable_is_serializable_and_converts_frozensets(self) -> None:
        state = GameState.initial(3)
        view = state_to_jsonable(state)
        # Enums become their value, frozensets become lists.
        assert view["game_loop_phase"] == "start_packet_ar"
        assert isinstance(view["trains_first_bought"], list)
        json.dumps(view)  # must not raise
