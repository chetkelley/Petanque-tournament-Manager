"""
Pétanque Pro — Turnierverwaltung (Kompaktversion)
Refaktoriert für saubere Architektur, Sicherheit und Wartbarkeit.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import pandas as pd
import datetime
import platform
import random
import os
import sys
from PIL import Image, ImageTk


# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

class SpielStatus:
    SPIELT  = "Spielt"
    WARTEND = "Wartend"
    BEENDET = "Beendet"


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def resource_path(relative_path: str) -> str:
    """Gibt absoluten Pfad zurück; funktioniert in der Entwicklung und mit PyInstaller."""
    try:
        base = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        base = os.path.abspath(".")
    return os.path.join(base, relative_path)


def split_team(team_string: str) -> list[str]:
    """Teilt 'Alice, Bob & Carol' in ['Alice', 'Bob', 'Carol'] auf."""
    return [n.strip() for n in team_string.replace(" & ", ",").split(",")]


# ---------------------------------------------------------------------------
# Datenbankschicht
# ---------------------------------------------------------------------------

class Datenbank:
    """Alle SQL-Abfragen befinden sich hier. Der Rest der App schreibt kein rohes SQL."""

    def __init__(self, path: str = "tournament.db"):
        self.path = path
        self._init_schema()

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self.connect() as conn:
            # Migrationsspalten für bestehende Datenbanken hinzufügen
            for col in ("match_id INTEGER", "terrain INTEGER", "round_num INTEGER"):
                try:
                    conn.execute(f"ALTER TABLE history ADD COLUMN {col}")
                except sqlite3.OperationalError:
                    pass  # Spalte existiert bereits

            conn.executescript("""
                CREATE TABLE IF NOT EXISTS players (
                    id   INTEGER PRIMARY KEY,
                    name TEXT UNIQUE,
                    wins INTEGER DEFAULT 0,
                    diff INTEGER DEFAULT 0,
                    pf   INTEGER DEFAULT 0,
                    pa   INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS matches (
                    id      INTEGER PRIMARY KEY,
                    t1      TEXT,
                    t2      TEXT,
                    terrain INTEGER,
                    status  TEXT
                );
                CREATE TABLE IF NOT EXISTS history (
                    id        INTEGER PRIMARY KEY,
                    match_id  INTEGER,
                    terrain   INTEGER,
                    team_a    TEXT,
                    team_b    TEXT,
                    score_a   INTEGER,
                    score_b   INTEGER,
                    round_num INTEGER
                );
            """)

    # -- Spieler --

    def spieler_hinzufuegen(self, name: str):
        with self.connect() as conn:
            conn.execute("INSERT INTO players (name) VALUES (?)", (name,))

    def spieler_loeschen(self, name: str):
        with self.connect() as conn:
            conn.execute("DELETE FROM players WHERE name=?", (name,))

    def alle_spieler_holen(self) -> list:
        with self.connect() as conn:
            return conn.execute(
                "SELECT name, wins, diff, pf, pa FROM players ORDER BY wins DESC, diff DESC, pf DESC"
            ).fetchall()

    def alle_spielernamen_holen(self) -> list[str]:
        with self.connect() as conn:
            return [r["name"] for r in conn.execute("SELECT name FROM players").fetchall()]

    def spieler_statistik_aktualisieren(self, conn, name: str, pf: int, pa: int, win: int):
        conn.execute(
            "UPDATE players SET wins=wins+?, diff=diff+?, pf=pf+?, pa=pa+? WHERE name=?",
            (win, pf - pa, pf, pa, name)
        )

    def spieler_statistik_rueckgaengig(self, conn, name: str, pf: int, pa: int, win: int):
        conn.execute(
            "UPDATE players SET wins=MAX(0,wins-?), diff=diff-?, pf=pf-?, pa=pa-? WHERE name=?",
            (win, pf - pa, pf, pa, name)
        )

    # -- Spiele --

    def spiele_loeschen(self, conn):
        conn.execute("DELETE FROM matches")

    def spiel_einfuegen(self, conn, t1: str, t2: str, terrain: int, status: str):
        conn.execute(
            "INSERT INTO matches (t1, t2, terrain, status) VALUES (?,?,?,?)",
            (t1, t2, terrain, status)
        )

    def alle_spiele_holen(self) -> list:
        with self.connect() as conn:
            return conn.execute("SELECT id, terrain, t1, t2, status FROM matches").fetchall()

    def laufende_spiele_holen(self) -> list:
        with self.connect() as conn:
            return conn.execute(
                "SELECT terrain, t1, t2 FROM matches WHERE status=? ORDER BY terrain ASC",
                (SpielStatus.SPIELT,)
            ).fetchall()

    def spiel_beenden(self, conn, match_id: int):
        conn.execute(
            "UPDATE matches SET status=?, terrain=0 WHERE id=?",
            (SpielStatus.BEENDET, match_id)
        )

    def naechstes_wartend_hochstufen(self, conn, terrain: int):
        row = conn.execute(
            "SELECT id FROM matches WHERE status=? LIMIT 1",
            (SpielStatus.WARTEND,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE matches SET status=?, terrain=? WHERE id=?",
                (SpielStatus.SPIELT, terrain, row["id"])
            )

    def spiel_nach_id_wiederoeffnen(self, conn, match_id: int, terrain: int):
        """Öffnet ein beendetes Spiel anhand seiner ID wieder — zuverlässiger als Namenssuche."""
        conn.execute(
            "UPDATE matches SET status=?, terrain=? WHERE id=?",
            (SpielStatus.SPIELT, terrain, match_id)
        )

    def spiel_auf_wartend_zuruecksetzen(self, conn, terrain: int, exclude_match_id: int):
        """Setzt ein anderes 'Spielt'-Spiel auf dieser Bahn auf 'Wartend' zurück.
        Wird beim Undo benötigt, wenn ein nachrücktes Spiel die Bahn wieder freigeben muss."""
        conn.execute(
            "UPDATE matches SET status=?, terrain=0 WHERE status=? AND terrain=? AND id!=?",
            (SpielStatus.WARTEND, SpielStatus.SPIELT, terrain, exclude_match_id)
        )

    # -- Verlauf --

    def verlauf_hinzufuegen(self, conn, match_id: int, terrain: int,
                            team_a: str, team_b: str, score_a: int, score_b: int):
        conn.execute(
            "INSERT INTO history (match_id, terrain, team_a, team_b, score_a, score_b) "
            "VALUES (?,?,?,?,?,?)",
            (match_id, terrain, team_a, team_b, score_a, score_b)
        )

    def letzten_verlauf_holen(self):
        with self.connect() as conn:
            return conn.execute(
                "SELECT id, match_id, terrain, team_a, team_b, score_a, score_b "
                "FROM history ORDER BY id DESC LIMIT 1"
            ).fetchone()

    def verlauf_loeschen(self, conn, history_id: int):
        conn.execute("DELETE FROM history WHERE id=?", (history_id,))

    # -- Gesamt --

    def alles_zuruecksetzen(self):
        with self.connect() as conn:
            conn.executescript("DELETE FROM players; DELETE FROM matches; DELETE FROM history;")

    def rangliste_als_df(self):
        with self.connect() as conn:
            return pd.read_sql_query(
                "SELECT name AS Team, wins AS Siege, diff AS Diff, pf AS Plus, pa AS Minus "
                "FROM players ORDER BY wins DESC, diff DESC", conn
            )

    def verlauf_als_df(self):
        with self.connect() as conn:
            df = pd.read_sql_query(
                "SELECT id, team_a, team_b, score_a, score_b FROM history ORDER BY id ASC", conn
            )
        df.insert(0, "Runde", range(1, len(df) + 1))
        df["Ergebnis"] = df["score_a"].astype(str) + " - " + df["score_b"].astype(str)
        return df[["Runde", "team_a", "team_b", "Ergebnis"]].rename(
            columns={"team_a": "Team 1", "team_b": "Team 2"}
        )


# ---------------------------------------------------------------------------
# Hauptanwendung (nur UI)
# ---------------------------------------------------------------------------

class PetanqueProMaster:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Pétanque Pro — Turnierverwaltung")

        self.db = Datenbank()

        self._dash: tk.Toplevel | None = None
        self._scroll_idx = 0
        # After-IDs für sauberes Beenden
        self._after_uhr:    str | None = None
        self._after_daten:  str | None = None
        self._after_scroll: str | None = None

        self._ui_aufbauen()
        self._alles_aktualisieren()

    # -----------------------------------------------------------------------
    # UI-Aufbau
    # -----------------------------------------------------------------------

    def _ui_aufbauen(self):
        self.tabs = ttk.Notebook(self.root)
        self.tab1 = tk.Frame(self.tabs, padx=20, pady=20)
        self.tab2 = tk.Frame(self.tabs, padx=20, pady=20)
        self.tabs.add(self.tab1, text=" 1. Rangliste & Anmeldung ")
        self.tabs.add(self.tab2, text=" 2. Begegnungen & Auslosung ")
        self.tabs.pack(fill="both", expand=True)

        self._tab1_aufbauen()
        self._tab2_aufbauen()

    def _tab1_aufbauen(self):
        mgmt = tk.LabelFrame(self.tab1, text="Turnier-Management", padx=10, pady=10)
        mgmt.pack(fill="x", pady=5)

        z1 = tk.Frame(mgmt)
        z1.pack(fill="x")

        self.ent_name = tk.Entry(z1, width=25, font=("Arial", 12))
        self.ent_name.pack(side="left", padx=5)
        self.ent_name.bind("<Return>", lambda _e: self._spieler_hinzufuegen())

        tk.Button(z1, text="Team hinzufügen", command=self._spieler_hinzufuegen).pack(side="left", padx=2)
        tk.Button(z1, text="Auswahl löschen", command=self._spieler_loeschen, fg="orange").pack(side="left", padx=2)
        tk.Button(z1, text="DATEN RESET",     command=self._reset,  fg="red"     ).pack(side="right", padx=2)
        tk.Button(z1, text="EXCEL EXPORT",    command=self._export, bg="#27ae60" ).pack(side="right", padx=5)
        tk.Button(z1, text="DASHBOARD",       command=self._dashboard_oeffnen,
                  bg="#ecf0f1", font=("Arial", 10, "bold")).pack(side="right", padx=5)

        z2 = tk.Frame(mgmt)
        z2.pack(fill="x", pady=(10, 0))

        tk.Label(z2, text="📢 DURCHSAGE:", font=("Arial", 10, "bold")).pack(side="left", padx=5)
        self.announce_entry = tk.Entry(z2, font=("Arial", 12), fg="blue")
        self.announce_entry.pack(side="left", fill="x", expand=True, padx=10)
        self.announce_entry.insert(0, "Willkommen zum Turnier!")

        cols = ("name", "wins", "diff", "pf", "pa")
        self.tree = ttk.Treeview(self.tab1, columns=cols, show="headings")
        for col, head in zip(cols, ["Team", "Siege", "+/-", "+", "-"]):
            self.tree.heading(col, text=head)
            self.tree.column(col, anchor="center")
        self.tree.pack(fill="both", expand=True, pady=10)

    def _tab2_aufbauen(self):
        ctrl = tk.LabelFrame(self.tab2, text="Steuerung", padx=10, pady=10)
        ctrl.pack(fill="x")

        tk.Label(ctrl, text="Bahnen:").pack(side="left")
        self.ent_bahnen = tk.Entry(ctrl, width=4)
        self.ent_bahnen.insert(0, "4")
        self.ent_bahnen.pack(side="left", padx=5)

        tk.Button(ctrl, text="AUSLOSEN",         command=self._auslosen,
                  bg="#3498db", font=("Arial", 10, "bold")).pack(side="left", padx=10)
        tk.Button(ctrl, text="UNDO (Korrektur)",  command=self._undo,
                  bg="#f39c12").pack(side="left")
        tk.Label(ctrl, text="(Doppelklick auf Spiel für Ergebniseingabe)",
                 fg="gray", font=("Arial", 9)).pack(side="left", padx=10)

        cols = ("id", "bahn", "t1", "vs", "t2", "status")
        self.m_tree = ttk.Treeview(self.tab2, columns=cols, show="headings")
        headers = {"id": ("ID", 50), "bahn": ("Bahn", 70), "t1": ("Team 1", 200),
                   "vs": ("vs", 40), "t2": ("Team 2", 200), "status": ("Status", 100)}
        for col, (label, width) in headers.items():
            self.m_tree.heading(col, text=label)
            self.m_tree.column(col, width=width, anchor="center")
        self.m_tree.pack(fill="both", expand=True, pady=10)
        self.m_tree.bind("<Double-1>", self._ergebnis_fenster)

    # -----------------------------------------------------------------------
    # Aktualisierung
    # -----------------------------------------------------------------------

    def _alles_aktualisieren(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        for p in self.db.alle_spieler_holen():
            self.tree.insert("", "end", values=(p["name"], p["wins"], p["diff"], p["pf"], p["pa"]))

        for r in self.m_tree.get_children():
            self.m_tree.delete(r)
        for m in self.db.alle_spiele_holen():
            bahn = m["terrain"] if m["terrain"] and m["terrain"] > 0 else "-"
            self.m_tree.insert("", "end", values=(m["id"], bahn, m["t1"], "vs", m["t2"], m["status"]))

    # -----------------------------------------------------------------------
    # Spielerverwaltung
    # -----------------------------------------------------------------------

    def _spieler_hinzufuegen(self):
        name = self.ent_name.get().strip()
        if not name:
            return
        try:
            self.db.spieler_hinzufuegen(name)
            self.ent_name.delete(0, tk.END)
            self._alles_aktualisieren()
        except sqlite3.IntegrityError:
            messagebox.showerror("Fehler", "Team existiert bereits.")

    def _spieler_loeschen(self):
        sel = self.tree.selection()
        if not sel:
            return
        name = self.tree.item(sel[0], "values")[0]
        if messagebox.askyesno("Löschen", f"Soll '{name}' wirklich gelöscht werden?"):
            self.db.spieler_loeschen(name)
            self._alles_aktualisieren()

    # -----------------------------------------------------------------------
    # Auslosung
    # -----------------------------------------------------------------------

    def _max_bahnen(self) -> int:
        try:
            return int(self.ent_bahnen.get())
        except ValueError:
            return 4

    def _auslosen(self):
        namen = self.db.alle_spielernamen_holen()
        if len(namen) < 2:
            messagebox.showwarning("Warnung", "Mindestens 2 Teams benötigt!")
            return

        random.shuffle(namen)
        max_t = self._max_bahnen()

        with self.db.connect() as conn:
            self.db.spiele_loeschen(conn)
            for i in range(0, len(namen) - 1, 2):
                idx = (i // 2) + 1
                terrain = idx if idx <= max_t else 0
                status  = SpielStatus.SPIELT if idx <= max_t else SpielStatus.WARTEND
                self.db.spiel_einfuegen(conn, namen[i], namen[i + 1], terrain, status)

        self._alles_aktualisieren()

    # -----------------------------------------------------------------------
    # Ergebniseingabe
    # -----------------------------------------------------------------------

    def _ergebnis_fenster(self, _event):
        sel = self.m_tree.selection()
        if not sel:
            return
        v = self.m_tree.item(sel[0], "values")
        # v: (id, bahn, t1, "vs", t2, status)
        if v[5] != SpielStatus.SPIELT:
            return

        pop = tk.Toplevel(self.root)
        pop.title("Ergebniseingabe")
        pop.geometry("300x180")
        pop.grab_set()

        tk.Label(pop, text=f"{v[2]}  vs  {v[4]}", font=("Arial", 10, "bold")).pack(pady=10)
        ent = tk.Entry(pop, font=("Arial", 14), justify="center")
        ent.insert(0, "13-0")
        ent.pack(pady=5)
        ent.focus_set()
        ent.selection_range(0, tk.END)

        def speichern():
            try:
                s1, s2 = map(int, ent.get().replace(" ", "").split("-"))
                match_id = int(v[0])
                terrain  = int(v[1]) if v[1] != "-" else 0
                self._ergebnis_eintragen(match_id, terrain, v[2], v[4], s1, s2)
                pop.destroy()
            except (ValueError, AttributeError):
                messagebox.showerror("Formatfehler", "Bitte Format  13-5  verwenden", parent=pop)

        ent.bind("<Return>", lambda _e: speichern())
        tk.Button(pop, text="Speichern (Enter)", command=speichern, bg="#2ecc71").pack(pady=10)

    def _ergebnis_eintragen(self, match_id: int, terrain: int,
                             t1: str, t2: str, s1: int, s2: int):
        with self.db.connect() as conn:
            # Spielerstatistiken aktualisieren
            for name in split_team(t1):
                self.db.spieler_statistik_aktualisieren(conn, name, s1, s2, 1 if s1 > s2 else 0)
            for name in split_team(t2):
                self.db.spieler_statistik_aktualisieren(conn, name, s2, s1, 1 if s2 > s1 else 0)

            # Verlauf mit match_id und terrain speichern (für zuverlässiges Undo)
            self.db.verlauf_hinzufuegen(conn, match_id, terrain, t1, t2, s1, s2)

            # Spiel beenden und nächstes Wartespiel hochstufen
            self.db.spiel_beenden(conn, match_id)
            if terrain > 0:
                self.db.naechstes_wartend_hochstufen(conn, terrain)

        self._alles_aktualisieren()

    # -----------------------------------------------------------------------
    # Undo
    # -----------------------------------------------------------------------

    def _undo(self):
        last = self.db.letzten_verlauf_holen()
        if not last:
            messagebox.showinfo("Korrektur", "Kein Spielverlauf zum Rückgängigmachen.")
            return

        t1, t2   = last["team_a"], last["team_b"]
        s1, s2   = last["score_a"], last["score_b"]
        match_id = last["match_id"]
        terrain  = last["terrain"]

        if not messagebox.askyesno("Korrektur", f"Ergebnis {t1} {s1}:{s2} {t2} rückgängig machen?"):
            return

        with self.db.connect() as conn:
            for name in split_team(t1):
                self.db.spieler_statistik_rueckgaengig(conn, name, s1, s2, 1 if s1 > s2 else 0)
            for name in split_team(t2):
                self.db.spieler_statistik_rueckgaengig(conn, name, s2, s1, 1 if s2 > s1 else 0)

            # Spiel direkt per ID wiedereröffnen — kein Bahnen-Suchaufwand nötig
            self.db.spiel_nach_id_wiederoeffnen(conn, match_id, terrain)
            # Falls ein nachrücktes Spiel diese Bahn belegt hat, zurück auf Wartend setzen
            self.db.spiel_auf_wartend_zuruecksetzen(conn, terrain, exclude_match_id=match_id)
            self.db.verlauf_loeschen(conn, last["id"])

        self._alles_aktualisieren()

    # -----------------------------------------------------------------------
    # Export & Reset
    # -----------------------------------------------------------------------

    def _export(self):
        try:
            out = "Turnier.xlsx"
            with pd.ExcelWriter(out, engine="openpyxl") as writer:
                self.db.rangliste_als_df().to_excel(writer, sheet_name="Abschlussrangliste", index=False)
                self.db.verlauf_als_df().to_excel(writer, sheet_name="Spielverlauf", index=False)
            messagebox.showinfo("Export", f"Gespeichert als '{os.path.abspath(out)}'")
        except PermissionError:
            messagebox.showerror("Exportfehler", "Bitte zuerst die Excel-Datei schließen.")
        except Exception as exc:
            messagebox.showerror("Exportfehler", str(exc))

    def _reset(self):
        if messagebox.askyesno("Reset", "Alle Daten löschen?"):
            self.db.alles_zuruecksetzen()
            self._alles_aktualisieren()

    # -----------------------------------------------------------------------
    # Dashboard
    # -----------------------------------------------------------------------

    def _dash_ist_aktiv(self) -> bool:
        return self._dash is not None and self._dash.winfo_exists()

    def _dashboard_oeffnen(self):
        if self._dash_ist_aktiv():
            self._dash.lift()
            return

        self._dash = tk.Toplevel(self.root)
        self._dash.title("OFFIZIELLE ANZEIGETAFEL")
        self._dash.configure(bg="black")
        self._dash.protocol("WM_DELETE_WINDOW", self._dashboard_schliessen)

        os_name = platform.system()
        if os_name == "Windows":
            self._dash.state("zoomed")
        else:
            self._dash.geometry("1200x800")

        # Stile
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("D.Treeview",
                        background="#111111", foreground="white",
                        fieldbackground="#111111",
                        font=("Arial", 28), rowheight=55)
        style.configure("D.Treeview.Heading",
                        background="#003366", foreground="white",
                        font=("Arial", 20, "bold"))
        style.map("D.Treeview",
                  foreground=[("selected", "white"),  ("!disabled", "white")],
                  background=[("selected", "#34495e"), ("!disabled", "#111111")])

        # Kopfzeile
        header = tk.Frame(self._dash, bg="black")
        header.pack(fill="x", pady=20)

        tk.Label(header, text="🏆 RANGLISTE",
                 font=("Arial", 30, "bold"), bg="black", fg="gold").pack(side="left", padx=50)

        right = tk.Frame(header, bg="black")
        right.pack(side="right", padx=50)

        try:
            img = Image.open(resource_path("boule icon.png")).resize((80, 80), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(right, image=photo, bg="black")
            lbl.image = photo  # GC-Schutz
            lbl.pack(side="right")
        except Exception as exc:
            print(f"Icon nicht geladen: {exc}")

        self._lbl_uhr = tk.Label(right, text="", font=("Consolas", 30),
                                 bg="black", fg="#00ff00")
        self._lbl_uhr.pack(side="right", padx=20)

        # Ranglisten-Treeview
        cols = ("rang", "name", "siege", "diff")
        self.d_tree = ttk.Treeview(self._dash, columns=cols, show="headings",
                                   style="D.Treeview")
        for col, label, width in [
            ("rang",  "RANG",   100),
            ("name",  "TEAM",   400),
            ("siege", "SIEGE",  150),
            ("diff",  "+/-",    150),
        ]:
            self.d_tree.heading(col, text=label)
            self.d_tree.column(col, anchor="center", width=width)
        self.d_tree.pack(fill="both", expand=True, padx=40)

        # Bahnbelegung
        tk.Label(self._dash, text="AKTUELL AUF DEN BAHNEN",
                 font=("Arial", 22, "bold"), bg="black", fg="#00FF7F").pack(pady=10)

        self.d_txt = tk.Text(self._dash, font=("Arial", 28, "bold"),
                             bg="black", fg="white", height=4, relief="flat", cursor="arrow")
        self.d_txt.pack(fill="x", padx=40)

        # Durchsage-Banner
        self.d_msg = tk.Label(self._dash, text="",
                              font=("Arial", 30, "bold"),
                              bg="#c0392b", fg="white", pady=10)
        self.d_msg.pack(side="bottom", fill="x")

        self._scroll_idx = 0

        # Drei unabhängige Schleifen starten
        self._dash_uhr_update()
        self._dash_daten_update()          # Füllt den Baum sofort beim Öffnen
        self._dash.after(2000, self._dash_scroll_update)   # Kurz warten bis Daten geladen

    def _dashboard_schliessen(self):
        """Sauberes Beenden — alle laufenden after()-Aufrufe abbrechen."""
        for attr in ("_after_uhr", "_after_daten", "_after_scroll"):
            after_id = getattr(self, attr, None)
            if after_id:
                try:
                    self.root.after_cancel(after_id)
                except Exception:
                    pass
                setattr(self, attr, None)
        if self._dash_ist_aktiv():
            self._dash.destroy()

    def _dash_uhr_update(self):
        """Schleife 1: Uhr — aktualisiert jede Sekunde."""
        if not self._dash_ist_aktiv():
            return
        self._lbl_uhr.config(text=datetime.datetime.now().strftime("%H:%M:%S"))
        self._after_uhr = self.root.after(1000, self._dash_uhr_update)

    def _dash_daten_update(self):
        """Schleife 2: Daten — aktualisiert alle 5 Sekunden."""
        if not self._dash_ist_aktiv():
            return

        # Rangliste — nur neu befüllen wenn Ansicht oben ist, sonst wird Scroll-Position zurückgesetzt
        if self.d_tree.yview()[0] == 0.0:
            for r in self.d_tree.get_children():
                self.d_tree.delete(r)
            for i, p in enumerate(self.db.alle_spieler_holen(), 1):
                self.d_tree.insert("", "end", values=(i, p["name"], p["wins"], p["diff"]))

        # Bahnbelegung
        self.d_txt.config(state="normal")
        self.d_txt.delete("1.0", "end")
        spiele = self.db.laufende_spiele_holen()
        if spiele:
            for m in spiele:
                self.d_txt.insert("end", f"BAHN {m['terrain']}:  {m['t1']}  vs  {m['t2']}\n")
        else:
            self.d_txt.insert("end", "\n— RUNDE BEENDET —")
        self.d_txt.tag_add("center", "1.0", "end")
        self.d_txt.tag_configure("center", justify="center")
        self.d_txt.config(state="disabled")

        # Durchsage
        self.d_msg.config(text=self.announce_entry.get().upper())

        self._after_daten = self.root.after(5000, self._dash_daten_update)

    def _dash_scroll_update(self):
        """Schleife 3: Auto-Scroll — bewegt sich zeilenweise durch die Rangliste."""
        if not self._dash_ist_aktiv():
            return

        eintraege = self.d_tree.get_children()
        if not eintraege:
            self._after_scroll = self.root.after(2000, self._dash_scroll_update)
            return

        sichtbar = 8  # Anzahl der ohne Scrollen sichtbaren Zeilen

        if self._scroll_idx < len(eintraege):
            self.d_tree.see(eintraege[self._scroll_idx])
            ist_sichtbar = self._scroll_idx < sichtbar
            self._scroll_idx += 1
            # Kurze Verzögerung für bereits sichtbare Zeilen, lange nur beim echten Scrollen
            verzoegerung = 200 if ist_sichtbar else (6000 if self._scroll_idx == len(eintraege) else 3000)
            self._after_scroll = self.root.after(verzoegerung, self._dash_scroll_update)
        else:
            # Zurück nach oben und pausieren
            self._scroll_idx = 0
            self.d_tree.yview_moveto(0)
            self._after_scroll = self.root.after(5000, self._dash_scroll_update)


# ---------------------------------------------------------------------------
# Einstiegspunkt
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    root = tk.Tk()
    root.lift()
    root.attributes("-topmost", True)
    root.after_idle(root.attributes, "-topmost", False)
    PetanqueProMaster(root)
    root.mainloop()
