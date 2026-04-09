"""
Pétanque Pro - Tournament Director Edition
Refactored for clean architecture, safety, and maintainability.
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
    PLAYING  = "Playing"
    WAITING  = "Waiting"
    FINISHED = "Finished"


class TournamentMode:
    SWISS     = "Swiss Ladder"
    MELEE     = "Super Melee"
    ELIM      = "Single Elimination"


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

    # -- Context manager so callers can do: with self.db as conn: ...
    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self.connect() as conn:
            # Migrate existing databases that predate these columns
            for col in ("match_id INTEGER", "terrain INTEGER"):
                try:
                    conn.execute(f"ALTER TABLE history ADD COLUMN {col}")
                except Exception:
                    pass  # Column already exists — safe to ignore

            conn.executescript("""
                CREATE TABLE IF NOT EXISTS players (
                    id   INTEGER PRIMARY KEY,
                    name TEXT UNIQUE,
                    wins INTEGER DEFAULT 0,
                    pf   INTEGER DEFAULT 0,
                    pa   INTEGER DEFAULT 0,
                    diff INTEGER DEFAULT 0
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
                CREATE TABLE IF NOT EXISTS payments (
                    id     INTEGER PRIMARY KEY,
                    name   TEXT,
                    amount REAL
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT
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
                "SELECT name, wins, pf, pa, diff FROM players ORDER BY wins DESC, diff DESC"
            ).fetchall()

    def get_all_player_names(self) -> list[str]:
        with self.connect() as conn:
            return [r["name"] for r in conn.execute(
                "SELECT name FROM players ORDER BY wins DESC, diff DESC"
            ).fetchall()]

    def apply_bye(self, name: str):
        with self.connect() as conn:
            conn.execute(
                "UPDATE players SET wins=wins+1, pf=pf+13, diff=diff+13 WHERE name=?",
                (name,)
            )

    def update_player_stats(self, conn, name: str, pf: int, pa: int, win: int):
        conn.execute(
            "UPDATE players SET pf=pf+?, pa=pa+?, wins=MAX(0,wins+?), diff=diff+? WHERE name=?",
            (pf, pa, win, pf - pa, name)
        )

    def reverse_player_stats(self, conn, name: str, pf: int, pa: int, win: int):
        conn.execute(
            "UPDATE players SET pf=pf-?, pa=pa-?, wins=MAX(0,wins-?), diff=diff-? WHERE name=?",
            (pf, pa, win, pf - pa, name)
        )

    # -- Matches --

    def clear_matches(self, conn=None):
        def _do(c):
            c.execute("DELETE FROM matches")
        if conn:
            _do(conn)
        else:
            with self.connect() as c:
                _do(c)

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

    def reopen_match(self, conn, match_id: int, terrain: int, status: str):
        """Reopen a finished match by its ID — reliable, no name-matching."""
        conn.execute(
            "UPDATE matches SET terrain=?, status=? WHERE id=? AND status=?",
            (terrain, status, match_id, MatchStatus.FINISHED)
        )

    def get_occupied_terrains(self, conn) -> list[int]:
        return [r["terrain"] for r in conn.execute(
            "SELECT terrain FROM matches WHERE status=?", (MatchStatus.PLAYING,)
        ).fetchall()]

    # -- History --

    def add_history(self, conn, match_id: int, terrain: int, team_a: str, team_b: str,
                    score_a: int, score_b: int, round_num: int):
        conn.execute(
            "INSERT INTO history (match_id, terrain, team_a, team_b, score_a, score_b, round_num) "
            "VALUES (?,?,?,?,?,?,?)",
            (match_id, terrain, team_a, team_b, score_a, score_b, round_num)
        )

    def get_last_history(self):
        with self.connect() as conn:
            return conn.execute(
                "SELECT id, match_id, terrain, team_a, team_b, score_a, score_b "
                "FROM history ORDER BY id DESC LIMIT 1"
            ).fetchone()

    def delete_history(self, conn, history_id: int):
        conn.execute("DELETE FROM history WHERE id=?", (history_id,))

    def played_before(self, conn, t1: str, t2: str) -> bool:
        return conn.execute(
            "SELECT id FROM history WHERE (team_a=? AND team_b=?) OR (team_a=? AND team_b=?)",
            (t1, t2, t2, t1)
        ).fetchone() is not None

    def get_current_round(self) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT MAX(round_num) as r FROM history").fetchone()
            return (row["r"] or 0) + 1

    # -- Payments --

    def get_fee(self) -> float:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='fee'").fetchone()
            return float(row["value"]) if row else 0.0

    def set_fee(self, amount: float):
        with self.connect() as conn:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('fee', ?)",
                         (str(amount),))

    def add_payment(self, name: str, amount: float):
        with self.connect() as conn:
            conn.execute("INSERT INTO payments (name, amount) VALUES (?,?)", (name, amount))

    def get_payments(self) -> list:
        """Return each registered player/team with total paid and balance owed."""
        with self.connect() as conn:
            fee     = self.get_fee()
            players = conn.execute("SELECT name FROM players ORDER BY name ASC").fetchall()
            result  = []
            for p in players:
                row = conn.execute(
                    "SELECT COALESCE(SUM(amount), 0) AS paid FROM payments WHERE name=?",
                    (p["name"],)
                ).fetchone()
                paid = round(row["paid"], 2)
                owed = round(max(0.0, fee - paid), 2)
                result.append({"name": p["name"], "paid": paid, "owed": owed})
            return result

    def get_payment_summary(self) -> dict:
        with self.connect() as conn:
            fee        = self.get_fee()
            n          = conn.execute("SELECT COUNT(*) AS c FROM players").fetchone()["c"]
            total_due  = round(fee * n, 2)
            collected  = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS s FROM payments"
            ).fetchone()["s"]
            collected  = round(collected, 2)
            fully_paid = conn.execute(
                """SELECT COUNT(*) AS c FROM (
                       SELECT name, SUM(amount) AS paid FROM payments GROUP BY name
                       HAVING paid >= ?
                   )""", (fee,)
            ).fetchone()["c"]
            return {
                "total_due":   total_due,
                "collected":   collected,
                "outstanding": round(total_due - collected, 2),
                "fully_paid":  fully_paid,
                "n":           n,
            }

    # -- Bulk --

    def reset_all(self):
        with self.connect() as conn:
            conn.executescript(
                "DELETE FROM players; DELETE FROM matches; "
                "DELETE FROM history; DELETE FROM payments;"
            )

    def get_standings_df(self):
        with self.connect() as conn:
            return pd.read_sql_query(
                "SELECT name AS Team, wins AS Wins, pf AS PF, pa AS PA, diff AS Diff "
                "FROM players ORDER BY wins DESC, diff DESC", conn
            )

    def get_history_df(self):
        with self.connect() as conn:
            # We use SQL string concatenation to combine the scores
            # || is the standard SQLite operator for joining strings
            query = """
                SELECT 
                    round_num AS 'Round', 
                    team_a AS 'Team 1', 
                    team_b AS 'Team 2', 
                    score_a || ' - ' || score_b AS 'Result'
                FROM history
                ORDER BY round_num ASC, id ASC
            """
            return pd.read_sql_query(query, conn)


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

        Pairing strategy: players arrive pre-sorted by rank (wins DESC, diff DESC).
        For each unpaired player, find the closest-ranked opponent they haven't
        already faced. Only fall back to a rematch if no fresh opponent exists.
        This keeps winners playing winners and losers playing losers as fairly
        as possible while still avoiding rematches.
        """
        players = list(player_names)
        bye = None

        if len(players) % 2 != 0:
            bye = players.pop()

        paired   = []
        unpaired = list(players)

        while len(unpaired) >= 2:
            t1 = unpaired.pop(0)

            # Search the remaining list in order (closest rank first).
            # Accept the first opponent t1 hasn't played before.
            best_idx = None
            for i, candidate in enumerate(unpaired):
                if not already_played_fn(t1, candidate):
                    best_idx = i
                    break  # first = closest rank — stop immediately

            if best_idx is not None:
                paired.append((t1, unpaired.pop(best_idx)))
            else:
                # Every remaining opponent is a rematch — accept the closest
                # ranked one (index 0) rather than a random pick
                paired.append((t1, unpaired.pop(0)))

        return paired, bye

    @staticmethod
    def melee_teams(player_names: list[str]) -> tuple[list, str | None]:
        """
        Return (pairs, bye_player_or_None).
        Mixes 2v2 and 3v3 so no one is left out.
        """
        players = list(player_names)
        random.shuffle(players)
        bye = None

        if len(players) % 2 != 0:
            bye = players.pop()

        matches = []

        # Create 3v3 matches to handle counts that don't divide cleanly into 2v2
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
        Seeds bracket so highest-ranked players meet latest.
        """
        players = list(player_names)
        byes = []

        # Round up to next power of 2
        target = 1
        while target < len(players):
            target *= 2

        while len(players) < target:
            byes.append(players.pop(0) if players else None)

        # Seed: 1 vs last, 2 vs second-last, etc.
        pairs = []
        while len(players) >= 2:
            pairs.append((players.pop(0), players.pop()))

        return pairs, byes


