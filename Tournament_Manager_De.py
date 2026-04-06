"""
Pétanque Pro — Tournament Director Edition (German UI)
English code, German user interface strings.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import pandas as pd
import datetime
import random
import os
import sys
from PIL import Image, ImageTk


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class MatchStatus:
    PLAYING  = "Spielt"
    WAITING  = "Wartend"
    FINISHED = "Beendet"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resource_path(relative_path: str) -> str:
    """Return absolute path; works both in dev and when bundled by PyInstaller."""
    try:
        base = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        base = os.path.abspath(".")
    return os.path.join(base, relative_path)


def split_team(team_string: str) -> list[str]:
    """Split 'Alice, Bob & Carol' into ['Alice', 'Bob', 'Carol']."""
    return [n.strip() for n in team_string.replace(" & ", ",").split(",")]


# ---------------------------------------------------------------------------
# Database Layer
# ---------------------------------------------------------------------------

class Database:
    """All SQL lives here. The rest of the app never writes raw SQL."""

    def __init__(self, path: str = "tournament.db"):
        self.path = path
        self._init_schema()

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self.connect() as conn:
            # Migrate existing databases that predate these columns
            for col in ("match_id INTEGER", "terrain INTEGER", "round_num INTEGER"):
                try:
                    conn.execute(f"ALTER TABLE history ADD COLUMN {col}")
                except sqlite3.OperationalError:
                    pass  # Column already exists — safe to ignore

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

    # -- Players --

    def add_player(self, name: str):
        with self.connect() as conn:
            conn.execute("INSERT INTO players (name) VALUES (?)", (name,))

    def delete_player(self, name: str):
        with self.connect() as conn:
            conn.execute("DELETE FROM players WHERE name=?", (name,))

    def get_standings(self) -> list:
        with self.connect() as conn:
            return conn.execute(
                "SELECT name, wins, diff, pf, pa FROM players ORDER BY wins DESC, diff DESC, pf DESC"
            ).fetchall()

    def get_all_player_names(self) -> list[str]:
        with self.connect() as conn:
            return [r["name"] for r in conn.execute(
                "SELECT name FROM players ORDER BY wins DESC, diff DESC, pf DESC"
            ).fetchall()]

    def played_before(self, conn, t1: str, t2: str) -> bool:
        """Check whether two teams have already played each other."""
        return conn.execute(
            "SELECT id FROM history WHERE (team_a=? AND team_b=?) OR (team_a=? AND team_b=?)",
            (t1, t2, t2, t1)
        ).fetchone() is not None

    def update_player_stats(self, conn, name: str, pf: int, pa: int, win: int):
        conn.execute(
            "UPDATE players SET wins=wins+?, diff=diff+?, pf=pf+?, pa=pa+? WHERE name=?",
            (win, pf - pa, pf, pa, name)
        )

    def reverse_player_stats(self, conn, name: str, pf: int, pa: int, win: int):
        conn.execute(
            "UPDATE players SET wins=MAX(0,wins-?), diff=diff-?, pf=pf-?, pa=pa-? WHERE name=?",
            (win, pf - pa, pf, pa, name)
        )

    # -- Matches --

    def clear_matches(self, conn):
        conn.execute("DELETE FROM matches")

    def insert_match(self, conn, t1: str, t2: str, terrain: int, status: str):
        conn.execute(
            "INSERT INTO matches (t1, t2, terrain, status) VALUES (?,?,?,?)",
            (t1, t2, terrain, status)
        )

    def get_matches(self) -> list:
        with self.connect() as conn:
            return conn.execute("SELECT id, terrain, t1, t2, status FROM matches").fetchall()

    def get_active_match(self):
        with self.connect() as conn:
            return conn.execute(
                "SELECT id FROM matches WHERE status IN (?,?)",
                (MatchStatus.PLAYING, MatchStatus.WAITING)
            ).fetchone()

    def get_playing_matches(self) -> list:
        with self.connect() as conn:
            return conn.execute(
                "SELECT terrain, t1, t2 FROM matches WHERE status=? ORDER BY terrain ASC",
                (MatchStatus.PLAYING,)
            ).fetchall()

    def get_waiting_matches(self, limit: int = 2) -> list:
        with self.connect() as conn:
            return conn.execute(
                "SELECT t1, t2 FROM matches WHERE status=? ORDER BY id ASC LIMIT ?",
                (MatchStatus.WAITING, limit)
            ).fetchall()

    def finish_match(self, conn, match_id: int):
        conn.execute(
            "UPDATE matches SET status=?, terrain=0 WHERE id=?",
            (MatchStatus.FINISHED, match_id)
        )

    def promote_waiting(self, conn, terrain: int):
        row = conn.execute(
            "SELECT id FROM matches WHERE status=? LIMIT 1",
            (MatchStatus.WAITING,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE matches SET status=?, terrain=? WHERE id=?",
                (MatchStatus.PLAYING, terrain, row["id"])
            )

    def reopen_match(self, conn, match_id: int, terrain: int):
        """Reopen a finished match by its ID — reliable, no name-matching."""
        conn.execute(
            "UPDATE matches SET status=?, terrain=? WHERE id=?",
            (MatchStatus.PLAYING, terrain, match_id)
        )

    def demote_occupant(self, conn, terrain: int, exclude_match_id: int):
        """If another match was promoted onto this lane, send it back to Waiting."""
        conn.execute(
            "UPDATE matches SET status=?, terrain=0 WHERE status=? AND terrain=? AND id!=?",
            (MatchStatus.WAITING, MatchStatus.PLAYING, terrain, exclude_match_id)
        )

    # -- History --

    def add_history(self, conn, match_id: int, terrain: int,
                    team_a: str, team_b: str, score_a: int, score_b: int):
        conn.execute(
            "INSERT INTO history (match_id, terrain, team_a, team_b, score_a, score_b) "
            "VALUES (?,?,?,?,?,?)",
            (match_id, terrain, team_a, team_b, score_a, score_b)
        )

    def get_last_history(self):
        with self.connect() as conn:
            return conn.execute(
                "SELECT id, match_id, terrain, team_a, team_b, score_a, score_b "
                "FROM history ORDER BY id DESC LIMIT 1"
            ).fetchone()

    def delete_history(self, conn, history_id: int):
        conn.execute("DELETE FROM history WHERE id=?", (history_id,))

    # -- Bulk --

    def reset_all(self):
        with self.connect() as conn:
            conn.executescript("DELETE FROM players; DELETE FROM matches; DELETE FROM history;")

    def get_standings_df(self):
        with self.connect() as conn:
            return pd.read_sql_query(
                "SELECT name AS Team, wins AS Siege, diff AS Diff, pf AS Plus, pa AS Minus "
                "FROM players ORDER BY wins DESC, diff DESC", conn
            )

    def get_history_df(self):
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
# Tournament Engine
# ---------------------------------------------------------------------------

class TournamentEngine:
    """Pure pairing logic — no UI, no DB writes (returns data for caller to persist)."""

    @staticmethod
    def swiss_pairs(player_names: list[str], already_played_fn) -> tuple[list, str | None]:
        """
        Return (pairs, bye_player_or_None).
        pairs = [(t1, t2), ...]

        Players arrive pre-sorted by rank (wins DESC, diff DESC).
        For each unpaired player, find the closest-ranked opponent they haven't
        already faced. Only fall back to a rematch if no fresh opponent exists.
        """
        players = list(player_names)
        bye = None

        if len(players) % 2 != 0:
            bye = players.pop()

        paired   = []
        unpaired = list(players)

        while len(unpaired) >= 2:
            t1 = unpaired.pop(0)

            # Search in rank order — take the first (closest-ranked) fresh opponent
            best_idx = None
            for i, candidate in enumerate(unpaired):
                if not already_played_fn(t1, candidate):
                    best_idx = i
                    break

            if best_idx is not None:
                paired.append((t1, unpaired.pop(best_idx)))
            else:
                # All remaining opponents are rematches — accept the closest-ranked
                paired.append((t1, unpaired.pop(0)))

        return paired, bye

    @staticmethod
    def melee_teams(player_names: list[str]) -> tuple[list, str | None]:
        """
        Return (pairs, bye_player_or_None).
        Randomly mixes players into 2v2 teams, using 3v3 to handle
        counts that don't divide cleanly into groups of four.
        """
        players = list(player_names)
        random.shuffle(players)
        bye = None

        if len(players) % 2 != 0:
            bye = players.pop()

        matches = []

        while len(players) >= 6 and len(players) % 4 != 0:
            p = [players.pop(0) for _ in range(6)]
            matches.append(
                (f"{p[0]}, {p[1]} & {p[2]}", f"{p[3]}, {p[4]} & {p[5]}")
            )

        while len(players) >= 4:
            p = [players.pop(0) for _ in range(4)]
            matches.append((f"{p[0]} & {p[1]}", f"{p[2]} & {p[3]}"))

        return matches, bye

    @staticmethod
    def elimination_bracket(player_names: list[str]) -> tuple[list, list]:
        """
        Return (pairs, byes).
        Seeds bracket so highest-ranked players meet as late as possible.
        """
        players = list(player_names)
        byes = []

        # Round up to next power of 2
        target = 1
        while target < len(players):
            target *= 2

        # Top seeds receive byes to fill the bracket
        while len(players) < target:
            byes.append(players.pop(0) if players else None)

        # Seed: 1 vs last, 2 vs second-last, etc.
        pairs = []
        while len(players) >= 2:
            pairs.append((players.pop(0), players.pop()))

        return pairs, byes


class TournamentMode:
    SWISS = "Schweizer System"
    MELEE = "Super Mêlée"
    ELIM  = "K.O.-System"


# ---------------------------------------------------------------------------
# Main Application (UI only)
# ---------------------------------------------------------------------------

class PetanqueProMaster:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Pétanque Pro — Turnierverwaltung")

        self.db     = Database()
        self.engine = TournamentEngine()

        self._dash: tk.Toplevel | None = None
        self._scroll_idx = 0
        # After-IDs for clean shutdown
        self._after_clock:  str | None = None
        self._after_data:   str | None = None
        self._after_scroll: str | None = None

        self._build_ui()
        self._refresh_all()

    # -----------------------------------------------------------------------
    # UI Construction
    # -----------------------------------------------------------------------

    def _build_ui(self):
        self.tabs = ttk.Notebook(self.root)
        self.tab1 = tk.Frame(self.tabs, padx=20, pady=20)
        self.tab2 = tk.Frame(self.tabs, padx=20, pady=20)
        self.tabs.add(self.tab1, text=" 1. Rangliste & Anmeldung ")
        self.tabs.add(self.tab2, text=" 2. Begegnungen & Auslosung ")
        self.tabs.pack(fill="both", expand=True)

        self._build_tab1()
        self._build_tab2()

    def _build_tab1(self):
        mgmt = tk.LabelFrame(self.tab1, text="Turnier-Management", padx=10, pady=10)
        mgmt.pack(fill="x", pady=5)

        row1 = tk.Frame(mgmt)
        row1.pack(fill="x")

        self.entry_name = tk.Entry(row1, width=25, font=("Arial", 12))
        self.entry_name.pack(side="left", padx=5)
        self.entry_name.bind("<Return>", lambda _e: self._add_player())

        tk.Button(row1, text="Team hinzufügen", command=self._add_player).pack(side="left", padx=2)
        tk.Button(row1, text="Auswahl löschen", command=self._delete_player, fg="orange").pack(side="left", padx=2)
        tk.Button(row1, text="DATEN RESET",     command=self._reset,         fg="red"    ).pack(side="right", padx=2)
        tk.Button(row1, text="EXCEL EXPORT",    command=self._export,        bg="#27ae60").pack(side="right", padx=5)
        tk.Button(row1, text="DASHBOARD",       command=self._open_dashboard,
                  bg="#ecf0f1", font=("Arial", 10, "bold")).pack(side="right", padx=5)

        row2 = tk.Frame(mgmt)
        row2.pack(fill="x", pady=(10, 0))

        tk.Label(row2, text="📢 DURCHSAGE:", font=("Arial", 10, "bold")).pack(side="left", padx=5)
        self.announce_entry = tk.Entry(row2, font=("Arial", 12), fg="blue")
        self.announce_entry.pack(side="left", fill="x", expand=True, padx=10)
        self.announce_entry.insert(0, "Willkommen zum Turnier!")

        cols = ("name", "wins", "diff", "pf", "pa")
        self.tree = ttk.Treeview(self.tab1, columns=cols, show="headings")
        for col, head in zip(cols, ["Team", "Siege", "+/-", "+", "-"]):
            self.tree.heading(col, text=head)
            self.tree.column(col, anchor="center")
        self.tree.pack(fill="both", expand=True, pady=10)

    def _build_tab2(self):
        ctrl = tk.LabelFrame(self.tab2, text="Steuerung", padx=10, pady=10)
        ctrl.pack(fill="x")

        tk.Label(ctrl, text="Bahnen:").pack(side="left")
        self.entry_lanes = tk.Entry(ctrl, width=4)
        self.entry_lanes.insert(0, "4")
        self.entry_lanes.pack(side="left", padx=5)

        tk.Label(ctrl, text="System:").pack(side="left", padx=(10, 2))
        self.tourney_type = ttk.Combobox(
            ctrl,
            values=[TournamentMode.SWISS, TournamentMode.MELEE, TournamentMode.ELIM],
            state="readonly", width=16
        )
        self.tourney_type.set(TournamentMode.SWISS)
        self.tourney_type.pack(side="left", padx=5)

        tk.Button(ctrl, text="AUSLOSEN",        command=self._generate_draw,
                  bg="#3498db", font=("Arial", 10, "bold")).pack(side="left", padx=10)
        tk.Button(ctrl, text="UNDO (Korrektur)", command=self._undo,
                  bg="#f39c12").pack(side="left")
        tk.Label(ctrl, text="(Doppelklick auf Spiel für Ergebniseingabe)",
                 fg="gray", font=("Arial", 9)).pack(side="left", padx=10)

        cols = ("id", "lane", "t1", "vs", "t2", "status")
        self.match_list = ttk.Treeview(self.tab2, columns=cols, show="headings")
        headers = {"id": ("ID", 50), "lane": ("Bahn", 70), "t1": ("Team 1", 200),
                   "vs": ("vs", 40), "t2": ("Team 2", 200), "status": ("Status", 100)}
        for col, (label, width) in headers.items():
            self.match_list.heading(col, text=label)
            self.match_list.column(col, width=width, anchor="center")
        self.match_list.pack(fill="both", expand=True, pady=10)
        self.match_list.bind("<Double-1>", self._on_match_double_click)

    # -----------------------------------------------------------------------
    # Refresh
    # -----------------------------------------------------------------------

    def _refresh_all(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for p in self.db.get_standings():
            self.tree.insert("", "end", values=(p["name"], p["wins"], p["diff"], p["pf"], p["pa"]))

        for row in self.match_list.get_children():
            self.match_list.delete(row)
        for m in self.db.get_matches():
            lane = m["terrain"] if m["terrain"] and m["terrain"] > 0 else "-"
            self.match_list.insert("", "end", values=(m["id"], lane, m["t1"], "vs", m["t2"], m["status"]))

        if self._dash_is_alive():
            self._standings_dirty = True

    # -----------------------------------------------------------------------
    # Player management
    # -----------------------------------------------------------------------

    def _add_player(self):
        name = self.entry_name.get().strip()
        if not name:
            return
        try:
            self.db.add_player(name)
            self.entry_name.delete(0, tk.END)
            self._refresh_all()
        except sqlite3.IntegrityError:
            messagebox.showerror("Fehler", "Team existiert bereits.")

    def _delete_player(self):
        sel = self.tree.selection()
        if not sel:
            return
        name = self.tree.item(sel[0], "values")[0]
        if messagebox.askyesno("Löschen", f"Soll '{name}' wirklich gelöscht werden?"):
            self.db.delete_player(name)
            self._refresh_all()

    # -----------------------------------------------------------------------
    # Draw / Pairing
    # -----------------------------------------------------------------------

    def _max_lanes(self) -> int:
        try:
            return int(self.entry_lanes.get())
        except ValueError:
            return 4

    def _check_active_round(self) -> bool:
        """Returns True if safe to proceed (no active round, or user confirmed override)."""
        if self.db.get_active_match():
            return messagebox.askyesno(
                "Runde läuft",
                "Eine Runde ist noch aktiv. Trotzdem neu auslosen?"
            )
        return True

    def _assign_lanes(self, conn, pairs: list[tuple[str, str]]):
        """Insert match rows, assigning lanes to the first N matches."""
        max_t = self._max_lanes()
        for i, (t1, t2) in enumerate(pairs, 1):
            terrain = i if i <= max_t else 0
            status  = MatchStatus.PLAYING if i <= max_t else MatchStatus.WAITING
            self.db.insert_match(conn, t1, t2, terrain, status)

    def _apply_bye(self, conn, bye: str):
        conn.execute(
            "UPDATE players SET wins=wins+1, pf=pf+13, diff=diff+13 WHERE name=?", (bye,)
        )
        messagebox.showinfo("Freilos", f"{bye} erhält ein Freilos (13:0 Sieg).")

    def _generate_draw(self):
        mode = self.tourney_type.get()
        dispatch = {
            TournamentMode.SWISS: self._generate_swiss,
            TournamentMode.MELEE: self._generate_melee,
            TournamentMode.ELIM:  self._generate_elimination,
        }
        dispatch[mode]()

    def _generate_swiss(self):
        names = self.db.get_all_player_names()
        if len(names) < 2:
            messagebox.showwarning("Warnung", "Mindestens 2 Teams benötigt!")
            return
        if not self._check_active_round():
            return

        with self.db.connect() as conn:
            def played(a, b): return self.db.played_before(conn, a, b)
            pairs, bye = self.engine.swiss_pairs(names, played)
            self.db.clear_matches(conn)
            if bye:
                self._apply_bye(conn, bye)
            self._assign_lanes(conn, pairs)

        self._refresh_all()

    def _generate_melee(self):
        names = self.db.get_all_player_names()
        if len(names) < 4:
            messagebox.showwarning("Warnung", "Mindestens 4 Spieler benötigt!")
            return
        if not self._check_active_round():
            return

        pairs, bye = self.engine.melee_teams(names)

        with self.db.connect() as conn:
            self.db.clear_matches(conn)
            if bye:
                self._apply_bye(conn, bye)
            self._assign_lanes(conn, pairs)

        self._refresh_all()

    def _generate_elimination(self):
        names = self.db.get_all_player_names()
        if len(names) < 2:
            messagebox.showwarning("Warnung", "Mindestens 2 Teams benötigt!")
            return
        if not self._check_active_round():
            return

        pairs, byes = self.engine.elimination_bracket(names)

        with self.db.connect() as conn:
            self.db.clear_matches(conn)
            for bye in byes:
                if bye:
                    self._apply_bye(conn, bye)
            self._assign_lanes(conn, pairs)

        if byes:
            names_str = ", ".join(b for b in byes if b)
            messagebox.showinfo("Freilos", f"Freilose in der ersten Runde: {names_str}")

        self._refresh_all()

    # -----------------------------------------------------------------------
    # Scoring
    # -----------------------------------------------------------------------

    def _on_match_double_click(self, _event):
        sel = self.match_list.selection()
        if not sel:
            return
        v = self.match_list.item(sel[0], "values")
        # v: (id, lane, t1, "vs", t2, status)
        if v[5] != MatchStatus.PLAYING:
            return

        pop = tk.Toplevel(self.root)
        pop.title("Ergebniseingabe")
        pop.geometry("300x180")
        pop.grab_set()

        tk.Label(pop, text=f"{v[2]}  vs  {v[4]}", font=("Arial", 10, "bold")).pack(pady=10)
        entry = tk.Entry(pop, font=("Arial", 14), justify="center")
        entry.insert(0, "13-0")
        entry.pack(pady=5)
        entry.focus_set()
        entry.selection_range(0, tk.END)

        def save():
            try:
                s1, s2   = map(int, entry.get().replace(" ", "").split("-"))
                match_id = int(v[0])
                terrain  = int(v[1]) if v[1] != "-" else 0
                self._record_score(match_id, terrain, v[2], v[4], s1, s2)
                pop.destroy()
            except (ValueError, AttributeError):
                messagebox.showerror("Formatfehler", "Bitte Format  13-5  verwenden", parent=pop)

        entry.bind("<Return>", lambda _e: save())
        tk.Button(pop, text="Speichern (Enter)", command=save, bg="#2ecc71").pack(pady=10)

    def _record_score(self, match_id: int, terrain: int,
                      t1: str, t2: str, s1: int, s2: int):
        with self.db.connect() as conn:
            for name in split_team(t1):
                self.db.update_player_stats(conn, name, s1, s2, 1 if s1 > s2 else 0)
            for name in split_team(t2):
                self.db.update_player_stats(conn, name, s2, s1, 1 if s2 > s1 else 0)

            # Store terrain in history so undo can restore the exact lane
            self.db.add_history(conn, match_id, terrain, t1, t2, s1, s2)

            self.db.finish_match(conn, match_id)
            if terrain > 0:
                self.db.promote_waiting(conn, terrain)

        self._refresh_all()

    # -----------------------------------------------------------------------
    # Undo
    # -----------------------------------------------------------------------

    def _undo(self):
        last = self.db.get_last_history()
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
                self.db.reverse_player_stats(conn, name, s1, s2, 1 if s1 > s2 else 0)
            for name in split_team(t2):
                self.db.reverse_player_stats(conn, name, s2, s1, 1 if s2 > s1 else 0)

            # Demote any match that was promoted onto this lane
            self.db.demote_occupant(conn, terrain, exclude_match_id=match_id)
            # Restore the original match to Playing on its original lane
            self.db.reopen_match(conn, match_id, terrain)
            self.db.delete_history(conn, last["id"])

        self._refresh_all()

    # -----------------------------------------------------------------------
    # Export & Reset
    # -----------------------------------------------------------------------

    def _export(self):
        try:
            out = "Turnier.xlsx"
            with pd.ExcelWriter(out, engine="openpyxl") as writer:
                self.db.get_standings_df().to_excel(writer, sheet_name="Abschlussrangliste", index=False)
                self.db.get_history_df().to_excel(writer,  sheet_name="Spielverlauf",        index=False)
            messagebox.showinfo("Export", f"Gespeichert als '{os.path.abspath(out)}'")
        except PermissionError:
            messagebox.showerror("Exportfehler", "Bitte zuerst die Excel-Datei schließen.")
        except Exception as exc:
            messagebox.showerror("Exportfehler", str(exc))

    def _reset(self):
        if messagebox.askyesno("Reset", "Alle Daten löschen?"):
            self.db.reset_all()
            self._refresh_all()

    # -----------------------------------------------------------------------
    # Dashboard
    # -----------------------------------------------------------------------

    def _dash_is_alive(self) -> bool:
        return self._dash is not None and self._dash.winfo_exists()

    def _open_dashboard(self):
        if self._dash_is_alive():
            self._dash.lift()
            return

        self._dash = tk.Toplevel(self.root)
        self._dash.title("OFFIZIELLE ANZEIGETAFEL")
        self._dash.configure(bg="black")
        self._dash.protocol("WM_DELETE_WINDOW", self._close_dashboard)
        self._dash.state("zoomed")

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

        # Header
        header = tk.Frame(self._dash, bg="black")
        header.pack(fill="x", pady=20)

        tk.Label(header, text="🏆 RANGLISTE",
                 font=("Arial", 30, "bold"), bg="black", fg="gold").pack(side="left", padx=50)

        right = tk.Frame(header, bg="black")
        right.pack(side="right", padx=50)

        try:
            img   = Image.open(resource_path("boule icon.png")).resize((80, 80), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            lbl   = tk.Label(right, image=photo, bg="black")
            lbl.image = photo  # prevent GC
            lbl.pack(side="right")
        except Exception as exc:
            print(f"Icon not loaded: {exc}")

        self._dash_clock = tk.Label(right, text="", font=("Consolas", 30),
                                    bg="black", fg="#00ff00")
        self._dash_clock.pack(side="right", padx=20)

        # Announcement banner (packed first so it stays pinned to the bottom)
        self._dash_msg = tk.Label(self._dash, text="",
                                  font=("Arial", 30, "bold"),
                                  bg="#c0392b", fg="white", pady=10)
        self._dash_msg.pack(side="bottom", fill="x")

        # Standings tree — takes all remaining space
        txt_height = self._max_lanes() + 2

        self._dash_tree = ttk.Treeview(self._dash,
                                       columns=("rank", "name", "wins", "diff"),
                                       show="headings", style="D.Treeview")
        for col, label, width in [
            ("rank", "RANG",  100),
            ("name", "TEAM",  400),
            ("wins", "SIEGE", 150),
            ("diff", "+/-",   150),
        ]:
            self._dash_tree.heading(col, text=label)
            self._dash_tree.column(col, anchor="center", width=width)
        self._dash_tree.pack(fill="both", expand=True, padx=40, pady=(0, 5))

        # Lane assignments — fixed height, does not grow with window
        tk.Label(self._dash, text="AKTUELL AUF DEN BAHNEN",
                 font=("Arial", 22, "bold"), bg="black", fg="#00FF7F").pack(pady=5)

        self._dash_match_text = tk.Text(self._dash, font=("Arial", 28, "bold"),
                                        bg="black", fg="white", height=txt_height,
                                        relief="flat", cursor="arrow",
                                        padx=10, pady=12)
        self._dash_match_text.pack(fill="x", padx=40, pady=(5, 15))

        self._scroll_idx      = 0
        self._standings_dirty = False  # standings populated immediately below

        self._repopulate_standings()
        self._update_clock()
        self._update_live_data()
        self._dash.after(1500, self._auto_scroll)

    def _close_dashboard(self):
        """Cancel all pending after() calls before destroying the window."""
        for attr in ("_after_clock", "_after_data", "_after_scroll"):
            after_id = getattr(self, attr, None)
            if after_id:
                try:
                    self.root.after_cancel(after_id)
                except Exception:
                    pass
                setattr(self, attr, None)
        if self._dash_is_alive():
            self._dash.destroy()

    def _repopulate_standings(self):
        """Wipe and refill the leaderboard tree. Only called when scroll index is 0."""
        for row in self._dash_tree.get_children():
            self._dash_tree.delete(row)
        for i, p in enumerate(self.db.get_standings(), 1):
            self._dash_tree.insert("", "end", values=(i, p["name"], p["wins"], p["diff"]))
        self._standings_dirty = False

    def _update_clock(self):
        """Loop 1: clock — updates every second."""
        if not self._dash_is_alive():
            return
        self._dash_clock.config(text=datetime.datetime.now().strftime("%H:%M:%S"))
        self._after_clock = self.root.after(1000, self._update_clock)

    def _update_live_data(self):
        """Loop 2: lane assignments and announcement — updates every second.
        Never touches the standings tree — that belongs to the scroll loop."""
        if not self._dash_is_alive():
            return

        # Lane assignments — playing matches + up to 2 waiting
        self._dash_match_text.config(state="normal")
        self._dash_match_text.delete("1.0", "end")
        playing = self.db.get_playing_matches()
        waiting = self.db.get_waiting_matches(limit=2)
        if playing:
            for m in playing:
                self._dash_match_text.insert("end", f"BAHN {m['terrain']}:  {m['t1']}  vs  {m['t2']}\n")
            for w in waiting:
                self._dash_match_text.insert("end", f"  ⏳  {w['t1']}  vs  {w['t2']}\n")
        else:
            self._dash_match_text.insert("end", "\n— RUNDE BEENDET —")
        self._dash_match_text.tag_add("center", "1.0", "end")
        self._dash_match_text.tag_configure("center", justify="center")
        self._dash_match_text.config(state="disabled")

        # Announcement
        self._dash_msg.config(text=self.announce_entry.get().upper())

        self._after_data = self.root.after(1000, self._update_live_data)

    def _auto_scroll(self):
        """Loop 3: auto-scroll — crawls through the standings row by row."""
        if not self._dash_is_alive():
            return

        visible = 8  # rows visible without scrolling

        # At the top: apply any pending standings update, then start the crawl
        if self._scroll_idx == 0:
            if self._standings_dirty:
                self._repopulate_standings()
            items = self._dash_tree.get_children()
            if not items:
                self._after_scroll = self.root.after(2000, self._auto_scroll)
                return
            if len(items) <= visible:
                self._after_scroll = self.root.after(5000, self._auto_scroll)
                return
            self._scroll_idx = visible

        items = self._dash_tree.get_children()

        if self._scroll_idx < len(items):
            self._dash_tree.see(items[self._scroll_idx])
            self._scroll_idx += 1
            delay = 6000 if self._scroll_idx >= len(items) else 3000
            self._after_scroll = self.root.after(delay, self._auto_scroll)
        else:
            # Reached the bottom — snap back to top and pause
            self._scroll_idx = 0
            self._dash_tree.yview_moveto(0)
            self._after_scroll = self.root.after(5000, self._auto_scroll)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    root = tk.Tk()
    root.lift()
    root.attributes("-topmost", True)
    root.after_idle(root.attributes, "-topmost", False)
    PetanqueProMaster(root)
    root.mainloop()
