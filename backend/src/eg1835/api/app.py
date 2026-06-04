"""FastAPI application factory wiring the REST + WebSocket API (Phase 8).

The domain validates; the API only (de)serialises and persists.  Every accepted
action is broadcast to all WebSocket clients of the game as a ``state_delta``.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from ..application.game_service import (
    ActionValidationError,
    ConflictError,
    GameNotFoundError,
    GameService,
)
from ..domain.serialization import action_from_payload, state_to_jsonable
from ..infrastructure.db import Base, create_engine, create_session_factory
from .schemas import (
    CreateGameRequest,
    CreateGameResponse,
    JoinGameRequest,
    LogResponse,
    StateResponse,
    SubmitActionRequest,
    SubmitActionResponse,
)
from .websocket import ConnectionManager


def _build_router(app: FastAPI) -> APIRouter:
    router = APIRouter()

    def service() -> GameService:
        svc: GameService = app.state.game_service
        return svc

    def manager() -> ConnectionManager:
        mgr: ConnectionManager = app.state.connection_manager
        return mgr

    @router.post("/games", response_model=CreateGameResponse, status_code=201)
    async def create_game(req: CreateGameRequest) -> CreateGameResponse:
        game_id = await service().create_game(req.num_players, req.creator_email)
        return CreateGameResponse(game_id=game_id)

    @router.post("/games/{game_id}/join", status_code=204)
    async def join_game(game_id: int, req: JoinGameRequest) -> None:
        try:
            await service().join_game(game_id, req.user_email, req.seat)
        except GameNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/games/{game_id}/actions", response_model=SubmitActionResponse)
    async def submit_action(game_id: int, req: SubmitActionRequest) -> SubmitActionResponse:
        try:
            action = action_from_payload({"type": req.type, "payload": req.payload})
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            result = await service().submit_action(
                game_id, req.player_id, action, req.expected_seq
            )
        except GameNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ActionValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        state_json = state_to_jsonable(result.state)
        await manager().broadcast(
            game_id,
            {"event": "state_delta", "sequence": result.sequence, "state": state_json},
        )
        return SubmitActionResponse(sequence=result.sequence, state=state_json)

    @router.get("/games/{game_id}/state", response_model=StateResponse)
    async def get_state(game_id: int) -> StateResponse:
        try:
            seq = await service().current_sequence(game_id)
            state = await service().get_state(game_id)
        except GameNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return StateResponse(sequence=seq, state=state_to_jsonable(state))

    @router.get("/games/{game_id}/log", response_model=LogResponse)
    async def get_log(game_id: int) -> LogResponse:
        try:
            events = await service().get_log(game_id)
        except GameNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return LogResponse(events=events)  # type: ignore[arg-type]

    @router.get("/games/{game_id}/view")
    async def get_view(game_id: int) -> dict[str, object]:
        try:
            return await service().get_view(game_id)
        except GameNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/games/{game_id}/legal_actions")
    async def get_legal_actions(game_id: int, player_id: str) -> dict[str, object]:
        try:
            return await service().get_legal_actions(game_id, player_id)
        except GameNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.websocket("/ws/games/{game_id}")
    async def game_ws(websocket: WebSocket, game_id: int) -> None:
        mgr = manager()
        await mgr.connect(game_id, websocket)
        try:
            while True:
                await websocket.receive_text()  # keepalive; server only broadcasts
        except WebSocketDisconnect:
            await mgr.disconnect(game_id, websocket)

    return router


def create_app(service: GameService | None = None) -> FastAPI:
    """Build the FastAPI app.

    When ``service`` is None the app creates its own engine from ``DATABASE_URL``
    on startup and creates the schema (convenient for dev; production uses the
    Alembic migration).  Tests inject a service backed by an in-memory database.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if getattr(app.state, "game_service", None) is None:
            engine = create_engine()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            app.state.engine = engine
            app.state.game_service = GameService(create_session_factory(engine))
        yield

    app = FastAPI(title="1835 Konsek", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.game_service = service
    app.state.connection_manager = ConnectionManager()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "1835-konsek"}

    app.include_router(_build_router(app))
    return app
