# 1835-konsek

Digitale Umsetzung des Brettspiel-Klassikers **1835** – ein Eisenbahnbauspiel im Deutschland des 19. Jahrhunderts. Spieler kaufen Aktien, bauen Streckennetze und betreiben Züge, um den höchsten Vermögenswert zu erreichen.

Die vollständigen Spielregeln sind in [1835-Spielregeln.md](1835-Spielregeln.md) dokumentiert.

---

## Architektur

```
Browser (React)  ←HTTP/WS→  FastAPI (Python)  ←→  PostgreSQL
     :5173                       :8000               :5432
```

**Kernprinzip:** Die gesamte Spiellogik lebt im Backend. Das Frontend rendert ausschließlich, was der Server in `legal_actions` liefert – keine Spielregeln im Client. Kein optimistisches Update: der Server ist immer die einzige Wahrheit.

### Backend-Schichten

```
api/            HTTP-Rand: FastAPI-Routen, Schemas, WebSocket
application/    Orchestrierung: GameService, AuthService, View-Projektion
domain/         Spiellogik: rein funktional, kein I/O
infrastructure/ Datenbankzugriff: SQLAlchemy ORM + Repository
```

### Domain (`backend/src/eg1835/domain/`)

| Datei | Inhalt |
|-------|--------|
| `game_state.py` | Immutabler Spielzustand (`GameState`) |
| `actions.py` | Alle Spielaktionen mit `validate` / `apply` |
| `fsm.py` | Phasen-State-Machine (AR → OR → Sub-Phasen) |
| `or_flow.py` | OR-Runden-Ablauf, `current_actor()`, `step()` |
| `start_packet.py` | Startpaket-Auktion |
| `tile_system.py` | Gleisplättchen & Aufwertungsregeln |
| `routing.py` | Routenfindung & Einnahmenberechnung |
| `share_price.py` | Aktienkurstafel-Logik |

### Speicherung — Event Sourcing

Spielstände werden als geordneter **Event-Log** in PostgreSQL gespeichert. Jede Aktion schreibt ein neues Event; der aktuelle Spielzustand wird durch Replay aller Events rekonstruiert.

```
events      game_id | sequence | type | payload (JSONB) | player_id
            UNIQUE(game_id, sequence)  ← optimistisches Locking (HTTP 409 bei Race)

snapshots   game_id | sequence | state_blob (bytes)
            ← alle 20 Events geschrieben, damit Replay nicht von Event 1 starten muss
```

Weitere Tabellen: `users`, `games`, `players`, `magic_tokens`

### API-Endpunkte

| Method | Pfad | Funktion |
|--------|------|----------|
| POST | `/games` | Spiel erstellen |
| POST | `/games/{id}/join` | Spieler beitreten |
| POST | `/games/{id}/actions` | Aktion ausführen |
| GET | `/games/{id}/state` | Roher GameState |
| GET | `/games/{id}/view` | UI-Projektion (Board, Stocks, Players) |
| GET | `/games/{id}/legal_actions?player_id=` | Erlaubte Züge für einen Spieler |
| GET | `/games/{id}/log` | Vollständiger Event-Log |
| GET | `/games/{id}/export` | Kompletter Export (replaybar) |
| POST | `/games/{id}/pause` | Spiel pausieren |
| POST | `/games/{id}/resume` | Spiel fortsetzen |
| WS | `/ws/games/{id}` | Echtzeit-Updates per WebSocket |
| POST | `/auth/magic-link` | Passwortlosen Login-Link anfordern |
| POST | `/auth/verify` | Magic-Link-Token prüfen |

### Frontend (`frontend/src/`)

**Stack:** React 18 + TypeScript + Vite + Zustand

Vite proxied `/api` → Backend `:8000`. Bei jedem WebSocket-Event (`state_delta`) fetcht der Store frisches View + Legal Actions.

| Komponente | Funktion |
|------------|----------|
| `HexMap.tsx` | Hex-Spielbrett (SVG) |
| `ActionBar.tsx` | Aktions-Buttons (generiert aus `legal_actions`) |
| `CompanyPanel.tsx` | Gesellschafts-Übersicht |
| `StockMarket.tsx` | Aktienkurstafel |
| `PlayerPanel.tsx` | Spieler-Vermögen |
| `TileTray.tsx` | Verfügbare Gleisplättchen |
| `PhaseGuide.tsx` | Phasen-Erklärung für den aktiven Spieler |

---

## Quickstart

```bash
# Entwicklungsumgebung starten
make dev

# Nach Code-Änderungen neu bauen
docker-compose up --build
```

Danach erreichbar unter:
- Frontend: http://localhost:5173
- API: http://localhost:8000
- API-Docs: http://localhost:8000/docs

---

## Häufige Befehle

```bash
make test      # Tests (pytest + tsc)
make lint      # Linter (ruff + mypy + eslint)
make format    # Formatter (ruff + prettier)
make migrate   # Datenbankmigrationen (alembic upgrade head)
make clean     # Docker-Container und Volumes entfernen
```

---

## Entwicklungsstand

Die Implementierung ist in Phasen aufgeteilt. Offene Phasen als GitHub Issues:

| Phase | Issue | Inhalt |
|-------|-------|--------|
| 6 | [#7](../../issues/7) | Operationsrunden-Logik (Bauen, Fahren, Lokkauf, Phasenwechsel) |
| 7 | [#8](../../issues/8) | Sonderfälle: Preußen, Privatbahnen, Bankrott, Baden-Heimat |
| 8 | [#9](../../issues/9) | Persistenz & API (Event-Sourcing, WebSocket, Spielende) |
| 9 | [#10](../../issues/10) | Frontend-Grundgerüst (HexMap, Aktienkurstafel, ActionBar) |
| 10 | [#11](../../issues/11) | Multiplayer-Features (Lobby, Auth, Web Push) |
| 11 | [#12](../../issues/12) | Optionale Regeln (Konfig-Flags) |
