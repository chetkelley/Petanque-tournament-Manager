# Pétanque Tournament Manager

[English](#english) | [Deutsch](#deutsch)

---

## English

### Overview

Pétanque Tournament Manager is a lightweight, offline desktop application for managing Pétanque and Boule club tournaments. It handles player registration, automatic match pairing, score tracking, and a live public scoreboard — all without requiring an internet connection or a web server.

The application comes in two versions sharing the same codebase and architecture:

- **Tournament_Manager.py** — English UI, optimised for macOS
- **Tournament_Manager_De.py** — German UI, optimised for Windows

### Key Features

**Three Tournament Formats**
Supports Swiss Ladder, Super Melee, and Single Elimination from a single dropdown. Swiss pairing uses a closest-rank-first algorithm to keep winners playing winners and losers playing losers across rounds, while avoiding rematches where possible. Super Melee randomly mixes players into 2v2 teams, handling odd counts with 3v3 matches so no one is left out. Single Elimination seeds the bracket so top-ranked players meet as late as possible.

**Live Public Dashboard**
A fullscreen, high-contrast scoreboard designed to be shown on a second screen or projector. Displays a scrolling leaderboard, current lane assignments, the next two waiting matches, and a broadcast message ticker at the bottom. The leaderboard auto-scrolls through all players and refreshes automatically after every score entry.

**Lane Queue Management**
Matches are automatically assigned to available lanes. When a match finishes, the next waiting match is promoted to that lane immediately. The dashboard reflects this in real time.

**Reliable Undo**
Any incorrectly entered score can be reversed with the Undo button. The match is restored to its original lane in Playing status so the correct score can be entered immediately. Player stats, standings, and history are all rolled back cleanly.

**Entry Fee Tracking**
A dedicated Entry Fees tab lets the tournament director configure a fee per team or player and record payments as they come in. Partial payments are supported and accumulate — if three members of a team each pay separately, their contributions are tracked individually against the team's balance. Each entry is colour-coded: green for fully paid, orange for partial, red for nothing received yet. A summary bar shows total due, total collected, outstanding balance, and how many entries are fully paid at a glance. Payments reset automatically with the tournament data.

**Data Management**
SQLite database backend stores all player stats, match results, history, and payment records across sessions. One-click Excel export produces a workbook with a Final Rankings sheet and a full Match History sheet.

### Architecture

The application is structured in three layers:

- **Database** — all SQL in one class; the rest of the app never writes raw queries
- **TournamentEngine** — pure pairing logic with no UI or database dependencies
- **PetanqueProMaster** — UI only; delegates all data and logic to the layers above

The dashboard runs three independent timing loops: one for the clock, one for lane assignments and the announcement ticker, and one for the auto-scrolling leaderboard. These are deliberately kept separate so updating live match data never interrupts the scroll.

### Getting Started

**Requirements:** Python 3.10+, pandas, Pillow, openpyxl

**Installation:**
```bash
pip install pandas pillow openpyxl
```

**Run:**
```bash
python Tournament_Manager.py        # English / macOS
python Tournament_Manager_De.py     # German / Windows
```

Ensure `boule icon.png` is in the same directory as the script.

### Project Structure

| File | Description |
|------|-------------|
| `Tournament_Manager.py` | English version — macOS, Helvetica Neue font, aqua theme |
| `Tournament_Manager_De.py` | German version — Windows, Arial font, clam theme |
| `boule icon.png` | Dashboard logo |
| `tournament.db` | SQLite database — created automatically on first run |
| `Tournament_Results.xlsx` | Excel export — created when Export is clicked |

### Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3 |
| UI Framework | Tkinter |
| Database | SQLite3 |
| Image Handling | Pillow (PIL) |
| Data Export | Pandas + openpyxl |

---

## Deutsch

### Überblick

Pétanque Tournament Manager ist eine schlanke Desktop-Anwendung zur Turnierverwaltung für Pétanque- und Boule-Vereine. Sie läuft vollständig offline — ohne Internetverbindung oder Webserver — und übernimmt Anmeldung, Auslosung, Ergebniserfassung und eine Live-Anzeigetafel.

Die Anwendung ist in zwei Versionen mit gemeinsamer Codebasis verfügbar:

- **Tournament_Manager.py** — Englische Benutzeroberfläche, optimiert für macOS
- **Tournament_Manager_De.py** — Deutsche Benutzeroberfläche, optimiert für Windows

### Hauptfunktionen

**Drei Turnierformate**
Über ein Dropdown-Menü wählbar: Schweizer System, Super Mêlée und K.O.-System. Die Auslosung nach dem Schweizer System verwendet einen rangbasierten Algorithmus, der Gewinner möglichst gegen Gewinner und Verlierer gegen Verlierer setzt und dabei Wiederholungsspiele vermeidet. Super Mêlée mischt die Spieler zufällig in 2-gegen-2-Teams; bei ungerader Spielerzahl werden 3-gegen-3-Spiele eingebaut, damit niemand pausieren muss. Das K.O.-System setzt die Spieler so, dass die besten Teams erst in späteren Runden aufeinandertreffen.

**Live-Anzeigetafel**
Eine Vollbild-Anzeigetafel im hochkontrastreichen Design für Beamer oder zweiten Bildschirm. Zeigt eine automatisch scrollende Rangliste, aktuelle Bahnbelegungen, die nächsten zwei wartenden Spiele sowie einen Durchsage-Banner am unteren Bildschirmrand. Die Rangliste aktualisiert sich nach jeder Ergebniseingabe automatisch.

**Bahnwarteschlange**
Spiele werden automatisch den verfügbaren Bahnen zugewiesen. Sobald ein Spiel beendet wird, rückt das nächste Wartespiel sofort auf die freie Bahn nach. Die Anzeigetafel spiegelt dies in Echtzeit wider.

**Zuverlässige Korrektur**
Falsch eingegebene Ergebnisse lassen sich per UNDO-Schaltfläche rückgängig machen. Das Spiel wird auf seiner ursprünglichen Bahn im Status „Spielt" wiederhergestellt, sodass das richtige Ergebnis sofort eingetragen werden kann. Statistiken, Rangliste und Spielverlauf werden vollständig zurückgesetzt.

**Startgeldverwaltung**
Ein eigener Reiter „Startgelder" ermöglicht der Turnierleiterin, den Betrag pro Team oder Spieler festzulegen und Zahlungen zu erfassen. Teilzahlungen werden unterstützt und akkumuliert — zahlen drei Mitglieder eines Teams einzeln, werden ihre Beiträge separat erfasst und dem Team angerechnet. Jeder Eintrag ist farblich markiert: grün für vollständig bezahlt, orange für Teilzahlung, rot für noch ausstehend. Eine Zusammenfassungsleiste zeigt auf einen Blick: Gesamtbetrag fällig, eingenommen, ausstehend und wie viele Teams vollständig bezahlt haben. Zahlungen werden beim Zurücksetzen der Turnierdaten automatisch gelöscht.

**Datenverwaltung**
SQLite-Datenbank speichert Spielerstatistiken, Spielergebnisse, Verlauf und Zahlungsdaten sitzungsübergreifend. Per Knopfdruck wird ein Excel-Export mit Abschlussrangliste und vollständigem Spielverlauf erstellt.

### Erste Schritte

**Voraussetzungen:** Python 3.10+, pandas, Pillow, openpyxl

**Installation:**
```bash
pip install pandas pillow openpyxl
```

**Start:**
```bash
python Tournament_Manager_De.py
```

Die Datei `boule icon.png` muss sich im selben Verzeichnis wie das Skript befinden.

### Projektstruktur

| Datei | Beschreibung |
|-------|--------------|
| `Tournament_Manager.py` | Englische Version — macOS, Schrift Helvetica Neue, Aqua-Design |
| `Tournament_Manager_De.py` | Deutsche Version — Windows, Schrift Arial, Clam-Design |
| `boule icon.png` | Logo für die Anzeigetafel |
| `tournament.db` | SQLite-Datenbank — wird beim ersten Start automatisch erstellt |
| `Turnier.xlsx` | Excel-Export — wird beim Klick auf „Excel Export" erstellt |

### Technologien

| Komponente | Technologie |
|------------|-------------|
| Sprache | Python 3 |
| UI-Framework | Tkinter |
| Datenbank | SQLite3 |
| Bildverarbeitung | Pillow (PIL) |
| Datenexport | Pandas + openpyxl |
