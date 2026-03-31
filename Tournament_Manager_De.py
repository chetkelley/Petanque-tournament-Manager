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
        
        # UI Setup
        self.setup_ui()
        
        # Initial Refresh
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

        # --- TAB 1: RANNGLISTE ---
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

        self.tree = ttk.Treeview(self.tab_standings, columns=("name", "wins", "diff", "pf", "pa"), show="headings")
        self.tree.heading("name", text="Spieler / Team")
        self.tree.heading("wins", text="Siege")
        self.tree.heading("diff", text="+/-")
        self.tree.heading("pf", text="+")
        self.tree.heading("pa", text="-")
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
        """Aktualisiert alle Tabellen und das öffentliche Dashboard."""
        # 1. Rangliste (Tab 1) leeren
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        conn = sqlite3.connect(self.db_path)
        # 2. Aktuelle Daten sortiert abrufen: Erst Siege, dann Differenz, dann Eigenpunkte
        standings_query = """
            SELECT name, wins, diff, pf, pa 
            FROM players 
            ORDER BY wins DESC, diff DESC, pf DESC
        """
        data = conn.execute(standings_query).fetchall()
        
        # 3. Neue Daten in die Rangliste schreiben
        for row in data:
            self.tree.insert("", "end", values=row)

        # 4. Begegnungen (Tab 2) aktualisieren
        for i in self.match_list.get_children():
            self.match_list.delete(i)
            
        matches = conn.execute("SELECT id, terrain, t1, 'vs', t2, status FROM matches").fetchall()
        for m in matches:
            self.match_list.insert("", "end", values=m)
            
        conn.close()
        
        # 5. Dashboard aktualisieren (falls offen)
        if hasattr(self, 'dash') and self.dash.winfo_exists():
            self.update_dashboard()

    def handle_draw_logic(self):
        """Erstellt eine neue Runde und weist Bahnen nur bis zum Limit zu."""
        conn = sqlite3.connect(self.db_path)
        players = [r[0] for r in conn.execute("SELECT name FROM players").fetchall()]
        
        if len(players) < 2:
            messagebox.showwarning("Warnung", "Nicht genug Spieler!")
            conn.close()
            return

        random.shuffle(players)
        
        try:
            max_lanes = int(self.terrain_count.get())
        except:
            max_lanes = 1
            
        conn.execute("DELETE FROM matches") 
        
        match_count = 0
        for i in range(0, len(players)//2 * 2, 2):
            match_count += 1
            p1, p2 = players[i], players[i+1]
            
            # Logik für die Warteschlange:
            if match_count <= max_lanes:
                # Bahn wird zugewiesen
                lane = match_count
                status = 'Spielt'
            else:
                # Keine Bahn frei -> Warteschleife
                lane = 0 # 0 bedeutet "Wartend"
                status = 'Wartend'
                
            conn.execute("INSERT INTO matches (t1, t2, terrain, status) VALUES (?,?,?,?)", 
                         (p1, p2, lane, status))
        
        conn.commit()
        conn.close()
        self.refresh_all()
        messagebox.showinfo("Erfolg", f"Runde ausgelost! {min(match_count, max_lanes)} Spiele aktiv.")

    def on_match_double_click(self, event):
        item = self.match_list.selection()
        if not item: 
            return
            
        # Get values from the selected row
        values = self.match_list.item(item[0])['values']
        m_id, terrain, t1, vs, t2, status = values

        print(f"Debug: Klick auf Spiel {m_id}, Status: {status}") # Check your terminal

        # We must check for 'Spielt' because that is what we set in setup_ui/init_db
        if status != 'Spielt':
            messagebox.showinfo("Info", f"Status ist '{status}'. Nur Spiele mit Status 'Spielt' können bearbeitet werden.")
            return
        
        # Open the score entry dialog
        res = simpledialog.askstring("Ergebnis eingeben", 
                                     f"Ergebnis für {t1} gegen {t2}\nFormat: 13-5")
        
        if res and "-" in res:
            try:
                s1, s2 = map(int, res.split("-"))
                self.submit_score(m_id, t1, t2, s1, s2)
            except ValueError:
                messagebox.showerror("Fehler", "Bitte das Ergebnis im Format '13-5' eingeben.")

    def submit_score(self, m_id, t1, t2, s1, s2):
        conn = sqlite3.connect(self.db_path)
        # Update Matches
        conn.execute("UPDATE matches SET status='Beendet' WHERE id=?", (m_id,))
        # Update Player 1
        w1 = 1 if s1 > s2 else 0
        conn.execute("UPDATE players SET wins=wins+?, diff=diff+?, pf=pf+?, pa=pa+? WHERE name=?", (w1, s1-s2, s1, s2, t1))
        # Update Player 2
        w2 = 1 if s2 > s1 else 0
        conn.execute("UPDATE players SET wins=wins+?, diff=diff+?, pf=pf+?, pa=pa+? WHERE name=?", (w2, s2-s1, s2, s1, t2))
        # History
        conn.execute("INSERT INTO history (team_a, team_b, score_a, score_b) VALUES (?,?,?,?)", (t1, t2, s1, s2))
        conn.commit()
        conn.close()
        self.refresh_all()

    def undo_last_score(self):
        """Macht das letzte Ergebnis rückgängig und setzt das Spiel auf 'Spielt'."""
        conn = sqlite3.connect(self.db_path)
        # We need a cursor to get the row ID
        cursor = conn.cursor()
        last = cursor.execute("SELECT * FROM history ORDER BY id DESC LIMIT 1").fetchone()
        
        if last:
            h_id, t1, t2, s1, s2 = last
            
            # Confirm with the manager
            if messagebox.askyesno("Korrektur", f"Ergebnis {t1} {s1}:{s2} {t2} wirklich löschen?"):
                # 1. Reverse player stats
                w1 = 1 if s1 > s2 else 0
                w2 = 1 if s2 > s1 else 0
                conn.execute("UPDATE players SET wins=wins-?, diff=diff-?, pf=pf-?, pa=pa-? WHERE name=?", (w1, s1-s2, s1, s2, t1))
                conn.execute("UPDATE players SET wins=wins-?, diff=diff-?, pf=pf-?, pa=pa-? WHERE name=?", (w2, s2-s1, s2, s1, t2))
                
                # 2. IMPORTANT FIX: Reset the match status so it can be played/edited again
                conn.execute("UPDATE matches SET status='Spielt' WHERE (t1=? AND t2=?) OR (t1=? AND t2=?)", (t1, t2, t2, t1))
                
                # 3. Delete from history
                conn.execute("DELETE FROM history WHERE id=?", (h_id,))
                conn.commit()
        else:
            messagebox.showinfo("Info", "Keine gespeicherten Ergebnisse gefunden.")
            
        conn.close()
        self.refresh_all()

    def reset_tournament(self):
        if messagebox.askyesno("Reset", "Alle Daten löschen?"):
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM players")
            conn.execute("DELETE FROM matches")
            conn.execute("DELETE FROM history")
            conn.commit()
            conn.close()
            self.refresh_all()

    def export_to_excel(self):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("SELECT * FROM players ORDER BY wins DESC, diff DESC", conn)
        df.to_excel("Turnierergebnisse.xlsx", index=False)
        conn.close()
        messagebox.showinfo("Export", "Erfolgreich als 'Turnierergebnisse.xlsx' gespeichert.")

    # --- DASHBOARD LOGIC ---
    def open_dashboard(self):
        self.dash = tk.Toplevel(self.root)
        self.dash.title("OFFIZIELLE ANZEIGE")
        if platform.system() == "Windows": self.dash.state('zoomed')
        self.dash.configure(bg="#000000")

        # --- Header Section ---
        header_frame = tk.Frame(self.dash, bg="#000000")
        header_frame.pack(fill="x", pady=20)
        
        # Left Side: Title
        tk.Label(header_frame, text="🏆 RANGLISTE", font=("Segoe UI", 28, "bold"), 
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
            
        # The Clock (moved slightly left of the icon)
        self.dash_clock = tk.Label(right_container, text="", font=("Consolas", 24), 
                                   bg="#000000", fg="#00FF00")
        self.dash_clock.pack(side="right", padx=10)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(    "Dash.Treeview", background="#1a1a1a", foreground="white", fieldbackground="#1a1a1a", font=("Segoe UI", 20), rowheight=45)
        style.configure("Dash.Treeview.Heading", background="#003366", foreground="white", font=("Segoe UI", 22, "bold"))

        self.dash_tree = ttk.Treeview(self.dash, columns=("rank", "name", "wins", "diff"), show="headings", height=8, style="Dash.Treeview")
        for col, head in zip(self.dash_tree["columns"], ["RANG", "SPIELER / TEAM", "SIEGE", "+/-"]):
            self.dash_tree.heading(col, text=head)
        self.dash_tree.pack(fill="x", padx=50)

        tk.Label(self.dash, text="AKTUELL AUF DEN BAHNEN", font=("Segoe UI", 32, "bold"), bg="#000000", fg="#00FF7F").pack(pady=20)

        self.dash_msg = tk.Label(self.dash, text="WILLKOMMEN!", font=("Segoe UI", 36, "bold"), bg="#c0392b", fg="white", pady=15)
        self.dash_msg.pack(side="bottom", fill="x")

        self.dash_match_text = tk.Text(self.dash, font=("Segoe UI", 42, "bold"), bg="#000000", fg="#FFFFFF", relief="flat")
        self.dash_match_text.pack(fill="both", expand=True, padx=50, pady=10)
        
        self.update_dashboard()

    def update_dashboard(self):
        if not hasattr(self, 'dash') or not self.dash.winfo_exists(): return
        
        # 1. Update Clock
        self.dash_clock.config(text=datetime.datetime.now().strftime("%H:%M:%S"))
        
        # 2. Update Banner (FETCH FROM ENTRY)
        new_msg = self.announce_entry.get()
        self.dash_msg.config(text=new_msg.upper())
        
        # 3. Update Rankings
        for i in self.dash_tree.get_children(): self.dash_tree.delete(i)
        conn = sqlite3.connect(self.db_path)
        standings = conn.execute("SELECT name, wins, diff FROM players ORDER BY wins DESC, diff DESC LIMIT 10").fetchall()
        for i, row in enumerate(standings, 1):
            self.dash_tree.insert("", "end", values=(i, f" {row[0]}", row[1], row[2]))

        # 4. Update Matches
        active_matches = conn.execute("SELECT terrain, t1, t2 FROM matches WHERE status='Spielt' ORDER BY terrain ASC").fetchall()
        waiting_matches = conn.execute("SELECT t1, t2 FROM matches WHERE status='Wartend'").fetchall()
        conn.close()

        self.dash_match_text.config(state="normal") # Unlock for editing
        self.dash_match_text.delete("1.0", "end")
        
        if not active_matches and not waiting_matches:
            self.dash_match_text.insert("end", "\n\n--- RUNDE BEENDET ---")
        else:
            for row in active_matches:
                self.dash_match_text.insert("end", f"BAHN {row[0]}:  {row[1]} vs {row[2]}\n")
            
            if waiting_matches:
                self.dash_match_text.insert("end", "\n--- WARTESCHLEIFE ---\n")
                for row in waiting_matches:
                    self.dash_match_text.insert("end", f"DEMNÄCHST: {row[0]} vs {row[1]}\n")
        
        self.dash_match_text.config(state="disabled") # Lock so users can't type in it
        self.dash.after(1000, self.update_dashboard)

if __name__ == "__main__":
    root = tk.Tk()
    app = PetanqueProMaster(root)
    root.mainloop()