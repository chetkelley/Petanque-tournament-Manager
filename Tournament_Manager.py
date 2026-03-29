import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import pandas as pd
import datetime
import platform
import random
import os
from PIL import Image, ImageTk
import sys

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class PetanqueProMaster:
    def __init__(self, root):
        self.root = root
        self.root.title("Pétanque Pro - Tournament Director Edition")
        self.db_path = "tournament.db"
        self.init_db()
        
        # 1. BUILD the UI first
        self.setup_ui() 
        
        # 2. REFRESH the data only after the UI (match_list) is created
        self.refresh_all()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        # Players Table
        conn.execute('''CREATE TABLE IF NOT EXISTS players 
                        (id INTEGER PRIMARY KEY, name TEXT UNIQUE, wins INT DEFAULT 0, 
                         pf INT DEFAULT 0, pa INT DEFAULT 0, diff INT DEFAULT 0)''')
        # Current Round Matches
        conn.execute('''CREATE TABLE IF NOT EXISTS matches 
                        (id INTEGER PRIMARY KEY, t1 TEXT, t2 TEXT, terrain INT, status TEXT)''')
        # Enhanced Match History for Stats
        conn.execute('''CREATE TABLE IF NOT EXISTS history 
                        (id INTEGER PRIMARY KEY, team_a TEXT, team_b TEXT, 
                         score_a INT, score_b INT, round_num INT)''')
        conn.commit()
        conn.close()

    def setup_ui(self):
        self.tabs = ttk.Notebook(self.root)
        self.tab_standings = tk.Frame(self.tabs, padx=20, pady=20)
        self.tab_matches = tk.Frame(self.tabs, padx=20, pady=20)
        
        self.tabs.add(self.tab_standings, text=" 1. Leaderboard ")
        self.tabs.add(self.tab_matches, text=" 2. Live Matches & Draw ")
        self.tabs.pack(expand=True, fill="both")

        # --- TAB 1: STANDINGS & REGISTRATION ---
        reg_frame = tk.LabelFrame(self.tab_standings, text="Tournament Management", padx=10, pady=10)
        reg_frame.pack(fill="x", pady=5)
        
        # --- ROW 1: Team Entry & Buttons ---
        row1 = tk.Frame(reg_frame)
        row1.pack(fill="x", pady=5)

        self.entry_name = tk.Entry(row1, width=25, font=("Arial", 12))
        self.entry_name.pack(side="left", padx=5)
        self.entry_name.bind("<Return>", lambda e: self.add_player())
        
        tk.Button(row1, text="Add Team", command=self.add_player, bg="#ecf0f1").pack(side="left", padx=2)
        tk.Button(row1, text="Delete Selected", command=self.delete_player, fg="orange").pack(side="left", padx=2)
        
        # Dashboard Button (The Dark Blue one)
        tk.Button(row1, text="OPEN PUBLIC DASHBOARD", command=self.open_dashboard, 
                  bg="#ecf0f1", fg="#00008B", font=("Arial", 10, "bold")).pack(side="right", padx=5)

        tk.Button(row1, text="EXPORT TO EXCEL", command=self.export_to_excel, bg="#27ae60", fg="black").pack(side="right", padx=5)
        tk.Button(row1, text="RESET DATA", fg="red", command=self.reset_tournament).pack(side="right")

        # --- ROW 2: Announcement Bar (Now Below) ---
        row2 = tk.Frame(reg_frame)
        row2.pack(fill="x", pady=(10, 0)) # Add a little top padding to separate it

        tk.Label(row2, text="📢 BOARDCAST MESSAGE:", font=("Arial", 10, "bold")).pack(side="left", padx=5)
        self.announce_entry = tk.Entry(row2, font=("Arial", 12), fg="blue")
        self.announce_entry.pack(side="left", fill="x", expand=True, padx=10)
        self.announce_entry.insert(0, "Welcome to the Tournament!")
        
        # Let her press Enter in this box to update the dashboard immediately
        self.announce_entry.bind("<Return>", lambda e: self.update_dashboard())
        
        tk.Label(row2, text="(Press Enter to Update)", font=("Arial", 8), fg="gray").pack(side="left")

        cols = ("Rank", "Team Name", "Wins", "Points For", "Points Against", "Net Diff")
        self.tree = ttk.Treeview(self.tab_standings, columns=cols, show="headings")
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, anchor="center", width=120)
        self.tree.pack(expand=True, fill="both", pady=10)

     # --- TAB 2: MATCHES & DRAW ---
        ctrl_frame = tk.LabelFrame(self.tab_matches, text="Tournament Control", padx=5, pady=5)
        ctrl_frame.pack(fill="x")
        
        # Column 0-1: Lanes (Terrains)
        tk.Label(ctrl_frame, text="Lanes:").grid(row=0, column=0, padx=2)
        self.terrain_count = tk.Entry(ctrl_frame, width=3)
        self.terrain_count.insert(0, "3") 
        self.terrain_count.grid(row=0, column=1, padx=2)
        
        # Column 2-3: System Dropdown
        tk.Label(ctrl_frame, text="System:").grid(row=0, column=2, padx=5)
        self.tourney_type = ttk.Combobox(ctrl_frame, 
                                         values=["Swiss Ladder", "Super Melee", "Single Elimination"], 
                                         state="readonly", width=12)
        self.tourney_type.set("Swiss Ladder")
        self.tourney_type.grid(row=0, column=3, padx=2)
        
        # Column 4: Generate (Blue-ish)
        tk.Button(ctrl_frame, text="GENERATE", command=self.handle_draw_logic, 
                  bg="#3498db", fg="black", font=("Arial", 10, "bold")).grid(row=0, column=4, padx=5)

        # Column 5: Undo (Orange-ish)
        tk.Button(ctrl_frame, text="UNDO LAST", command=self.undo_last_score, 
                  bg="#f39c12", fg="black").grid(row=0, column=5, padx=5)
        
        # Column 6: Hint Label
        tk.Label(ctrl_frame, text="(Double-click to score)", fg="gray", font=("Arial", 9)).grid(row=0, column=6, padx=5)

        # --- THE MATCH LIST (This MUST be named self.match_list) ---
        self.match_list = ttk.Treeview(self.tab_matches, columns=("id", "t", "t1", "vs", "t2", "status"), show="headings")
        
        # Define Columns
        self.match_list.heading("id", text="ID")
        self.match_list.heading("t", text="Lanes")
        self.match_list.heading("t1", text="Team 1")
        self.match_list.heading("vs", text="vs")
        self.match_list.heading("t2", text="Team 2")
        self.match_list.heading("status", text="Status")
        
        # Set Widths
        self.match_list.column("id", width=40, anchor="center")
        self.match_list.column("t", width=60, anchor="center")
        self.match_list.column("t1", width=200, anchor="center")
        self.match_list.column("vs", width=40, anchor="center")
        self.match_list.column("t2", width=200, anchor="center")
        self.match_list.column("status", width=100, anchor="center")
        
        self.match_list.pack(fill="both", expand=True, pady=10)
        self.match_list.bind("<Double-1>", self.on_match_double_click)
        
        # Column 0-1: Terrains
        tk.Label(ctrl_frame, text="Lanes:").grid(row=0, column=0, padx=2)
        self.terrain_count = tk.Entry(ctrl_frame, width=3)
        self.terrain_count.insert(0, "3") 
        self.terrain_count.grid(row=0, column=1, padx=2)
        
        # Column 2-3: System
        tk.Label(ctrl_frame, text="System:").grid(row=0, column=2, padx=5)
        self.tourney_type = ttk.Combobox(ctrl_frame, 
                                         values=["Swiss Ladder", "Super Melee", "Single Elimination"], 
                                         state="readonly", width=12)
        self.tourney_type.set("Swiss Ladder")
        self.tourney_type.grid(row=0, column=3, padx=2)
        
        # Column 4: Generate (Blue)
        tk.Button(ctrl_frame, text="GENERATE", command=self.handle_draw_logic, 
                  bg="#3498db", fg="black", font=("Arial", 10, "bold")).grid(row=0, column=4, padx=5)

        # Column 5: Undo (Orange)
        tk.Button(ctrl_frame, text="UNDO LAST", command=self.undo_last_score, 
                  bg="#f39c12", fg="black").grid(row=0, column=5, padx=5)
        
        # Column 6: Shortened Hint
        tk.Label(ctrl_frame, text="(Double-click to score)", fg="gray", font=("Arial", 9)).grid(row=0, column=6, padx=5)

    # --- LOGIC ---

    def add_player(self):
        name = self.entry_name.get().strip()
        if name:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("INSERT INTO players (name) VALUES (?)", (name,))
                conn.commit()
                self.entry_name.delete(0, tk.END)
                self.refresh_all()
            except: messagebox.showerror("Error", "Team already exists.")
            conn.close()
    def delete_player(self):
        """Removes the highlighted player from the standings."""
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("Selection Error", "Please click a name in the list first to select them.")
            return
        
        # Get the name from the second column (index 1) of the treeview
        player_name = self.tree.item(selected_item)['values'][1]
        
        if messagebox.askyesno("Confirm Delete", f"Remove '{player_name}' from the tournament?"):
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM players WHERE name=?", (player_name,))
            conn.commit()
            conn.close()
            self.refresh_all()

    def generate_swiss_draw(self):
        conn = sqlite3.connect(self.db_path)
        players = [row[0] for row in conn.execute("SELECT name FROM players ORDER BY wins DESC, diff DESC").fetchall()]
        
        if len(players) < 2:
            messagebox.showwarning("Warning", "Need at least 2 teams!")
            return

        # Check for unfinished matches
        active = conn.execute("SELECT id FROM matches WHERE status='Playing' OR status='Waiting'").fetchone()
        if active:
            if not messagebox.askyesno("Warning", "A round is currently in progress. Generating a new one will wipe current matches. Continue?"):
                return

        def played_before(t1, t2):
            res = conn.execute("SELECT id FROM history WHERE (team_a=? AND team_b=?) OR (team_a=? AND team_b=?)", (t1, t2, t2, t1)).fetchone()
            return res is not None

        paired = []
        unpaired = list(players)
        
        # Swiss Pairing Logic
        while len(unpaired) >= 2:
            t1 = unpaired.pop(0)
            partner_found = False
            for i in range(len(unpaired)):
                if not played_before(t1, unpaired[i]):
                    paired.append((t1, unpaired.pop(i)))
                    partner_found = True
                    break
            if not partner_found:
                paired.append((t1, unpaired.pop(0)))

        if unpaired: # Handle Bye
            bye_team = unpaired[0]
            conn.execute("UPDATE players SET wins=wins+1, pf=pf+13, diff=diff+13 WHERE name=?", (bye_team,))
            messagebox.showinfo("BYE", f"{bye_team} gets a BYE (13-0 win)")

        conn.execute("DELETE FROM matches")
        max_t = int(self.terrain_count.get())
        for i, (p1, p2) in enumerate(paired, 1):
            status = "Playing" if i <= max_t else "Waiting"
            terr = i if status == "Playing" else 0
            conn.execute("INSERT INTO matches (t1, t2, terrain, status) VALUES (?,?,?,?)", (p1, p2, terr, status))
        
        conn.commit()
        conn.close()
        self.refresh_all()

    def on_match_double_click(self, event):
        item = self.match_list.selection()[0]
        val = self.match_list.item(item, "values")
        if val[5] != "Playing": return

        pop = tk.Toplevel(self.root)
        pop.title("Score Entry")
        pop.geometry("300x180")
        
        tk.Label(pop, text=f"{val[2]} vs {val[4]}", font=("Arial", 10, "bold")).pack(pady=10)
        e = tk.Entry(pop, font=("Arial", 14), justify="center")
        e.insert(0, "13-0")
        e.pack(pady=5)
        e.focus_set()
        e.selection_range(0, tk.END)

        def save():
            try:
                s1, s2 = map(int, e.get().split("-"))
                self.record_score(val[0], val[1], val[2], val[4], s1, s2)
                pop.destroy()
            except: messagebox.showerror("Error", "Use format 13-5")

        e.bind("<Return>", lambda ev: save())
        tk.Button(pop, text="Save (Enter)", command=save, bg="#2ecc71").pack(pady=10)

    def record_score(self, m_id, terrain, t1, t2, s1, s2):
        conn = sqlite3.connect(self.db_path)
        
        # Helper to split "John, Sarah & Robert" into ['John', 'Sarah', 'Robert']
        def get_individuals(team_string):
            # Replace '&' with ',' then split by ','
            names = team_string.replace(' & ', ',').split(',')
            return [n.strip() for n in names]

        players_t1 = get_individuals(t1)
        players_t2 = get_individuals(t2)

        # 1. Update Every Individual in Team 1
        for name in players_t1:
            conn.execute("""UPDATE players SET pf=pf+?, pa=pa+?, wins=wins+?, diff=diff+? 
                            WHERE name=?""", 
                         (s1, s2, (1 if s1 > s2 else 0), (s1 - s2), name))
        
        # 2. Update Every Individual in Team 2
        for name in players_t2:
            conn.execute("""UPDATE players SET pf=pf+?, pa=pa+?, wins=wins+?, diff=diff+? 
                            WHERE name=?""", 
                         (s2, s1, (1 if s2 > s1 else 0), (s2 - s1), name))
        
        # 3. Add to Statistical History (The Manager's Excel Data)
        conn.execute("INSERT INTO history (team_a, team_b, score_a, score_b) VALUES (?,?,?,?)", 
                     (t1, t2, s1, s2))
        
        # 4. Handle Terrain Queue
        conn.execute("UPDATE matches SET status='Finished', terrain=0 WHERE id=?", (m_id,))
        waiting = conn.execute("SELECT id FROM matches WHERE status='Waiting' LIMIT 1").fetchone()
        if waiting:
            conn.execute("UPDATE matches SET status='Playing', terrain=? WHERE id=?", (terrain, waiting[0]))
        
        conn.commit()
        conn.close()
        self.refresh_all()

    def export_to_excel(self):
        try:
            conn = sqlite3.connect(self.db_path)
            # Standings Sheet
            df_standings = pd.read_sql_query("SELECT name as Team, wins as Wins, pf as PF, pa as PA, diff as Diff FROM players ORDER BY wins DESC, diff DESC", conn)
            # History Sheet
            df_history = pd.read_sql_query("SELECT team_a as 'Team 1', score_a as 'Score 1', score_b as 'Score 2', team_b as 'Team 2' FROM history", conn)
            
            with pd.ExcelWriter("Tournament_Results.xlsx", engine="openpyxl") as writer:
                df_standings.to_excel(writer, sheet_name="Final Rankings", index=False)
                df_history.to_excel(writer, sheet_name="Match History", index=False)
            
            conn.close()
            messagebox.showinfo("Export Success", f"Saved to {os.path.abspath('Tournament_Results.xlsx')}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Check if Excel file is already open!\nError: {e}")

    def reset_tournament(self):
        if messagebox.askyesno("Confirm", "Wipe EVERYTHING?"):
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM players"); conn.execute("DELETE FROM matches"); conn.execute("DELETE FROM history")
            conn.commit(); conn.close(); self.refresh_all()

    def refresh_all(self):
        conn = sqlite3.connect(self.db_path)
        for i in self.tree.get_children(): self.tree.delete(i)
        players = conn.execute("SELECT name, wins, pf, pa, diff FROM players ORDER BY wins DESC, diff DESC").fetchall()
        for i, p in enumerate(players, 1):
            self.tree.insert("", "end", values=(i, p[0], p[1], p[2], p[3], p[4]))
            
        for i in self.match_list.get_children(): self.match_list.delete(i)
        matches = conn.execute("SELECT id, terrain, t1, 'vs', t2, status FROM matches").fetchall()
        for m in matches:
            t_disp = m[1] if m[1] > 0 else "-"
            self.match_list.insert("", "end", values=(m[0], t_disp, m[2], m[3], m[4], m[5]))
        conn.close()
        if hasattr(self, 'dash') and self.dash.winfo_exists():
            self.update_dashboard()

    def handle_draw_logic(self):
        """This function checks the dropdown and picks the right math."""
        mode = self.tourney_type.get()
        if mode == "Swiss Ladder":
            self.generate_swiss_draw()
        elif mode == "Super Melee":
            self.generate_super_melee()
        elif mode == "Single Elimination":
            self.generate_elimination_draw()

    def generate_super_melee(self):
        """Universal Melee: Actually mixes 2v2 and 3v3 so NO ONE is left out."""
        conn = sqlite3.connect(self.db_path)
        players = [row[0] for row in conn.execute("SELECT name FROM players").fetchall()]
        random.shuffle(players)
        
        count = len(players)
        if count < 4:
            messagebox.showwarning("Warning", "Need at least 4 players!")
            return

        conn.execute("DELETE FROM matches")
        max_t = int(self.terrain_count.get())
        temp_players = list(players)
        
        # 1. Handle the "Bye" if total is odd (e.g. 11, 13, 15)
        if count % 2 != 0:
            bye_player = temp_players.pop()
            conn.execute("UPDATE players SET wins=wins+1, pf=pf+13, diff=diff+13 WHERE name=?", (bye_player,))
            messagebox.showinfo("Bye", f"{bye_player} receives a BYE.")

        matches_to_create = []
        
        # 2. Logic to pivot to 3v3 if the remainder is awkward
        # This loop runs only if we have enough for a 3v3 AND the remaining count 
        # isn't a clean multiple of 4.
        while len(temp_players) >= 6 and (len(temp_players) % 4 != 0):
            p = [temp_players.pop(0) for _ in range(6)]
            matches_to_create.append((f"{p[0]}, {p[1]} & {p[2]}", f"{p[3]}, {p[4]} & {p[5]}"))

        # 3. Create standard 2v2 Matches with everything else
        while len(temp_players) >= 4:
            p = [temp_players.pop(0) for _ in range(4)]
            matches_to_create.append((f"{p[0]} & {p[1]}", f"{p[2]} & {p[3]}"))

        # 4. Save to Database
        for i, (team_a, team_b) in enumerate(matches_to_create, 1):
            status = "Playing" if i <= max_t else "Waiting"
            terr = i if status == "Playing" else 0
            conn.execute("INSERT INTO matches (t1, t2, terrain, status) VALUES (?,?,?,?)", 
                         (team_a, team_b, terr, status))
        
        conn.commit()
        conn.close()
        self.refresh_all()

    def undo_last_score(self):
        """Reverses the last result and reverts the existing match to 'Playing' status."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 1. Pull the last entry from history
        last_match = cursor.execute("SELECT id, team_a, team_b, score_a, score_b FROM history ORDER BY id DESC LIMIT 1").fetchone()
        
        if not last_match:
            messagebox.showinfo("Undo", "No match history found to undo.")
            conn.close()
            return

        h_id, t1_str, t2_str, s1, s2 = last_match
        if not messagebox.askyesno("Confirm Undo", f"Undo result: {t1_str} ({s1}) vs {t2_str} ({s2})?"):
            conn.close()
            return

        # Helper to handle 'Team A & Team B' naming
        def get_individuals(name_str):
            return [n.strip() for n in name_str.replace(' & ', ',').split(',')]

        p1, p2 = get_individuals(t1_str), get_individuals(t2_str)

        # 2. Reverse the Stats for all individuals in the teams
        for n in p1:
            cursor.execute("UPDATE players SET pf=pf-?, pa=pa-?, wins=wins-?, diff=diff-? WHERE name=?", 
                         (s1, s2, (1 if s1 > s2 else 0), (s1 - s2), n))
        for n in p2:
            cursor.execute("UPDATE players SET pf=pf-?, pa=pa-?, wins=wins-?, diff=diff-? WHERE name=?", 
                         (s2, s1, (1 if s2 > s1 else 0), (s2 - s1), n))

        # 3. Find a Free Terrain for the reverted match
        max_t = int(self.terrain_count.get())
        occupied = [r[0] for r in cursor.execute("SELECT terrain FROM matches WHERE status='Playing'").fetchall()]
        
        assigned_terrain = 0
        new_status = "Waiting"
        
        for t in range(1, max_t + 1):
            if t not in occupied:
                assigned_terrain = t
                new_status = "Playing"
                break

        # 4. THE FIX: Update the EXISTING match instead of Inserting a new one
        # We look for the match involving these teams that is currently 'Finished'
        cursor.execute("""
            UPDATE matches 
            SET terrain = ?, status = ? 
            WHERE ((t1 = ? AND t2 = ?) OR (t1 = ? AND t2 = ?)) 
            AND status = 'Finished'
        """, (assigned_terrain, new_status, t1_str, t2_str, t2_str, t1_str))

        # 5. Clean up history
        cursor.execute("DELETE FROM history WHERE id=?", (h_id,))
        
        conn.commit()
        conn.close()
        self.refresh_all()
        
        msg = f"Reversed! Match is back on Terrain {assigned_terrain}." if assigned_terrain > 0 else "Reversed! Match moved to Waiting list."
        messagebox.showinfo("Success", msg)

    def open_dashboard(self):
        """High-Visibility Scoreboard for Windows Monitors."""
        self.dash = tk.Toplevel(self.root)
        self.dash.title("OFFICIAL TOURNAMENT SCOREBOARD")
        self.dash.state('zoomed') # This opens the window MAXIMIZED on Windows
        self.dash.configure(bg="#000000") # Pure black for maximum contrast

        # --- Header Section ---
        header_frame = tk.Frame(self.dash, bg="#000000")
        header_frame.pack(fill="x", pady=20)
        
        # Left Side: Title
        tk.Label(header_frame, text="🏆 LEADERBOARD", font=("Segoe UI", 28, "bold"), 
                 bg="#000000", fg="#FFD700").pack(side="left", padx=50)
        
        # Right Side: Icon and Clock Container
        right_container = tk.Frame(header_frame, bg="#000000")
        right_container.pack(side="right", padx=50)

        # THE ICON: Using a Petanque/Boule-style symbol or a Trophy
        try:
            img_path = resource_path("boule icon.png") # <--- USE THE FUNCTION
            img = Image.open(img_path)
            img = img.resize((100, 100), Image.Resampling.LANCZOS)
            
            # 1. Create the PhotoImage
            photo = ImageTk.PhotoImage(img)
            
            # 2. Create the Label
            icon_label = tk.Label(right_container, image=photo, bg="#000000")
            
            # 3. CRITICAL: Keep a manual reference
            icon_label.image = photo 
            
            icon_label.pack(side="right", padx=10)
            
        except Exception as e:
            print(f"Icon error: {e}")
        
        # Live Clock in the top right
        self.dash_clock = tk.Label(header_frame, text="", font=("Consolas", 24), 
                                   bg="#000000", fg="#00FF00")
        self.dash_clock.pack(side="right", padx=50)

        # --- Standings Table ---
        # Windows needs a specific 'style' to make Treeview fonts large
        style = ttk.Style()
        style.theme_use("clam") # 'clam' allows better color control on Windows
        # 1. THE MAIN ROWS (Black background, White text)
        style.configure("Dash.Treeview", 
                        background="#1a1a1a", 
                        foreground="#FFFFFF", 
                        fieldbackground="#1a1a1a", 
                        font=("Segoe UI", 20), 
                        rowheight=45)

        # 2. THE HEADERS (Dark Blue background, White BOLD text)
        style.configure("Dash.Treeview.Heading", 
                        background="#003366",   # Professional Navy Blue
                        foreground="#FFFFFF",   # Bright White Text
                        font=("Segoe UI", 22, "bold"))
        
        # This 'map' ensures the colors don't change when the manager clicks them
        style.map("Dash.Treeview.Heading",
                  background=[('active', '#004080')], # Slightly lighter blue on hover
                  foreground=[('active', '#FFFFFF')])

        self.dash_tree = ttk.Treeview(self.dash, columns=("rank", "name", "wins", "diff"), 
                                      show="headings", height=8, style="Dash.Treeview")
        self.dash_tree.heading("rank", text="RANK")
        self.dash_tree.heading("name", text="PLAYER / TEAM")
        self.dash_tree.heading("wins", text="WINS")
        self.dash_tree.heading("diff", text="+ / -")
        
        self.dash_tree.column("rank", width=100, anchor="center")
        self.dash_tree.column("wins", width=150, anchor="center")
        self.dash_tree.column("diff", width=150, anchor="center")
        self.dash_tree.pack(fill="x", padx=50)

        # --- Live Matches Section ---
        tk.Label(self.dash, text="📍 CURRENT LANE ASSIGNMENTS", font=("Segoe UI", 32, "bold"), 
                 bg="#000000", fg="#00FF7F").pack(pady=30)

        # 1. CREATE AND PACK THE ANNOUNCEMENT BAR FIRST (side="bottom")
        self.dash_msg = tk.Label(self.dash, text="WELCOME!", font=("Segoe UI", 36, "bold"), 
                                 bg="#c0392b", fg="white", pady=10)
        self.dash_msg.pack(side="bottom", fill="x")

        # 2. THEN CREATE THE MATCH TEXT AND LET IT FILL THE REMAINING CENTER SPACE
        self.dash_match_text = tk.Text(self.dash, font=("Segoe UI", 42, "bold"), 
                                      bg="#000000", fg="#FFFFFF", 
                                      relief="flat", cursor="arrow")
        # By packing this AFTER the bottom bar, it will only fill the gap in between
        self.dash_match_text.pack(fill="both", expand=True, padx=50, pady=10)
        
        # 3. Final call
        self.update_dashboard()

    def update_dashboard(self):
        """Updates data, live clock, and announcement bar for the public display."""
        if not hasattr(self, 'dash') or not self.dash.winfo_exists():
            return

        # 1. Update the Clock
        import datetime
        now = datetime.datetime.now().strftime("%H:%M:%S")
        if hasattr(self, 'dash_clock'):
            self.dash_clock.config(text=now)

        # 2. Update Standings Table
        for i in self.dash_tree.get_children(): 
            self.dash_tree.delete(i)
            
        conn = sqlite3.connect(self.db_path)
        standings = conn.execute("SELECT name, wins, diff FROM players ORDER BY wins DESC, diff DESC LIMIT 10").fetchall()
        for i, row in enumerate(standings, 1):
            self.dash_tree.insert("", "end", values=(i, f" {row[0]}", row[1], row[2]))

        # 3. Update Match Assignments (Massive Text)
        self.dash_match_text.config(state="normal")
        self.dash_match_text.delete("1.0", "end")
        matches = conn.execute("SELECT terrain, t1, t2 FROM matches WHERE status='Playing' ORDER BY terrain ASC").fetchall()
        
        if not matches:
            self.dash_match_text.insert("end", "\n\n--- ROUND FINISHED / WAITING ---")
        else:
            for row in matches:
                line = f"LANE {row[0]}:   {row[1]}   vs   {row[2]}\n"
                self.dash_match_text.insert("end", line)

        self.dash_match_text.tag_add("center", "1.0", "end")
        self.dash_match_text.tag_configure("center", justify='center', spacing1=15)
        self.dash_match_text.config(state="disabled")
        conn.close()

        # 4. Update the Announcement Bar
        if hasattr(self, 'announce_entry') and hasattr(self, 'dash_msg'):
            msg = self.announce_entry.get().strip()
            self.dash_msg.config(text=msg if msg else "WELCOME TO THE TOURNAMENT!")

        # 5. Refresh every 1 second (keeps clock and announcements snappy)
        self.dash.after(1000, self.update_dashboard)

if __name__ == "__main__":
    root = tk.Tk()
    # Lift window to front for Mac users
    root.lift()
    root.attributes('-topmost', True)
    root.after_idle(root.attributes, '-topmost', False)
    app = PetanqueProMaster(root)
    root.mainloop()