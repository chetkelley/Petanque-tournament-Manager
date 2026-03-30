Petanque Tournament
English | Deutsch

**ENGLISH**

English: Overview
Petanque Tournament Manager is a lightweight, desktop-based tournament management system designed specifically for Petanque and Boule clubs. It simplifies player registration, match pairing via the Swiss System, and real-time score tracking.

Key Features
Live Dashboard: A high-contrast, fullscreen Public Display for players to see current rankings and court assignments.

Smart Matchmaking: Supports the Swiss System and Super Melee with automatic court allocation.

Data Management: SQLite database backend for reliability, with one-click Excel export for final results.

Correction Logic: Full Undo support for incorrectly entered scores to ensure tournament integrity.

Getting Started
Requirements: Python 3.x, pandas, Pillow, openpyxl.

Installation:

Bash
pip install pandas pillow openpyxl
Run: Execute python Tournament_Manager.py and ensure boule icon.png is in the same directory.

**Deutsch**


Petanque Tournament Manager ist eine schlanke Desktop-Anwendung zur Turnierverwaltung, speziell entwickelt für Petanque- und Boule-Vereine. Sie vereinfacht die Anmeldung, die Auslosung nach dem Schweizer System und die Ergebniserfassung.

Hauptfunktionen
Live-Dashboard: Eine kontrastreiche Vollbildanzeige für Spieler, um aktuelle Ranglisten und Bahnbelegungen in Echtzeit zu verfolgen.

Intelligente Auslosung: Unterstützt das Schweizer System und Super Melee mit automatischer Bahnzuweisung.

Datenverwaltung: SQLite-Datenbank für Stabilität und ein Ein-Klick-Excel-Export für die Endergebnisse.

Korrektur-Modus: Letzte Korrektur-Funktion, um falsch eingegebene Ergebnisse ohne Datenverlust rückgängig zu machen.

Erste Schritte
Voraussetzungen: Python 3.x, pandas, Pillow, openpyxl.

Installation:

Bash
pip install pandas pillow openpyxl
Start: Führen Sie python Tournament_Manager_De.py aus. Stellen Sie sicher, dass sich boule icon.png im selben Verzeichnis befindet.

Tech Stack / Technologien
Language: Python 3

UI Framework: Tkinter (Custom Styles)

Database: SQLite3

Image Handling: PIL (Pillow)

Data Export: Pandas and Openpyxl

Project Structure / Projektstruktur
Tournament_Manager.py: The core application logic / Hauptlogik der Anwendung.

boule icon.png: The dashboard logo / Das Logo für die Anzeige.

tournament.db: Generated automatically on first start / Wird beim ersten Start automatisch erstellt.
