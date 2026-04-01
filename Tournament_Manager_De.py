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
        self.root.title("Pétanque Pro - Turnierverwaltung")
        self.db_path = "tournament.db"
        self.init_db()
        self.setup_ui()
        self.refresh_all()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS players (id INTEGER PRIMARY KEY, name TEXT UNIQUE, wins INTEGER DEFAULT 0, diff INTEGER DEFAULT 0, pf INTEGER DEFAULT 0, pa INTEGER DEFAULT 0)")
        conn.execute("CREATE TABLE IF NOT EXISTS matches (id INTEGER PRIMARY KEY, t1 TEXT, t2 TEXT, terrain INTEGER, status TEXT DEFAULT 'Spielt')")
        conn.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, team_a TEXT, team_b TEXT, score_a INTEGER, score_b INTEGER)")
        conn.commit()
        conn.close()

    def setup_ui(self):
        self.tabs = ttk.Notebook(self.root)
        self.tab_standings = tk.Frame(self.tabs, padx=20, pady=20)
        self.tab_matches = tk.Frame(self.tabs, padx=20, pady=20)
        
        self.tabs.add(self.tab_standings, text=" 1. Rangliste & Anmeldung ")
        self.tabs.add(self.tab_matches, text=" 2. Begegnungen & Auslosung ")
        self.tabs.pack(expand=True, fill="both")

        # --- TAB 1: RANNGLISTE & VERWALTUNG ---
        reg_frame = tk.LabelFrame(self.tab_standings, text="Turnier-Management", padx=10, pady=10)
        reg_frame.pack(fill="x", pady=5)
        
        row1 = tk.Frame(reg_frame)
        row1.pack(fill="x", pady=5)

        self.entry_name = tk.Entry(row1, width=25, font=("Arial", 12))
        self.entry_name.pack(side="left", padx=5)
        self.entry_name.bind("<Return>", lambda e: self.add_player())
        
        tk.Button(row1, text="Team hinzufügen", command=self.add_player).pack(side="left", padx=2)
        tk.Button(row1, text="Auswahl löschen", command=self.delete_player, fg="orange").pack(side="left", padx=2)
        
        tk.Button(row1, text="PUBLIC DASHBOARD ÖFFNEN", command=self.open_dashboard, 
                  bg="#ecf0f1", fg="#00008B", font=("Arial", 10, "bold")).pack(side="right", padx=5)

        tk.Button(row1, text="EXCEL EXPORT", command=self.export_to_excel, bg="#27ae60").pack(side="right", padx=5)
        tk.Button(row1, text="DATEN RESET", fg="red", command=self.reset_tournament).pack(side="right")

        row2 = tk.Frame(reg_frame)
        row2.pack(fill="x", pady=(10, 0))

        tk.Label(row2, text="📢 DURCHSAGE:", font=("Arial", 10, "bold")).pack(side="left", padx=5)
        self.announce_entry = tk.Entry(row2, font=("Arial", 12), fg="blue")
        self.announce_entry.pack(side="left", fill="x", expand=True, padx=10)
        self.announce_entry.insert(0, "Willkommen zum Turnier!")
        self.announce_entry.bind("<Return>", lambda e: self.update_dashboard())

        cols = ("name", "wins", "diff", "pf", "pa")
        self.tree = ttk.Treeview(self.tab_standings, columns=cols, show="headings")
        heads = ["Spieler / Team", "Siege", "+/-", "+", "-"]
        for col, head in zip(cols, heads):
            self.tree.heading(col, text=head)
            self.tree.column(col, anchor="center")
        self.tree.pack(fill="both", expand=True, pady=10)

        # --- TAB 2: BEGEGNUNGEN ---
        ctrl_frame = tk.LabelFrame(self.tab_matches, text="Turnier-Steuerung", padx=5, pady=5)
        ctrl_frame.pack(fill="x")
        
        tk.Label(ctrl_frame, text="Bahnen:").grid(row=0, column=0)
        self.terrain_count = tk.Entry(ctrl_frame, width=3)
        self.terrain_count.insert(0, "3") 
        self.terrain_count.grid(row=0, column=1)
        
        tk.Label(ctrl_frame, text="System:").grid(row=0, column=2, padx=5)
        self.tourney_type = ttk.Combobox(ctrl_frame, values=["Schweizer System", "Super Mêlée"], state="readonly", width=15)
        self.tourney_type.set("Schweizer System")
        self.tourney_type.grid(row=0, column=3)
        
        tk.Button(ctrl_frame, text="RUNDE AUSLOSEN", command=self.handle_draw_logic, bg="#3498db", font=("Arial", 10, "bold")).grid(row=0, column=4, padx=5)
        tk.Button(ctrl_frame, text="LETZTE KORREKTUR", command=self.undo_last_score, bg="#f39c12").grid(row=0, column=5)

        self.match_list = ttk.Treeview(self.tab_matches, columns=("id", "t", "t1", "vs", "t2", "status"), show="headings")
        for col, head in zip(self.match_list["columns"], ["Nr.", "Bahn", "Team 1", "vs", "Team 2", "Status"]):
            self.match_list.heading(col, text=head)
            self.match_list.column(col, anchor="center")
        self.match_list.pack(fill="both", expand=True, pady=10)
        self.match_list.bind("<Double-1>", self.on_match_double_click)

    # --- LOGIK FUNKTIONEN ---
    def add_player(self):
        name = self.entry_name.get().strip()
        if name:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("INSERT INTO players (name) VALUES (?)", (name,))
                conn.commit()
                self.entry_name.delete(0, tk.END)
                self.refresh_all()
            except: messagebox.showerror("Fehler", "Name existiert bereits!")
            finally: conn.close()

    def delete_player(self):
        selected = self.tree.selection()
        if not selected: return
        name = self.tree.item(selected[0])['values'][0]
        if messagebox.askyesno("Löschen", f"Soll '{name}' wirklich gelöscht werden?"):
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM players WHERE name=?", (name,))
            conn.commit()
            conn.close()
            self.refresh_all()

    def refresh_all(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        conn = sqlite3.connect(self.db_path)
        data = conn.execute("SELECT name, wins, diff, pf, pa FROM players ORDER BY wins DESC, diff DESC, pf DESC").fetchall()
        for row in data: self.tree.insert("", "end", values=row)

        for i in self.match_list.get_children(): self.match_list.delete(i)
        matches = conn.execute("SELECT id, terrain, t1, 'vs', t2, status FROM matches").fetchall()
        for m in matches: self.match_list.insert("", "end", values=m)
        conn.close()
        
        if hasattr(self, 'dash') and self.dash.winfo_exists():
            self.update_dashboard()

    def handle_draw_logic(self):
        conn = sqlite3.connect(self.db_path)
        players = [r[0] for r in conn.execute("SELECT name FROM players").fetchall()]
        if len(players) < 2:
            messagebox.showwarning("Warnung", "Nicht genug Spieler!")
            conn.close(); return
        random.shuffle(players)
        try: max_lanes = int(self.terrain_count.get())
        except: max_lanes = 1
        conn.execute("DELETE FROM matches") 
        match_count = 0
        for i in range(0, len(players)//2 * 2, 2):
            match_count += 1
            p1, p2 = players[i], players[i+1]
            lane = match_count if match_count <= max_lanes else 0
            status = 'Spielt' if lane > 0 else 'Wartend'
            conn.execute("INSERT INTO matches (t1, t2, terrain, status) VALUES (?,?,?,?)", (p1, p2, lane, status))
        conn.commit(); conn.close(); self.refresh_all()

    def on_match_double_click(self, event):
        item = self.match_list.selection()
        if not item: return
        values = self.match_list.item(item[0])['values']
        m_id, terrain, t1, vs, t2, status = values
        if status != 'Spielt': return
        res = simpledialog.askstring("Ergebnis", f"{t1} vs {t2}\nFormat: 13-5")
        if res and "-" in res:
            try:
                s1, s2 = map(int, res.split("-"))
                self.submit_score(m_id, t1, t2, s1, s2)
            except: pass

    def submit_score(self, m_id, t1, t2, s1, s2):
        conn = sqlite3.connect(self.db_path)
        
        # 1. Die Bahnnummer des Spiels finden, das gerade beendet wurde
        curr_match = conn.execute("SELECT terrain FROM matches WHERE id=?", (m_id,)).fetchone()
        free_lane = curr_match[0] if curr_match else 0

        # 2. Match als beendet markieren und von der Bahn nehmen
        conn.execute("UPDATE matches SET status='Beendet', terrain=0 WHERE id=?", (m_id,))
        
        # 3. Statistiken der Spieler aktualisieren
        w1, w2 = (1, 0) if s1 > s2 else (0, 1)
        conn.execute("UPDATE players SET wins=wins+?, diff=diff+?, pf=pf+?, pa=pa+? WHERE name=?", (w1, s1-s2, s1, s2, t1))
        conn.execute("UPDATE players SET wins=wins+?, diff=diff+?, pf=pf+?, pa=pa+? WHERE name=?", (w2, s2-s1, s2, s1, t2))
        conn.execute("INSERT INTO history (team_a, team_b, score_a, score_b) VALUES (?,?,?,?)", (t1, t2, s1, s2))

        # 4. AUTOMATISCHES NACHRÜCKEN:
        # Prüfen, ob ein Spiel wartet. Wenn ja, bekommt es die frei gewordene Bahn.
        if free_lane > 0:
            next_match = conn.execute("SELECT id FROM matches WHERE status='Wartend' LIMIT 1").fetchone()
            if next_match:
                conn.execute("UPDATE matches SET status='Spielt', terrain=? WHERE id=?", (free_lane, next_match[0]))
        
        conn.commit()
        conn.close()
        self.refresh_all()

    def undo_last_score(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        last = cursor.execute("SELECT * FROM history ORDER BY id DESC LIMIT 1").fetchone()
        if last:
            h_id, t1, t2, s1, s2 = last
            if messagebox.askyesno("Korrektur", f"Ergebnis {t1} {s1}:{s2} {t2} löschen?"):
                w1, w2 = (1, 0) if s1 > s2 else (0, 1)
                conn.execute("UPDATE players SET wins=wins-?, diff=diff-?, pf=pf-?, pa=pa-? WHERE name=?", (w1, s1-s2, s1, s2, t1))
                conn.execute("UPDATE players SET wins=wins-?, diff=diff-?, pf=pf-?, pa=pa-? WHERE name=?", (w2, s2-s1, s2, s1, t2))
                conn.execute("UPDATE matches SET status='Spielt' WHERE (t1=? AND t2=?) OR (t1=? AND t2=?)", (t1, t2, t2, t1))
                conn.execute("DELETE FROM history WHERE id=?", (h_id,))
                conn.commit()
        conn.close(); self.refresh_all()

    def reset_tournament(self):
        if messagebox.askyesno("Reset", "Daten löschen?"):
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM players"); conn.execute("DELETE FROM matches"); conn.execute("DELETE FROM history")
            conn.commit(); conn.close(); self.refresh_all()

    def export_to_excel(self):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("SELECT * FROM players ORDER BY wins DESC, diff DESC", conn)
        df.to_excel("Turnierergebnisse.xlsx", index=False)
        conn.close()
        messagebox.showinfo("Export", "Gespeichert als 'Turnierergebnisse.xlsx'")

    # --- DASHBOARD LOGIC (Updated for Cross-Platform & Styling) ---
    def open_dashboard(self):
        self.dash = tk.Toplevel(self.root)
        self.dash.title("OFFIZIELLE ANZEIGE")
        self.dash.configure(bg="#000000")

        current_os = platform.system()
        style = ttk.Style()

        # --- THE CORRECTED THEME LOGIC ---
        if current_os == "Darwin":  # macOS
            style.theme_use("aqua")  # <--- Switch back to native Mac
            main_font = "Helvetica Neue"
            header_bg = "#FFFFFF"     # White background for Mac headers
            header_fg = "#003366"     # Dark blue text
            row_h = 60
        else:  # Windows
            style.theme_use("clam")  # Keep clam for Windows
            main_font = "Segoe UI"
            header_bg = "#003366"     # Navy background for Windows
            header_fg = "#FFFFFF"     # White text
            row_h = 50

        if current_os == "Windows": 
            self.dash.state('zoomed')
        else:
            # Optional: On Mac, you might want to force it to a large size manually
            self.dash.geometry("1200x800")

        # Style Configurations
        style.configure("Dash.Treeview", background="#1a1a1a", foreground="white", fieldbackground="#1a1a1a", font=(main_font, 32), rowheight=row_h)
        style.configure("Dash.Treeview.Heading", background=header_bg, foreground=header_fg, font=(main_font, 22, "bold"))
        
        # Prevent "Black Text" on focus loss
        style.map("Dash.Treeview", 
                  foreground=[('selected', 'white'), ('!disabled', 'white')],
                  background=[('selected', '#34495e'), ('!disabled', '#1a1a1a')])

        # Header Section
        header_frame = tk.Frame(self.dash, bg="#000000")
        header_frame.pack(fill="x", pady=20)
        
        tk.Label(header_frame, text="🏆 RANGLISTE", font=(main_font, 28, "bold"), bg="#000000", fg="#FFD700").pack(side="left", padx=50)
        
        right_container = tk.Frame(header_frame, bg="#000000")
        right_container.pack(side="right", padx=50)

        try:
            img_path = resource_path("boule icon.png")
            img = Image.open(img_path).resize((100, 100), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            icon_label = tk.Label(right_container, image=photo, bg="#000000")
            icon_label.image = photo 
            icon_label.pack(side="right", padx=10)
        except: pass
        
        self.dash_clock = tk.Label(right_container, text="", font=("Consolas", 24), bg="#000000", fg="#00FF00")
        self.dash_clock.pack(side="right", padx=10)

        # 1. Rankings Table (Height 12 for better proportions)
        self.dash_tree = ttk.Treeview(self.dash, columns=("rank", "name", "wins", "diff"), show="headings", height=12, style="Dash.Treeview")
        
        column_data = {
            "rank": ("RANG", 50),
            "name": ("SPIELER / TEAM", 400),
            "wins": ("SIEGE", 150),
            "diff": ("+/-", 150)
        }

        for col, (label, width) in column_data.items():
            self.dash_tree.heading(col, text=label)
            self.dash_tree.column(col, width=width, anchor="center" if col != "name" else "w")

        self.dash_tree.pack(fill="both", expand=True, padx=50, pady=10)

        # 2. Section Title
        tk.Label(self.dash, text="AKTUELL AUF DEN BAHNEN", font=(main_font, 24, "bold"), bg="#000000", fg="#00FF7F").pack(pady=10)

        # 3. The Announcement Banner (Bottom)
        self.dash_msg = tk.Label(self.dash, text="WILLKOMMEN!", font=(main_font, 32, "bold"), bg="#c0392b", fg="white", pady=10)
        self.dash_msg.pack(side="bottom", fill="x")

        # 4. The Match Text (Middle)
        self.dash_match_text = tk.Text(self.dash, font=(main_font, 32, "bold"), bg="#000000", fg="#FFFFFF", relief="flat")
        self.dash_match_text.pack(fill="both", expand=True, padx=50, pady=10)
        
        self.update_dashboard()
        self.dash.after(1000, self.auto_scroll_leaderboard)

    def auto_scroll_leaderboard(self):
        if not hasattr(self, 'dash') or not self.dash.winfo_exists(): return
        
        all_items = self.dash_tree.get_children()
        if not all_items: return

        if not hasattr(self, 'scroll_idx'): self.scroll_idx = 0
        
        # Adjust this to the number of rows visible when the app starts
        visible_rows = 11 

        if self.scroll_idx < len(all_items):
            if self.scroll_idx < visible_rows:
                # 1. FAST-FORWARD through initially visible rows
                self.scroll_idx += 1
                self.dash.after(10, self.auto_scroll_leaderboard)
            else:
                # 2. THE CRAWL: Move row-by-row
                self.dash_tree.see(all_items[self.scroll_idx])
                self.scroll_idx += 1
                
                # Check if we JUST hit the very last row
                if self.scroll_idx == len(all_items):
                    # --- PAUSE AT THE BOTTOM ---
                    # We reached the end. Wait 6 seconds so people can see the last names.
                    self.dash.after(6000, self.auto_scroll_leaderboard)
                else:
                    # Regular scrolling speed
                    self.dash.after(2000, self.auto_scroll_leaderboard)
        else:
            # 3. THE RESET: Snap back to the top after the pause is over
            self.scroll_idx = 0
            self.dash_tree.yview_moveto(0) 
            
            # Wait 5 seconds at the top before starting the next crawl
            self.dash.after(5000, self.auto_scroll_leaderboard)

    def reset_leaderboard(self):
        """Jumps back to the top and restarts the scroll loop after a pause."""
        if hasattr(self, 'dash') and self.dash.winfo_exists():
            self.dash_tree.yview_moveto(0)
            # Wait X milliseconds at the top so the leaders are visible
            self.dash.after(3000, self.auto_scroll_leaderboard)

    def update_dashboard(self):
        if not hasattr(self, 'dash') or not self.dash.winfo_exists(): return
        self.dash_clock.config(text=datetime.datetime.now().strftime("%H:%M:%S"))
        
        new_msg = self.announce_entry.get()
        self.dash_msg.config(text=new_msg.upper())
        
        for i in self.dash_tree.get_children(): self.dash_tree.delete(i)
        conn = sqlite3.connect(self.db_path)
        standings = conn.execute("SELECT name, wins, diff FROM players ORDER BY wins DESC, diff DESC").fetchall()
        for i, row in enumerate(standings, 1):
            self.dash_tree.insert("", "end", values=(i, f" {row[0]}", row[1], row[2]))

        active_matches = conn.execute("SELECT terrain, t1, t2 FROM matches WHERE status='Spielt' ORDER BY terrain ASC").fetchall()
        conn.close()

        self.dash_match_text.config(state="normal")
        self.dash_match_text.delete("1.0", "end")
        
        if not active_matches:
            self.dash_match_text.insert("end", "\n\n--- RUNDE BEENDET ---")
        else:
            for row in active_matches:
                self.dash_match_text.insert("end", f"BAHN {row[0]}:  {row[1]} vs {row[2]}\n")
        
        self.dash_match_text.tag_add("center", "1.0", "end")
        self.dash_match_text.tag_configure("center", justify='center', spacing1=10)
        self.dash_match_text.config(state="disabled")
        self.dash.after(1000, self.update_dashboard)

if __name__ == "__main__":
    root = tk.Tk()
    root.lift()
    root.attributes('-topmost', True)
    root.after_idle(root.attributes, '-topmost', False)
    app = PetanqueProMaster(root)
    root.mainloop()