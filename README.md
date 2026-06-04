# 1835-konsek

Digitale Umsetzung des Brettspiel-Klassikers **1835** – ein Eisenbahnbauspiel im Deutschland des 19. Jahrhunderts. Spieler kaufen Aktien, bauen Streckennetze und betreiben Züge, um den höchsten Vermögenswert zu erreichen.

Die vollständigen Spielregeln sind in [1835-Spielregeln.md](1835-Spielregeln.md) dokumentiert.

---

## Architektur

```
frontend/   React 18 + TypeScript + Vite  →  :5173
backend/    FastAPI + Python 3.12         →  :8000
postgres    PostgreSQL 16                 →  :5432
redis       Redis 7                       →  :6379
```

**Kernprinzip:** Die gesamte Spiellogik lebt im Backend. Das Frontend rendert ausschließlich, was der Server in `legal_actions` liefert – keine Spielregeln im Client.

**Backend-Domäne** (`backend/src/eg1835/domain/`):

| Datei | Inhalt |
|-------|--------|
| `actions.py` | Alle Spielaktionen mit `validate` / `apply` |
| `fsm.py` | Spielphasen-State-Machine (AR, OR, Sub-Phasen) |
| `game_state.py` | Immutabler Spielzustand |
| `routing.py` | Routenfindung & Einnahmenberechnung |
| `tile_system.py` | Gleisplättchen & Aufwertungsregeln |
| `share_price.py` | Aktienkurstafel-Logik |
| `start_packet.py` | Startpaket-Auktion |

Spielstand wird als **Event-Log** in Postgres gespeichert; Snapshots alle ~20 Events für schnelles Replay.

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
