#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wirkungsgefüge Mini – mit Löschen & Gewicht
------------------------------------------
Kleines, robustes Tkinter-Tool ohne Zusatzpakete:
- Knoten hinzufügen: Klick ins Leere → Namen eingeben
- Knoten verschieben: Linksklick halten und ziehen
- Knoten löschen/umbenennen: Rechtsklick auf Knoten
- Kante anlegen mit Gewicht: **Shift+Linksklick** auf Quelle → Maus über Ziel loslassen
- Kante bearbeiten/löschen: Rechtsklick auf Kante
- Speichern/Laden (JSON): Strg+S / Strg+O oder Menü Datei
"""

import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox
import json
import math

class InfluenceModel:
    def __init__(self):
        self.nodes = {}   # key -> (x, y, label)
        self.edges = []   # dicts: {"src": key, "dst": key, "w": float}
        self.counter = 1

    def add_node(self, label, x, y):
        key = f"F{self.counter}"
        self.counter += 1
        self.nodes[key] = (float(x), float(y), str(label))
        return key

    def remove_node(self, key):
        if key in self.nodes:
            del self.nodes[key]
        self.edges = [e for e in self.edges if e["src"] != key and e["dst"] != key]

    def rename_node(self, key, new_label):
        x, y, _ = self.nodes[key]
        self.nodes[key] = (x, y, str(new_label))

    def move_node(self, key, x, y):
        _, _, label = self.nodes[key]
        self.nodes[key] = (float(x), float(y), label)

    def add_edge(self, src, dst, w=1.0):
        if src == dst:
            return
        # update if exists
        for e in self.edges:
            if e["src"] == src and e["dst"] == dst:
                e["w"] = float(w)
                return
        self.edges.append({"src": src, "dst": dst, "w": float(w)})

    def remove_edge(self, src, dst):
        self.edges = [e for e in self.edges if not (e["src"] == src and e["dst"] == dst)]

    def to_dict(self):
        return {"nodes": self.nodes, "edges": self.edges}

    def from_dict(self, d):
        self.nodes = d.get("nodes", {})
        self.edges = d.get("edges", [])

class App(tk.Tk):
    R = 12  # smaller nodes
    def __init__(self):
        super().__init__()
        self.title("Wirkungsgefüge Mini – Clean Look")
        self.geometry("900x600")
        self.configure(bg="#0b1220")

        self.model = InfluenceModel()
        # Demo
        a = self.model.add_node("Preis", 260, 220)
        b = self.model.add_node("Nachfrage", 520, 220)
        c = self.model.add_node("Angebot", 390, 380)
        self.model.add_edge(a, b, -0.8)
        self.model.add_edge(b, a, -0.4)
        self.model.add_edge(c, b, -0.7)
        self.model.add_edge(b, c, 0.6)

        self.canvas = tk.Canvas(self, bg="#0b1020", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # Interaction state
        self.drag_key = None
        self.edge_from = None
        self.temp_line = None
        self.hover_key = None

        # Bindings
        self.canvas.bind("<Button-1>", self.on_left)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_right)
        self.canvas.bind("<Motion>", self.on_move)
        self.bind("<Control-s>", self.save_json)
        self.bind("<Control-o>", self.load_json)

        # Menu
        menubar = tk.Menu(self)
        filem = tk.Menu(menubar, tearoff=False)
        filem.add_command(label="Neu", command=self.new)
        filem.add_command(label="Speichern…", command=self.save_json)
        filem.add_command(label="Laden…", command=self.load_json)
        filem.add_separator()
        filem.add_command(label="Beenden", command=self.destroy)
        menubar.add_cascade(label="Datei", menu=filem)
        self.config(menu=menubar)

        self.redraw()

    # ---------- Hit Tests ----------
    def hit_node(self, x, y):
        r2 = self.R * self.R
        for k, (nx, ny, _) in self.model.nodes.items():
            if (nx - x) ** 2 + (ny - y) ** 2 <= r2:
                return k
        return None

    def hit_edge(self, x, y):
        def dist_seg(px, py, x1, y1, x2, y2):
            vx, vy = x2 - x1, y2 - y1
            if vx == 0 and vy == 0:
                return math.hypot(px - x1, py - y1)
            t = max(0, min(1, ((px - x1)*vx + (py - y1)*vy) / (vx*vx + vy*vy)))
            cx, cy = x1 + t*vx, y1 + t*vy
            return math.hypot(px - cx, py - cy)
        for e in self.model.edges:
            if e["src"] not in self.model.nodes or e["dst"] not in self.model.nodes:
                continue
            x1, y1, _ = self.model.nodes[e["src"]]
            x2, y2, _ = self.model.nodes[e["dst"]]
            if dist_seg(x, y, x1, y1, x2, y2) < 8:
                return e
        return None

    # ---------- Mouse ----------
    def on_left(self, e):
        k = self.hit_node(e.x, e.y)
        if k:
            if e.state & 0x0001:  # Shift → start edge
                self.edge_from = k
                self.temp_line = self.canvas.create_line(e.x, e.y, e.x, e.y, fill="#94a3b8", dash=(4, 2), arrow=tk.LAST, width=2)
            else:
                self.drag_key = k
        else:
            name = simpledialog.askstring("Neuer Faktor", "Name:")
            if name:
                self.model.add_node(name, e.x, e.y)
                self.redraw()

    def on_drag(self, e):
        if self.drag_key:
            self.model.move_node(self.drag_key, e.x, e.y)
            self.redraw()
        elif self.temp_line is not None and self.edge_from:
            x0, y0, _ = self.model.nodes[self.edge_from]
            sx, sy, ex, ey = self.arrow_coords(x0, y0, e.x, e.y)
            self.canvas.coords(self.temp_line, sx, sy, ex, ey)

    def on_release(self, e):
        if self.drag_key:
            self.drag_key = None
            return
        if self.temp_line is not None and self.edge_from:
            target = self.hit_node(e.x, e.y)
            if target and target != self.edge_from:
                w = simpledialog.askfloat("Gewicht", f"Gewicht für {self.edge_from} → {target}:", initialvalue=1.0, minvalue=-10.0, maxvalue=10.0)
                if w is not None:
                    self.model.add_edge(self.edge_from, target, w)
            self.canvas.delete(self.temp_line)
            self.temp_line = None
            self.edge_from = None
            self.redraw()

    def on_right(self, e):
        k = self.hit_node(e.x, e.y)
        if k:
            return self.menu_node(k, e)
        edge = self.hit_edge(e.x, e.y)
        if edge:
            return self.menu_edge(edge, e)
        self.menu_canvas(e)

    def on_move(self, e):
        self.hover_key = self.hit_node(e.x, e.y)
        self.canvas.config(cursor="hand2" if self.hover_key else "arrow")

    # ---------- Menus ----------
    def menu_node(self, key, e):
        m = tk.Menu(self, tearoff=False)
        m.add_command(label="Umbenennen…", command=lambda: self.act_rename_node(key))
        m.add_command(label="Löschen", command=lambda: self.act_delete_node(key))
        m.tk_popup(e.x_root, e.y_root)

    def menu_edge(self, edge, e):
        m = tk.Menu(self, tearoff=False)
        m.add_command(label="Gewicht ändern…", command=lambda: self.act_edit_weight(edge))
        m.add_command(label="Löschen", command=lambda: self.act_delete_edge(edge))
        m.tk_popup(e.x_root, e.y_root)

    def menu_canvas(self, e):
        m = tk.Menu(self, tearoff=False)
        m.add_command(label="Faktor hinzufügen", command=lambda: self.act_add_node_at(e.x, e.y))
        m.tk_popup(e.x_root, e.y_root)

    # ---------- Actions ----------
    def act_add_node_at(self, x, y):
        name = simpledialog.askstring("Neuer Faktor", "Name:")
        if name:
            self.model.add_node(name, x, y)
            self.redraw()

    def act_delete_node(self, key):
        if messagebox.askyesno("Löschen bestätigen", "Diesen Faktor mit allen Kanten löschen?"):
            self.model.remove_node(key)
            self.redraw()

    def act_rename_node(self, key):
        x, y, label = self.model.nodes[key]
        new = simpledialog.askstring("Umbenennen", "Neuer Name:", initialvalue=label)
        if new:
            self.model.rename_node(key, new)
            self.redraw()

    def act_edit_weight(self, edge):
        w = simpledialog.askfloat("Gewicht", f"Neues Gewicht {edge['src']} → {edge['dst']}:", initialvalue=edge['w'], minvalue=-10.0, maxvalue=10.0)
        if w is not None:
            edge['w'] = float(w)
            self.redraw()

    def act_delete_edge(self, edge):
        self.model.remove_edge(edge['src'], edge['dst'])
        self.redraw()

    # ---------- Drawing ----------
    def redraw(self):
        c = self.canvas
        c.delete("all")
        # edges first
        for e in self.model.edges:
            if e['src'] in self.model.nodes and e['dst'] in self.model.nodes:
                x1, y1, _ = self.model.nodes[e['src']]
                x2, y2, _ = self.model.nodes[e['dst']]
                self.draw_edge(x1, y1, x2, y2, e['w'])
        # nodes on top (small dots + detached labels)
        for k, (x, y, label) in self.model.nodes.items():
            self.draw_node(x, y, label, highlight=(k == self.hover_key))

    def draw_node(self, x, y, label, highlight=False):
        r = self.R
        # soft halo
        if highlight:
            self.canvas.create_oval(x-r-4, y-r-4, x+r+4, y+r+4, fill="", outline="#60a5fa")
        # main dot
        self.canvas.create_oval(x-r, y-r, x+r, y+r, fill="#1f2a44", outline="#93a7c1", width=1.5)
        # label next to dot
        self.canvas.create_text(x + r + 8, y, text=label, fill="#e6edf3", anchor="w", font=("Segoe UI", 10, "bold"))

    def arrow_coords(self, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy)
        if dist == 0:
            return (x1, y1, x2, y2)
        ux, uy = dx / dist, dy / dist
        r = self.R
        sx, sy = x1 + ux*r, y1 + uy*r
        ex, ey = x2 - ux*r, y2 - uy*r
        return (sx, sy, ex, ey)

    def draw_edge(self, x1, y1, x2, y2, w):
        sx, sy, ex, ey = self.arrow_coords(x1, y1, x2, y2)
        color = "#34d399" if float(w) >= 0 else "#fb7185"
        self.canvas.create_line(sx, sy, ex, ey, arrow=tk.LAST, width=2, fill=color, smooth=True)
        # weight near the target end
        tx, ty = (sx*0.3 + ex*0.7), (sy*0.3 + ey*0.7)
        self.canvas.create_rectangle(tx-12, ty-8, tx+12, ty+8, fill="#0b1020", outline="")
        self.canvas.create_text(tx, ty, text=f"{float(w):.2g}", fill="#cbd5e1", font=("Segoe UI", 9, "bold"))

    # ---------- File ----------
    def save_json(self, *_):
        path = filedialog.asksaveasfilename(defaultextension=".json")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.model.to_dict(), f, indent=2, ensure_ascii=False)
        messagebox.showinfo("Speichern", f"Gespeichert: {path}")

    def load_json(self, *_):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.model.from_dict(d)
            self.redraw()
        except Exception as ex:
            messagebox.showerror("Fehler", f"Konnte JSON nicht laden: {ex}")

    def new(self):
        if messagebox.askyesno("Neu", "Aktuelles Modell verwerfen und neues beginnen?"):
            self.model = InfluenceModel()
            self.redraw()

if __name__ == "__main__":
    App().mainloop()
    
