# 1835 Konsek

Digitale Umsetzung des Brettspiel-Klassikers **1835** – ein Eisenbahnbauspiel im Deutschland des 19. Jahrhunderts. Spieler kaufen Aktien, bauen Streckennetze und betreiben Züge, um den höchsten Vermögenswert zu erreichen.

Die vollständigen Spielregeln sind in [1835-Spielregeln.md](1835-Spielregeln.md) dokumentiert.

---

## Starten

```bash
make dev
```

Danach erreichbar unter:

| Dienst | URL |
|--------|-----|
| Spieloberfläche | http://localhost:5173 |
| API | http://localhost:8000 |
| API-Dokumentation | http://localhost:8000/docs |

---

## Wie funktioniert das Spiel?

Das Frontend zeigt immer nur das, was der Server erlaubt. Es gibt keine Spiellogik im Browser – der Server entscheidet bei jedem Zug, welche Aktionen gültig sind, und schickt diese als Liste ans Frontend. Die Buttons in der Oberfläche entstehen direkt aus dieser Liste.

Das bedeutet: Regeländerungen oder neue Spielphasen müssen nur an einer Stelle gepflegt werden – im Backend.

---

## Wie wird der Spielstand gespeichert?

Jede Aktion im Spiel wird als **Eintrag in einer Datenbank** festgehalten – nicht der Zustand selbst, sondern was passiert ist. Der aktuelle Spielstand ergibt sich immer durch das Nachspielen aller bisherigen Aktionen.

Das hat zwei Vorteile:
- **Vollständige Nachvollziehbarkeit** – jeder Zug ist dokumentiert
- **Zeitreise** – der Spielstand zu jedem beliebigen Zeitpunkt kann wiederhergestellt werden

Damit das Wiederherstellen nicht jedes Mal von Anfang an passieren muss, wird alle 20 Aktionen ein Zwischenstand gespeichert.

Mehrere Spieler können gleichzeitig spielen, ohne dass Züge verloren gehen: Wenn zwei Aktionen gleichzeitig ankommen, gewinnt die erste – die zweite bekommt eine Fehlermeldung und kann es erneut versuchen.

---

## Echtzeit-Updates

Sobald ein Spieler einen Zug macht, sehen alle anderen Spieler im selben Spiel den neuen Stand sofort – ohne die Seite neu laden zu müssen. Das läuft über eine dauerhafte Verbindung (WebSocket) zwischen Browser und Server.

---

## Authentifizierung

Der Login funktioniert ohne Passwort. Nach Eingabe einer E-Mail-Adresse wird ein einmaliger Link verschickt. Wer auf den Link klickt, ist eingeloggt.

---

## Aufbau des Projekts

```
frontend/   Spieloberfläche (React, TypeScript)     → :5173
backend/    Spiellogik & API (Python, FastAPI)       → :8000
            └── domain/       Spielregeln
            └── application/  Ablaufsteuerung
            └── api/          Schnittstelle nach außen
            └── infrastructure/ Datenbank
postgres    Speicherung aller Spielstände            → :5432
```

### Spieloberfläche

| Bereich | Funktion |
|---------|----------|
| Hex-Karte | Das Spielbrett mit allen Städten und Strecken |
| Aktionsleiste | Alle Züge, die aktuell erlaubt sind |
| Gesellschaften | Übersicht über Eisenbahngesellschaften und deren Züge |
| Aktienkurstafel | Aktueller Kursverlauf aller Gesellschaften |
| Spieler-Panel | Vermögen und Aktienbesitz je Spieler |
| Gleisvorrat | Verfügbare Gleisplättchen zum Bauen |
| Phasenführer | Erklärung, was in der aktuellen Spielphase zu tun ist |

### API-Übersicht

| Aktion | Beschreibung |
|--------|-------------|
| Spiel erstellen | Neue Partie anlegen |
| Spiel beitreten | Als Spieler an einer offenen Partie teilnehmen |
| Zug ausführen | Eine Aktion einreichen – der Server prüft und speichert |
| Spielstand abrufen | Aktuellen Stand des Spiels laden |
| Erlaubte Züge | Liste aller Aktionen, die ein Spieler gerade machen darf |
| Zugprotokoll | Alle bisherigen Aktionen einer Partie |
| Export | Vollständigen Spielstand als JSON exportieren (für Backups oder Import) |
| Pause / Fortsetzen | Partie einfrieren und wieder aktivieren |
| Echtzeit | WebSocket-Verbindung für Live-Updates |
| Magic-Link | Passwortlosen Login-Link per E-Mail anfordern |

---

## Häufige Befehle

```bash
make test      # Tests ausführen
make lint      # Code-Qualität prüfen
make format    # Code automatisch formatieren
make migrate   # Datenbankstruktur aktualisieren
make clean     # Alle Container und Daten entfernen
```