# ---------------------------------------------------------------------------
# Main Application (UI only)
# ---------------------------------------------------------------------------

class PetanqueProMaster:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Pétanque Pro — Tournament Director Edition")

        self.db     = Database()
        self.engine = TournamentEngine()

        # Dashboard window reference (may be None or destroyed)
        self._dash: tk.Toplevel | None = None
        self._dash_after_id: str | None = None   # tracks the recurring after() call
        self._scroll_idx = 0

        self._build_ui()
        self._refresh_all()

    # -----------------------------------------------------------------------
    # UI Construction
    # -----------------------------------------------------------------------

    def _build_ui(self):
        self.tabs = ttk.Notebook(self.root)
        self.tab_standings = tk.Frame(self.tabs, padx=20, pady=20)
        self.tab_matches   = tk.Frame(self.tabs, padx=20, pady=20)
        self.tab_payments  = tk.Frame(self.tabs, padx=20, pady=20)
        self.tabs.add(self.tab_standings, text=" 1. Leaderboard ")
        self.tabs.add(self.tab_matches,   text=" 2. Live Matches & Draw ")
        self.tabs.add(self.tab_payments,  text=" 3. Entry Fees ")
        self.tabs.pack(expand=True, fill="both")

        self._build_standings_tab()
        self._build_matches_tab()
        self._build_payments_tab()

    def _build_standings_tab(self):
        mgmt = tk.LabelFrame(self.tab_standings, text="Tournament Management", padx=10, pady=10)
        mgmt.pack(fill="x", pady=5)

        # Row 1 — team entry & action buttons
        row1 = tk.Frame(mgmt)
        row1.pack(fill="x", pady=5)

        self.entry_name = tk.Entry(row1, width=25, font=("Arial", 12))
        self.entry_name.pack(side="left", padx=5)
        self.entry_name.bind("<Return>", lambda _e: self._add_player())

        tk.Button(row1, text="Add Team",       command=self._add_player,    bg="#ecf0f1").pack(side="left", padx=2)
        tk.Button(row1, text="Delete Selected",command=self._delete_player, fg="orange" ).pack(side="left", padx=2)

        tk.Button(row1, text="RESET DATA",          fg="red",     command=self._reset_tournament ).pack(side="right", padx=2)
        tk.Button(row1, text="EXPORT TO EXCEL",      bg="#27ae60", command=self._export_to_excel  ).pack(side="right", padx=5)
        tk.Button(row1, text="OPEN PUBLIC DASHBOARD",bg="#ecf0f1", fg="#00008B",
                  font=("Arial", 10, "bold"),        command=self._open_dashboard              ).pack(side="right", padx=5)

        # Row 2 — broadcast message
        row2 = tk.Frame(mgmt)
        row2.pack(fill="x", pady=(10, 0))

        tk.Label(row2, text="📢 BROADCAST MESSAGE:", font=("Arial", 10, "bold")).pack(side="left", padx=5)
        self.announce_entry = tk.Entry(row2, font=("Arial", 12), fg="blue")
        self.announce_entry.pack(side="left", fill="x", expand=True, padx=10)
        self.announce_entry.insert(0, "Welcome to the Tournament!")
        self.announce_entry.bind("<Return>", lambda _e: self._update_dashboard())
        tk.Label(row2, text="(Press Enter to update dashboard)", font=("Arial", 8), fg="gray").pack(side="left")

        # Standings treeview
        cols = ("Rank", "Team Name", "Wins", "Points For", "Points Against", "Net Diff")
        self.tree = ttk.Treeview(self.tab_standings, columns=cols, show="headings")
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, anchor="center", width=120)
        self.tree.pack(expand=True, fill="both", pady=10)

    def _build_matches_tab(self):
        ctrl = tk.LabelFrame(self.tab_matches, text="Tournament Control", padx=5, pady=5)
        ctrl.pack(fill="x")

        tk.Label(ctrl, text="Lanes:").grid(row=0, column=0, padx=2)
        self.terrain_count = tk.Entry(ctrl, width=3)
        self.terrain_count.insert(0, "3")
        self.terrain_count.grid(row=0, column=1, padx=2)

        tk.Label(ctrl, text="System:").grid(row=0, column=2, padx=5)
        self.tourney_type = ttk.Combobox(
            ctrl,
            values=[TournamentMode.SWISS, TournamentMode.MELEE, TournamentMode.ELIM],
            state="readonly", width=16
        )
        self.tourney_type.set(TournamentMode.SWISS)
        self.tourney_type.grid(row=0, column=3, padx=2)

        tk.Button(ctrl, text="GENERATE",  command=self._handle_draw,
                  bg="#3498db", fg="black", font=("Arial", 10, "bold")).grid(row=0, column=4, padx=5)
        tk.Button(ctrl, text="UNDO LAST", command=self._undo_last_score,
                  bg="#f39c12", fg="black").grid(row=0, column=5, padx=5)
        tk.Label(ctrl, text="(Double-click match to enter score)",
                 fg="gray", font=("Arial", 9)).grid(row=0, column=6, padx=5)

        # Match list (single definition — no duplicates)
        cols = ("id", "lane", "t1", "vs", "t2", "status")
        self.match_list = ttk.Treeview(self.tab_matches, columns=cols, show="headings")

        headers = {"id": ("ID", 40), "lane": ("Lane", 60), "t1": ("Team 1", 200),
                   "vs": ("vs", 40), "t2": ("Team 2", 200), "status": ("Status", 100)}
        for col, (label, width) in headers.items():
            self.match_list.heading(col, text=label)
            self.match_list.column(col, width=width,
                                   anchor="center" if col != "t1" else "center")

        self.match_list.pack(fill="both", expand=True, pady=10)
        self.match_list.bind("<Double-1>", self._on_match_double_click)

    def _build_payments_tab(self):
        # Fee configuration row
        fee_frame = tk.LabelFrame(self.tab_payments, text="Fee Configuration", padx=10, pady=10)
        fee_frame.pack(fill="x", pady=5)

        tk.Label(fee_frame, text="Entry fee per team/player ($):",
                 font=("Arial", 11)).pack(side="left", padx=5)
        self.entry_fee = tk.Entry(fee_frame, width=8, font=("Arial", 12), justify="center")
        self.entry_fee.pack(side="left", padx=5)
        self.entry_fee.insert(0, f"{self.db.get_fee():.2f}")
        tk.Button(fee_frame, text="Save Fee", command=self._save_fee,
                  bg="#27ae60").pack(side="left", padx=10)

        # Summary bar
        self.lbl_summary = tk.Label(self.tab_payments, text="", font=("Arial", 11, "bold"),
                                    bg="#2c3e50", fg="white", pady=6)
        self.lbl_summary.pack(fill="x", pady=(5, 0))

        # Payment entry row
        pay_frame = tk.LabelFrame(self.tab_payments, text="Record Payment", padx=10, pady=10)
        pay_frame.pack(fill="x", pady=5)

        tk.Label(pay_frame, text="Amount ($):", font=("Arial", 11)).pack(side="left", padx=5)
        self.entry_payment = tk.Entry(pay_frame, width=8, font=("Arial", 12), justify="center")
        self.entry_payment.pack(side="left", padx=5)
        tk.Button(pay_frame, text="Record Payment",
                  command=self._record_payment, bg="#3498db").pack(side="left", padx=10)
        tk.Label(pay_frame, text="(Select a team/player in the list below, then record payment)",
                 fg="gray", font=("Arial", 9)).pack(side="left", padx=5)

        # Payment list
        cols = ("name", "paid", "owed", "status")
        self.pay_tree = ttk.Treeview(self.tab_payments, columns=cols, show="headings")
        for col, head, width in [
            ("name",   "Team / Player",  250),
            ("paid",   "Paid ($)",       130),
            ("owed",   "Outstanding ($)", 130),
            ("status", "Status",         120),
        ]:
            self.pay_tree.heading(col, text=head)
            self.pay_tree.column(col, width=width, anchor="center")

        self.pay_tree.tag_configure("paid",    background="#d5f5e3")
        self.pay_tree.tag_configure("partial", background="#fdebd0")
        self.pay_tree.tag_configure("unpaid",  background="#fadbd8")

        self.pay_tree.pack(fill="both", expand=True, pady=10)

    # -----------------------------------------------------------------------
    # Refresh
    # -----------------------------------------------------------------------

    def _refresh_all(self):
        # Standings
        for row in self.tree.get_children():
            self.tree.delete(row)
        for i, p in enumerate(self.db.get_standings(), 1):
            self.tree.insert("", "end", values=(i, p["name"], p["wins"], p["pf"], p["pa"], p["diff"]))

        # Matches
        for row in self.match_list.get_children():
            self.match_list.delete(row)
        for m in self.db.get_matches():
            lane = m["terrain"] if m["terrain"] > 0 else "-"
            self.match_list.insert("", "end",
                values=(m["id"], lane, m["t1"], "vs", m["t2"], m["status"]))

        # Push to dashboard if open
        if self._dash_is_alive():
            self._update_dashboard()

        self._refresh_payments()

    def _refresh_payments(self):
        """Repopulate the payments tab list and summary bar."""
        if not hasattr(self, "pay_tree"):
            return
        for row in self.pay_tree.get_children():
            self.pay_tree.delete(row)

        fee = self.db.get_fee()
        for p in self.db.get_payments():
            if p["owed"] <= 0:
                tag, status = "paid",    "✅ Paid"
            elif p["paid"] > 0:
                tag, status = "partial", "⚠️ Partial"
            else:
                tag, status = "unpaid",  "❌ Outstanding"
            self.pay_tree.insert("", "end", tags=(tag,),
                values=(p["name"], f"{p['paid']:.2f}", f"{p['owed']:.2f}", status))

        s = self.db.get_payment_summary()
        self.lbl_summary.config(
            text=f"  Due: ${s['total_due']:.2f}   |   "
                 f"Collected: ${s['collected']:.2f}   |   "
                 f"Outstanding: ${s['outstanding']:.2f}   |   "
                 f"Fully paid: {s['fully_paid']} / {s['n']}"
        )

    def _save_fee(self):
        try:
            amount = float(self.entry_fee.get().replace(",", "."))
            self.db.set_fee(amount)
            self._refresh_payments()
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid amount (e.g. 15.00)")

    def _record_payment(self):
        sel = self.pay_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a team/player in the list first.")
            return
        name = self.pay_tree.item(sel[0], "values")[0]
        try:
            amount = float(self.entry_payment.get().replace(",", "."))
            if amount <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid amount (e.g. 5.00)")
            return

        # Warn if payment would exceed the configured fee
        fee = self.db.get_fee()
        payments = self.db.get_payments()
        already_paid = next((p["paid"] for p in payments if p["name"] == name), 0.0)
        if fee > 0 and already_paid + amount > fee:
            if not messagebox.askyesno("Overpayment",
                    f"{name} would have paid more than the entry fee (${fee:.2f}). Continue?"):
                return

        self.db.add_payment(name, amount)
        self.entry_payment.delete(0, tk.END)
        self._refresh_payments()

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
            messagebox.showerror("Error", f"Team '{name}' already exists.")

    def _delete_player(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selection Error", "Please select a team first.")
            return
        name = self.tree.item(selected)["values"][1]
        if messagebox.askyesno("Confirm Delete", f"Remove '{name}' from the tournament?"):
            self.db.delete_player(name)
            self._refresh_all()

    # -----------------------------------------------------------------------
    # Draw / Pairing
    # -----------------------------------------------------------------------

    def _handle_draw(self):
        mode = self.tourney_type.get()
        dispatch = {
            TournamentMode.SWISS: self._generate_swiss,
            TournamentMode.MELEE: self._generate_melee,
            TournamentMode.ELIM:  self._generate_elimination,
        }
        dispatch[mode]()

    def _check_active_round(self) -> bool:
        """Returns True if it is safe to proceed (no active round, or user confirmed override)."""
        if self.db.get_active_match():
            return messagebox.askyesno(
                "Round In Progress",
                "A round is currently active. Generating a new draw will clear current matches. Continue?"
            )
        return True

    def _max_terrains(self) -> int:
        try:
            return int(self.terrain_count.get())
        except ValueError:
            return 3

    def _assign_terrains(self, conn, pairs: list[tuple[str, str]]):
        """Insert match rows, assigning terrains to the first N matches."""
        max_t = self._max_terrains()
        for i, (t1, t2) in enumerate(pairs, 1):
            if i <= max_t:
                self.db.insert_match(conn, t1, t2, i, MatchStatus.PLAYING)
            else:
                self.db.insert_match(conn, t1, t2, 0, MatchStatus.WAITING)

    def _generate_swiss(self):
        names = self.db.get_all_player_names()
        if len(names) < 2:
            messagebox.showwarning("Warning", "Need at least 2 teams!")
            return
        if not self._check_active_round():
            return

        with self.db.connect() as conn:
            def played(a, b): return self.db.played_before(conn, a, b)
            pairs, bye = self.engine.swiss_pairs(names, played)

            if bye:
                self.db.clear_matches(conn)
                conn.execute(
                    "UPDATE players SET wins=wins+1, pf=pf+13, diff=diff+13 WHERE name=?", (bye,)
                )
                messagebox.showinfo("BYE", f"{bye} receives a BYE (13–0 win).")
            else:
                self.db.clear_matches(conn)

            self._assign_terrains(conn, pairs)

        self._refresh_all()

    def _generate_melee(self):
        names = self.db.get_all_player_names()
        if len(names) < 4:
            messagebox.showwarning("Warning", "Need at least 4 players!")
            return
        if not self._check_active_round():
            return

        pairs, bye = self.engine.melee_teams(names)

        with self.db.connect() as conn:
            self.db.clear_matches(conn)
            if bye:
                conn.execute(
                    "UPDATE players SET wins=wins+1, pf=pf+13, diff=diff+13 WHERE name=?", (bye,)
                )
                messagebox.showinfo("BYE", f"{bye} receives a BYE.")
            self._assign_terrains(conn, pairs)

        self._refresh_all()

    def _generate_elimination(self):
        names = self.db.get_all_player_names()
        if len(names) < 2:
            messagebox.showwarning("Warning", "Need at least 2 teams!")
            return
        if not self._check_active_round():
            return

        pairs, byes = self.engine.elimination_bracket(names)

        with self.db.connect() as conn:
            self.db.clear_matches(conn)
            round_num = self.db.get_current_round()
            for bye in byes:
                if bye:
                    conn.execute(
                        "UPDATE players SET wins=wins+1, pf=pf+13, diff=diff+13 WHERE name=?", (bye,)
                    )
                    self.db.add_history(conn, bye, "BYE", 13, 0, round_num)
            self._assign_terrains(conn, pairs)

        if byes:
            names_str = ", ".join(b for b in byes if b)
            messagebox.showinfo("BYE", f"First-round byes: {names_str}")

        self._refresh_all()

    # -----------------------------------------------------------------------
    # Scoring
    # -----------------------------------------------------------------------

    def _on_match_double_click(self, _event):
        selection = self.match_list.selection()
        if not selection:
            return
        val = self.match_list.item(selection[0], "values")
        # val: (id, lane, t1, "vs", t2, status)
        if val[5] != MatchStatus.PLAYING:
            return

        pop = tk.Toplevel(self.root)
        pop.title("Score Entry")
        pop.geometry("300x180")
        pop.grab_set()

        tk.Label(pop, text=f"{val[2]}  vs  {val[4]}", font=("Arial", 10, "bold")).pack(pady=10)
        entry = tk.Entry(pop, font=("Arial", 14), justify="center")
        entry.insert(0, "13-0")
        entry.pack(pady=5)
        entry.focus_set()
        entry.selection_range(0, tk.END)

        def save():
            try:
                raw = entry.get().replace(" ", "")
                s1, s2 = map(int, raw.split("-"))
                self._record_score(int(val[0]), int(val[1]), val[2], val[4], s1, s2)
                pop.destroy()
            except (ValueError, AttributeError):
                messagebox.showerror("Format Error", "Use format  13-5", parent=pop)

        entry.bind("<Return>", lambda _e: save())
        tk.Button(pop, text="Save (Enter)", command=save, bg="#2ecc71").pack(pady=10)

    def _record_score(self, match_id: int, terrain: int,
                      t1: str, t2: str, s1: int, s2: int):
        round_num = self.db.get_current_round()
        with self.db.connect() as conn:
            # Update individual player stats
            for name in split_team(t1):
                self.db.update_player_stats(conn, name, s1, s2, 1 if s1 > s2 else 0)
            for name in split_team(t2):
                self.db.update_player_stats(conn, name, s2, s1, 1 if s2 > s1 else 0)

            # Record history — store terrain so undo can restore the exact lane
            self.db.add_history(conn, match_id, terrain, t1, t2, s1, s2, round_num)

            # Mark match finished and promote next waiting match to this terrain
            self.db.finish_match(conn, match_id)
            self.db.promote_waiting(conn, terrain)

        self._refresh_all()

    # -----------------------------------------------------------------------
    # Undo
    # -----------------------------------------------------------------------

    def _undo_last_score(self):
        """Reverses the last result and restores the match to its original lane."""
        last = self.db.get_last_history()
        if not last:
            messagebox.showinfo("Undo", "No match history found to undo.")
            return

        h_id     = last["id"]
        match_id = last["match_id"]
        terrain  = last["terrain"]
        t1, t2   = last["team_a"], last["team_b"]
        s1, s2   = last["score_a"], last["score_b"]

        if not messagebox.askyesno("Confirm Undo", f"Undo result: {t1} ({s1}) vs {t2} ({s2})?"):
            return

        with self.db.connect() as conn:
            # Reverse stats for every individual in both teams
            for name in split_team(t1):
                self.db.reverse_player_stats(conn, name, s1, s2, 1 if s1 > s2 else 0)
            for name in split_team(t2):
                self.db.reverse_player_stats(conn, name, s2, s1, 1 if s2 > s1 else 0)

            # If a match was promoted onto this lane, send it back to Waiting
            conn.execute(
                "UPDATE matches SET status=?, terrain=0 WHERE terrain=? AND status=? AND id!=?",
                (MatchStatus.WAITING, terrain, MatchStatus.PLAYING, match_id)
            )

            # Restore the original match to Playing on its original lane by ID
            conn.execute(
                "UPDATE matches SET terrain=?, status=? WHERE id=?",
                (terrain, MatchStatus.PLAYING, match_id)
            )

            # Remove the history entry
            self.db.delete_history(conn, h_id)

        self._refresh_all()
        messagebox.showinfo("Undo", f"Restored {t1} vs {t2} to Lane {terrain}. Enter the correct score.")

    # -----------------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------------

    def _export_to_excel(self):
        try:
            out = "Tournament_Results.xlsx"
            with pd.ExcelWriter(out, engine="openpyxl") as writer:
                self.db.get_standings_df().to_excel(writer, sheet_name="Final Rankings", index=False)
                self.db.get_history_df().to_excel(writer, sheet_name="Match History",   index=False)
            messagebox.showinfo("Export Success", f"Saved to:\n{os.path.abspath(out)}")
        except PermissionError:
            messagebox.showerror("Export Error", "Close the Excel file first, then try again.")
        except Exception as exc:
            messagebox.showerror("Export Error", str(exc))

    # -----------------------------------------------------------------------
    # Reset
    # -----------------------------------------------------------------------

    def _reset_tournament(self):
        if messagebox.askyesno("Confirm Reset", "Wipe ALL players, matches, and history?"):
            self.db.reset_all()
            self._refresh_all()

    # -----------------------------------------------------------------------
    # Dashboard
    # -----------------------------------------------------------------------

    def _dash_is_alive(self) -> bool:
        return self._dash is not None and self._dash.winfo_exists()

    def _open_dashboard(self):
        # If already open, just bring it to front
        if self._dash_is_alive():
            self._dash.lift()
            return

        self._dash = tk.Toplevel(self.root)
        self._dash.title("OFFICIAL TOURNAMENT SCOREBOARD")
        self._dash.configure(bg="#000000")
        self._dash.protocol("WM_DELETE_WINDOW", self._close_dashboard)
        # Set a large default geometry so exiting fullscreen restores to a usable size
        self._dash.geometry("1400x900")
        self._dash.minsize(900, 600)
        self._dash.attributes("-fullscreen", True)

        main_font = "Helvetica Neue"
        style     = ttk.Style()
        style.theme_use("aqua")
        style.configure("Dash.Treeview",
                        background="#1a1a1a", foreground="white",
                        fieldbackground="#1a1a1a",
                        font=(main_font, 32), rowheight=55)
        style.configure("Dash.Treeview.Heading",
                        background="#003366", foreground="#FFFFFF",
                        font=(main_font, 22, "bold"))
        style.map("Dash.Treeview.Heading",
                  background=[("active", "#FFFFFF"), ("!disabled", "#FFFFFF")],
                  foreground=[("active", "#003366"), ("!disabled", "#003366")])
        style.map("Dash.Treeview",
                  foreground=[("selected", "white"),  ("!disabled", "white")],
                  background=[("selected", "#34495e"), ("!disabled", "#1a1a1a")])

        # Header
        header = tk.Frame(self._dash, bg="#000000")
        header.pack(fill="x", pady=20)

        tk.Label(header, text="🏆 LEADERBOARD",
                 font=(main_font, 28, "bold"),
                 bg="#000000", fg="#FFD700").pack(side="left", padx=50)

        right = tk.Frame(header, bg="#000000")
        right.pack(side="right", padx=50)

        try:
            img = Image.open(resource_path("boule icon.png"))
            img = img.resize((80, 80), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            icon_lbl = tk.Label(right, image=photo, bg="#000000")
            icon_lbl.image = photo  # prevent GC
            icon_lbl.pack(side="right", padx=10)
        except Exception as exc:
            print(f"Icon not loaded: {exc}")

        self._dash_clock = tk.Label(right, text="", font=("Consolas", 24),
                                    bg="#000000", fg="#00FF00")
        self._dash_clock.pack(side="right", padx=20)

        # Announcement bar (bottom — packed first so it always stays pinned)
        self._dash_msg = tk.Label(self._dash, text="WELCOME!",
                                  font=(main_font, 36, "bold"),
                                  bg="#c0392b", fg="white", pady=10)
        self._dash_msg.pack(side="bottom", fill="x")

        # Bottom section — fixed pixel height so font size doesn't affect sizing
        # Mac renders Helvetica Neue 32 bold at ~62px per line; label + padding ~80px extra
        line_px   = 62
        pad_px    = 80
        n_lines   = self._max_terrains() + 2
        txt_px    = n_lines * line_px + pad_px

        bottom = tk.Frame(self._dash, bg="#000000", height=txt_px)
        bottom.pack(side="bottom", fill="x")
        bottom.pack_propagate(False)  # hold the fixed height

        tk.Label(bottom, text="CURRENT LANE ASSIGNMENTS",
                 font=(main_font, 26, "bold"),
                 bg="#000000", fg="#00FF7F").pack(pady=5)

        self._dash_match_text = tk.Text(
            bottom, font=(main_font, 32, "bold"),
            bg="#000000", fg="#FFFFFF", relief="flat", cursor="arrow",
            padx=10, pady=12
        )
        self._dash_match_text.pack(fill="both", expand=True, padx=50, pady=(0, 10))

        # Standings tree — takes all remaining space between header and bottom section
        self._dash_tree = ttk.Treeview(
            self._dash,
            columns=("rank", "name", "wins", "diff"),
            show="headings", style="Dash.Treeview"
        )
        for col, label, width, anchor in [
            ("rank", "Rank",         80,  "center"),
            ("name", "Player / Team",500, "w"),
            ("wins", "Wins",         80,  "center"),
            ("diff", "+/-",          80,  "center"),
        ]:
            self._dash_tree.heading(col, text=label)
            self._dash_tree.column(col, width=width, anchor=anchor)
        self._dash_tree.pack(fill="both", expand=True, padx=50, pady=10)

        self._scroll_idx = 0
        self._standings_dirty = False     # standings just about to be populated

        # Populate standings once immediately, then start the independent loops
        self._repopulate_dash_standings()
        self._update_dashboard_live()          # clock / lanes / ticker — every second
        self._dash.after(1500, self._auto_scroll_leaderboard)  # scroll starts after a short pause

    def _close_dashboard(self):
        """Clean shutdown — cancel pending after() calls before destroying."""
        if self._dash_after_id:
            try:
                self._dash.after_cancel(self._dash_after_id)
            except Exception:
                pass
            self._dash_after_id = None
        if self._dash_is_alive():
            self._dash.destroy()

    def _update_dashboard(self):
        """Called from _refresh_all whenever data changes. Marks standings dirty
        so the scroll loop will repopulate them at the next top-of-list opportunity."""
        if not self._dash_is_alive():
            return
        self._standings_dirty = True

    def _repopulate_dash_standings(self):
        """Wipe and refill the leaderboard tree. Only called when scroll is at position 0."""
        for row in self._dash_tree.get_children():
            self._dash_tree.delete(row)
        for i, p in enumerate(self.db.get_standings(), 1):
            self._dash_tree.insert("", "end",
                values=(i, f"  {p['name']}", p["wins"], p["diff"]))
        self._standings_dirty = False

    def _update_dashboard_live(self):
        """Runs every second. Updates clock, lane assignments, and ticker only.
        Never touches the standings tree — that is owned by the scroll loop."""
        if not self._dash_is_alive():
            return

        # Clock
        self._dash_clock.config(text=datetime.datetime.now().strftime("%H:%M:%S"))

        # Lane assignments — playing games + up to 2 waiting
        self._dash_match_text.config(state="normal")
        self._dash_match_text.delete("1.0", "end")
        matches = self.db.get_playing_matches()
        waiting = self.db.get_waiting_matches(limit=2)
        if matches:
            for m in matches:
                self._dash_match_text.insert(
                    "end", f"LANE {m['terrain']}:   {m['t1']}   vs   {m['t2']}\n"
                )
            for w in waiting:
                self._dash_match_text.insert(
                    "end", f"  ⏳   {w['t1']}   vs   {w['t2']}\n"
                )
        else:
            self._dash_match_text.insert("end", "\n\n— ROUND FINISHED / WAITING —")

        self._dash_match_text.tag_add("center", "1.0", "end")
        self._dash_match_text.tag_configure("center", justify="center", spacing1=15)
        self._dash_match_text.config(state="disabled")

        # Announcement ticker
        msg = self.announce_entry.get().strip()
        self._dash_msg.config(text=msg or "WELCOME TO THE TOURNAMENT!")

        # Schedule exactly ONE next call (stored so we can cancel it)
        self._dash_after_id = self._dash.after(1000, self._update_dashboard_live)

    def _auto_scroll_leaderboard(self):
        if not self._dash_is_alive():
            return

        visible = 11  # rows shown without scrolling

        # --- At the top: apply any pending standings update then start the crawl ---
        if self._scroll_idx == 0:
            if self._standings_dirty:
                self._repopulate_dash_standings()
            items = self._dash_tree.get_children()
            if not items:
                self._dash.after(2000, self._auto_scroll_leaderboard)
                return
            # If everything fits on screen there is nothing to scroll — just wait
            if len(items) <= visible:
                self._dash.after(5000, self._auto_scroll_leaderboard)
                return
            # Fast-forward the index past the initially visible rows
            self._scroll_idx = visible

        items = self._dash_tree.get_children()

        if self._scroll_idx < len(items):
            # Crawl one row at a time
            self._dash_tree.see(items[self._scroll_idx])
            self._scroll_idx += 1
            # Longer pause on the very last row so the bottom names are readable
            delay = 6000 if self._scroll_idx >= len(items) else 2000
            self._dash.after(delay, self._auto_scroll_leaderboard)
        else:
            # Bottom reached — snap back to top and pause before next cycle
            self._scroll_idx = 0
            self._dash_tree.yview_moveto(0)
            self._dash.after(5000, self._auto_scroll_leaderboard)


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
