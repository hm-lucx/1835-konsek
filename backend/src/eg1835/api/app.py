"""FastAPI application factory wiring the REST + WebSocket API (Phase 8).

The domain validates; the API only (de)serialises and persists.  Every accepted
action is broadcast to all WebSocket clients of the game as a ``state_delta``.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from ..application.auth_service import AuthError, AuthService
from ..application.game_service import (
    ActionValidationError,
    ConflictError,
    GameNotFoundError,
    GamePausedError,
    GameService,
    TurnError,
)
from ..domain.serialization import action_from_payload, state_to_jsonable
from ..infrastructure.db import Base, create_engine, create_session_factory
from .schemas import (
    AuthenticatedUserResponse,
    CreateGameRequest,
    CreateGameResponse,
    JoinGameRequest,
    LogResponse,
    MagicLinkRequest,
    StateResponse,
    SubmitActionRequest,
    SubmitActionResponse,
    VerifyTokenRequest,
)
from .websocket import ConnectionManager


def _auth(app: FastAPI) -> AuthService:
    auth: AuthService = app.state.auth_service
    return auth


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
        except TurnError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except GamePausedError as exc:
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

    @router.get("/games")
    async def list_games() -> dict[str, object]:
        return {"games": await service().list_games()}

    @router.get("/games/{game_id}/export")
    async def export_game(game_id: int) -> dict[str, object]:
        try:
            return await service().export_game(game_id)
        except GameNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/games/{game_id}/pause", status_code=204)
    async def pause_game(game_id: int) -> None:
        try:
            await service().set_status(game_id, "paused")
        except GameNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/games/{game_id}/resume", status_code=204)
    async def resume_game(game_id: int) -> None:
        try:
            await service().set_status(game_id, "active")
        except GameNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/auth/magic-link", status_code=202)
    async def request_magic_link(req: MagicLinkRequest) -> dict[str, bool]:
        await _auth(app).request_magic_link(req.email)
        return {"sent": True}

    @router.post("/auth/verify", response_model=AuthenticatedUserResponse)
    async def verify_token(req: VerifyTokenRequest) -> AuthenticatedUserResponse:
        try:
            user = await _auth(app).verify(req.token)
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        return AuthenticatedUserResponse(user_id=user.user_id, email=user.email)

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


def create_app(
    service: GameService | None = None, auth: AuthService | None = None
) -> FastAPI:
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
            session_factory = create_session_factory(engine)
            app.state.engine = engine
            app.state.game_service = GameService(session_factory)
            app.state.auth_service = AuthService(session_factory)
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
    app.state.auth_service = auth
    app.state.connection_manager = ConnectionManager()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "1835-konsek"}

    app.include_router(_build_router(app))
    return app
