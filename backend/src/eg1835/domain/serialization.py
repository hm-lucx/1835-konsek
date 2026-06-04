"""(De)serialization for events, snapshots and API state (Phase 8).

Two distinct representations:

* **Events** are stored as JSONB and must round-trip an action exactly.  An
  action is encoded as ``{"type": <class name>, "payload": <field dict>}`` and
  rebuilt through :data:`ACTION_REGISTRY`.
* **Snapshots** are an opaque ``BYTEA`` blob; we use :func:`pickle` for an exact,
  fast round-trip of the immutable :class:`GameState` (internal, never sent to a
  client).

:func:`state_to_jsonable` produces a plain JSON-friendly view of the state for
the read-only ``GET /state`` endpoint (frozensets → sorted lists, enums → their
value); it is not used for replay.
"""
from __future__ import annotations

import dataclasses
import pickle
from enum import Enum
from typing import Any

from . import actions as _actions
from .game_state import GameState

# ---------------------------------------------------------------------------
# Action registry (event payloads)
# ---------------------------------------------------------------------------

# Every concrete action class, keyed by its name.  New actions must be added
# here to be replayable.
_ACTION_CLASSES = (
    _actions.BuyStartItem,
    _actions.BuyShareFromBank,
    _actions.BuyShareFromPool,
    _actions.Nationalize,
    _actions.SellShares,
    _actions.Pass,
    _actions.LayTile,
    _actions.UpgradeTile,
    _actions.PlaceStation,
    _actions.RunTrains,
    _actions.DeclareDividend,
    _actions.WithholdDividend,
    _actions.BuyTrainFromBank,
    _actions.BuyTrainFromPool,
    _actions.BuyTrainFromCompany,
    _actions.BuyMandatoryTrain,
    _actions.OpenPreussen,
    _actions.ConvertToPreussenShare,
    _actions.ChooseBadenHomeStation,
    _actions.UseNFAbility,
    _actions.UseOBAbility,
    _actions.UsePFBuildAbility,
    _actions.UsePFStationAbility,
)

ACTION_REGISTRY: dict[str, type] = {cls.__name__: cls for cls in _ACTION_CLASSES}

# Public (snake_case) action names used by the API / frontend.  Explicit (not
# auto-derived) so acronyms read correctly, e.g. UseNFAbility → use_nf_ability.
ACTION_SNAKE_NAMES: dict[str, str] = {
    "BuyStartItem": "buy_start_item",
    "BuyShareFromBank": "buy_share_from_bank",
    "BuyShareFromPool": "buy_share_from_pool",
    "Nationalize": "nationalize",
    "SellShares": "sell_shares",
    "Pass": "pass",
    "LayTile": "lay_tile",
    "UpgradeTile": "upgrade_tile",
    "PlaceStation": "place_station",
    "RunTrains": "run_trains",
    "DeclareDividend": "declare_dividend",
    "WithholdDividend": "withhold_dividend",
    "BuyTrainFromBank": "buy_train_from_bank",
    "BuyTrainFromPool": "buy_train_from_pool",
    "BuyTrainFromCompany": "buy_train_from_company",
    "BuyMandatoryTrain": "buy_mandatory_train",
    "OpenPreussen": "open_preussen",
    "ConvertToPreussenShare": "convert_to_preussen_share",
    "ChooseBadenHomeStation": "choose_baden_home_station",
    "UseNFAbility": "use_nf_ability",
    "UseOBAbility": "use_ob_ability",
    "UsePFBuildAbility": "use_pf_build_ability",
    "UsePFStationAbility": "use_pf_station_ability",
}

# Reverse map plus the PascalCase names, so the API accepts either spelling.
_SNAKE_TO_CLASS: dict[str, type] = {
    snake: ACTION_REGISTRY[name] for name, snake in ACTION_SNAKE_NAMES.items()
}


def snake_name(action_type: str) -> str:
    """Public snake_case name for a PascalCase action class name."""
    return ACTION_SNAKE_NAMES.get(action_type, action_type)


def resolve_action_class(action_type: str) -> type | None:
    """Resolve an action class from either its PascalCase or snake_case name."""
    return ACTION_REGISTRY.get(action_type) or _SNAKE_TO_CLASS.get(action_type)


def action_to_payload(action: Any) -> dict[str, Any]:
    """Encode an action as a JSON-serializable ``{"type", "payload"}`` dict."""
    return {
        "type": type(action).__name__,
        "payload": dataclasses.asdict(action),
    }


def action_from_payload(data: dict[str, Any]) -> Any:
    """Rebuild an action from its ``{"type", "payload"}`` dict.

    ``type`` may be the PascalCase class name (event log) or the snake_case API
    name (frontend submissions).
    """
    cls = resolve_action_class(data["type"])
    if cls is None:
        raise ValueError(f"Unknown action type: {data['type']}")
    return cls(**data["payload"])


def action_type_name(action: Any) -> str:
    """Class name of an action (used for the events.type column)."""
    return type(action).__name__


# ---------------------------------------------------------------------------
# Snapshots (opaque BYTEA blob)
# ---------------------------------------------------------------------------


def dump_snapshot(state: GameState) -> bytes:
    """Serialize a GameState to an opaque snapshot blob (exact round-trip)."""
    return pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL)


def load_snapshot(blob: bytes) -> GameState:
    """Deserialize a snapshot blob back into a GameState."""
    state = pickle.loads(blob)  # noqa: S301 - internal, trusted blob
    if not isinstance(state, GameState):  # pragma: no cover - defensive
        raise TypeError("Snapshot blob did not contain a GameState")
    return state


# ---------------------------------------------------------------------------
# JSON view of the state (read-only API)
# ---------------------------------------------------------------------------


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, frozenset | set):
        return sorted(value, key=str)
    if isinstance(value, tuple | list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


def state_to_jsonable(state: GameState) -> dict[str, Any]:
    """Plain JSON-friendly view of the state for the read-only API."""
    return {f.name: _jsonable(getattr(state, f.name)) for f in dataclasses.fields(state)}
