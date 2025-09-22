#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wirkungsgefüge – Infinite Canvas + OneNote‑Navigation
----------------------------------------------------
Erweitert die Mini‑Version um:
- Quasi „unendliche“ Fläche via Scrollbars + dynamische scrollregion
- OneNote‑artige Navigation: Pannen (mit Leertaste+Ziehen oder Mittelklick) und Zoom (Strg+Mausrad)
- Alle Aktionen (Hinzufügen, Verschieben, Kanten, Kontextmenüs) funktionieren im Weltkoordinatensystem

Steuerung
---------
- Faktor hinzufügen: Linksklick ins Leere → Namen eingeben
- Faktor verschieben: Linksklick halten und ziehen
- Kante anlegen: **Shift+Linksklick** auf Quelle → Maus über Ziel loslassen
- Umbenennen/Löschen: Rechtsklick auf Faktor oder Kante
- Pannen: **Leertaste halten und ziehen** ODER Mittlere Maustaste (Maustaste 2)
- Zoomen: **Strg + Mausrad** (auch Trackpad-Gesten, soweit vom OS geliefert)
- Speichern/Laden: Strg+S / Strg+O oder Datei‑Menü

Hinweise
--------
- „Unendlich“: Die Zeichenfläche vergrößert ihre scrollregion automatisch auf Basis der Inhalte (mit Rand). Du kannst beliebig weit heraus- oder hineinzoomen.
- Zoom skaliert sowohl Darstellung als auch die Modellkoordinaten, damit Hit‑Tests, Kanten und JSON‑Speichern konsistent bleiben.
"""

import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox
import json
import math

class InfluenceModel:
    def __init__(self):
        self.nodes = {}   # key -> (x, y, label)   (Weltkoordinaten)
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
    BASE_R = 12   # Basis‑Radius (skaliert mit Zoom)

    def __init__(self):
        super().__init__()
        self.title("Wirkungsgefüge – Infinite Canvas")
        self.geometry("1100x700")
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

        # Zoomzustand
        self.scale_factor = 1.0  # absolute Skalierung relativ zum Startzustand

        # Layout: Scrollbars + Canvas
        self.container = tk.Frame(self, bg="#0b1220")
        self.container.pack(fill="both", expand=True)

        self.hbar = tk.Scrollbar(self.container, orient="horizontal")
        self.vbar = tk.Scrollbar(self.container, orient="vertical")
        self.canvas = tk.Canvas(self.container, bg="#0b1020", highlightthickness=0,
                                xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
        self.hbar.config(command=self.canvas.xview)
        self.vbar.config(command=self.canvas.yview)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar.grid(row=1, column=0, sticky="ew")
        self.container.rowconfigure(0, weight=1)
        self.container.columnconfigure(0, weight=1)

        # Interaktionszustand
        self.drag_key = None
        self.edge_from = None
        self.temp_line = None
        self.hover_key = None
        self.is_panning = False

        # Bindings (Maus & Tasten)
        self.canvas.bind("<Button-1>", self.on_left)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_right)
        self.canvas.bind("<Motion>", self.on_move)

        # Panning: Mittlere Maustaste ODER Leertaste halten
        self.canvas.bind("<Button-2>", self.pan_start)
        self.canvas.bind("<B2-Motion>", self.pan_move)
        self.canvas.bind("<ButtonRelease-2>", self.pan_end)
        self.bind("<KeyPress-space>", self.space_down)
        self.bind("<KeyRelease-space>", self.space_up)

        # Zoom: Strg + Mausrad (Windows/Linux)
        self.canvas.bind("<Control-MouseWheel>", self.on_zoom)
        # Zoom: Strg + (Button-4/5) für einige X11-Systeme
        self.canvas.bind("<Control-Button-4>", lambda e: self.on_zoom(fake_wheel_event(e, delta=120)))
        self.canvas.bind("<Control-Button-5>", lambda e: self.on_zoom(fake_wheel_event(e, delta=-120)))

        # Normales Scrollen ohne Strg
        self.canvas.bind("<MouseWheel>", self.on_scroll)
        self.canvas.bind("<Shift-MouseWheel>", self.on_scroll_h)
        self.canvas.bind("<Button-4>", lambda e: self.on_scroll(fake_wheel_event(e, delta=120)))
        self.canvas.bind("<Button-5>", lambda e: self.on_scroll(fake_wheel_event(e, delta=-120)))

        # Datei‑Shortcuts
        self.bind("<Control-s>", self.save_json)
        self.bind("<Control-o>", self.load_json)

        # Menü
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

    # ---------- Hilfsfunktionen ----------
    def world_xy(self, e):
        """Event‑Pixel → Weltkoordinaten (Canvas‑Koords)."""
        return (self.canvas.canvasx(e.x), self.canvas.canvasy(e.y))

    def current_radius(self):
        return self.BASE_R * self.scale_factor

    def update_scrollregion(self, pad=2000):
        bbox = self.canvas.bbox("all")
        if bbox is None:
            # Fallback‑Region
            self.canvas.configure(scrollregion=(-pad, -pad, pad, pad))
            return
        x1, y1, x2, y2 = bbox
        self.canvas.configure(scrollregion=(x1 - pad, y1 - pad, x2 + pad, y2 + pad))

    # ---------- Hit Tests ----------
    def hit_node(self, x, y):
        r2 = self.current_radius() ** 2
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
            if dist_seg(x, y, x1, y1, x2, y2) < max(8 * self.scale_factor, 6):
                return e
        return None

    # ---------- Maus ----------
    def on_left(self, e):
        wx, wy = self.world_xy(e)
        k = self.hit_node(wx, wy)
        if k:
            if e.state & 0x0001:  # Shift → Kantenstart
                self.edge_from = k
                self.temp_line = self.canvas.create_line(wx, wy, wx, wy, fill="#94a3b8", dash=(4, 2), arrow=tk.LAST, width=2)
            else:
                self.drag_key = k
        else:
            name = simpledialog.askstring("Neuer Faktor", "Name:")
            if name:
                self.model.add_node(name, wx, wy)
                self.redraw()

    def on_drag(self, e):
        wx, wy = self.world_xy(e)
        if self.drag_key:
            self.model.move_node(self.drag_key, wx, wy)
            self.redraw()
        elif self.temp_line is not None and self.edge_from:
            x0, y0, _ = self.model.nodes[self.edge_from]
            sx, sy, ex, ey = self.arrow_coords(x0, y0, wx, wy)
            self.canvas.coords(self.temp_line, sx, sy, ex, ey)

    def on_release(self, e):
        if self.drag_key:
            self.drag_key = None
            return
        if self.temp_line is not None and self.edge_from:
            wx, wy = self.world_xy(e)
            target = self.hit_node(wx, wy)
            if target and target != self.edge_from:
                w = simpledialog.askfloat("Gewicht", f"Gewicht für {self.edge_from} → {target}:", initialvalue=1.0, minvalue=-10.0, maxvalue=10.0)
                if w is not None:
                    self.model.add_edge(self.edge_from, target, w)
            self.canvas.delete(self.temp_line)
            self.temp_line = None
            self.edge_from = None
            self.redraw()

    def on_right(self, e):
        wx, wy = self.world_xy(e)
        k = self.hit_node(wx, wy)
        if k:
            return self.menu_node(k, e)
        edge = self.hit_edge(wx, wy)
        if edge:
            return self.menu_edge(edge, e)
        self.menu_canvas(wx, wy, e)

    def on_move(self, e):
        wx, wy = self.world_xy(e)
        self.hover_key = self.hit_node(wx, wy)
        self.canvas.config(cursor="hand2" if self.hover_key else ("fleur" if self.is_panning else "arrow"))

    # ---------- Panning ----------
    def pan_start(self, e):
        self.is_panning = True
        self.canvas.config(cursor="fleur")
        self.canvas.scan_mark(e.x, e.y)

    def pan_move(self, e):
        if self.is_panning:
            self.canvas.scan_dragto(e.x, e.y, gain=1)

    def pan_end(self, e):
        self.is_panning = False
        self.canvas.config(cursor="arrow")

    def space_down(self, _):
        # Raum für Space+Drag: binde temporär Button‑1 als Pan
        self.canvas.bind("<Button-1>", self.pan_start)
        self.canvas.bind("<B1-Motion>", self.pan_move)
        self.canvas.bind("<ButtonRelease-1>", self.pan_end)

    def space_up(self, _):
        # Standard‑Bindings wiederherstellen
        self.canvas.bind("<Button-1>", self.on_left)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        if self.is_panning:
            self.is_panning = False
            self.canvas.config(cursor="arrow")

    # ---------- Scrollen & Zoomen ----------
    def on_scroll(self, e):
        # Vertikal scrollen, wenn Strg NICHT gedrückt
        if not (e.state & 0x0004):  # Control
            direction = -1 if e.delta > 0 else 1
            self.canvas.yview_scroll(direction, "units")

    def on_scroll_h(self, e):
        # Horizontal scrollen mit Shift+Mausrad
        direction = -1 if e.delta > 0 else 1
        self.canvas.xview_scroll(direction, "units")

    def on_zoom(self, e):
        # Zoomen um den Mausfokus (Weltkoordinaten)
        wx, wy = self.world_xy(e)
        # Delta normalisieren (Windows liefert 120er Schritte)
        step = 1 if e.delta > 0 else -1
        factor = 1.1 if step > 0 else (1/1.1)
        self.apply_zoom(factor, origin=(wx, wy))

    def apply_zoom(self, factor, origin=(0, 0)):
        if factor <= 0:
            return
        ox, oy = origin
        # Canvas‑Elemente skalieren
        self.canvas.scale("all", ox, oy, factor, factor)
        self.scale_factor *= factor
        # Modellkoordinaten entsprechend mit skalieren (damit Hit‑Tests/JSON konsistent bleiben)
        for k, (x, y, label) in list(self.model.nodes.items()):
            nx = ox + (x - ox) * factor
            ny = oy + (y - oy) * factor
            self.model.nodes[k] = (nx, ny, label)
        self.redraw(rebuild=False)  # nur Neu‑Layout von Labels etc.

    # ---------- Menüs ----------
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

    def menu_canvas(self, wx, wy, e):
        m = tk.Menu(self, tearoff=False)
        m.add_command(label="Faktor hier hinzufügen", command=lambda: self.act_add_node_at(wx, wy))
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

    # ---------- Zeichnen ----------
    def redraw(self, rebuild=True):
        c = self.canvas
        if rebuild:
            c.delete("all")
            # Kanten zuerst
            for e in self.model.edges:
                if e['src'] in self.model.nodes and e['dst'] in self.model.nodes:
                    x1, y1, _ = self.model.nodes[e['src']]
                    x2, y2, _ = self.model.nodes[e['dst']]
                    self.draw_edge(x1, y1, x2, y2, e['w'])
            # Knoten obenauf
            for k, (x, y, label) in self.model.nodes.items():
                self.draw_node(x, y, label, highlight=(k == self.hover_key))
        else:
            # Nur dynamische Dinge neu (z. B. Hover‑Heiligenschein)
            c.delete("hover")
            if self.hover_key:
                x, y, label = self.model.nodes[self.hover_key]
                self.draw_node(x, y, label, highlight=True)
        self.update_scrollregion()

    def draw_node(self, x, y, label, highlight=False):
        r = self.current_radius()
        if highlight:
            self.canvas.create_oval(x-r-4, y-r-4, x+r+4, y+r+4, fill="", outline="#60a5fa", tags=("hover",))
        self.canvas.create_oval(x-r, y-r, x+r, y+r, fill="#1f2a44", outline="#93a7c1", width=1.5)
        self.canvas.create_text(x + r + 8, y, text=label, fill="#e6edf3", anchor="w", font=("Segoe UI", int(10*self.scale_factor), "bold"))

    def arrow_coords(self, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy)
        if dist == 0:
            return (x1, y1, x2, y2)
        ux, uy = dx / dist, dy / dist
        r = self.current_radius()
        sx, sy = x1 + ux*r, y1 + uy*r
        ex, ey = x2 - ux*r, y2 - uy*r
        return (sx, sy, ex, ey)

    def draw_edge(self, x1, y1, x2, y2, w):
        sx, sy, ex, ey = self.arrow_coords(x1, y1, x2, y2)
        color = "#34d399" if float(w) >= 0 else "#fb7185"
        self.canvas.create_line(sx, sy, ex, ey, arrow=tk.LAST, width=max(2*self.scale_factor, 1), fill=color, smooth=True)
        # Gewicht nahe Zielende
        tx, ty = (sx*0.3 + ex*0.7), (sy*0.3 + ey*0.7)
        pad = 10 * self.scale_factor
        self.canvas.create_rectangle(tx-pad-2, ty-pad+2, tx+pad+2, ty+pad-2, fill="#0b1020", outline="")
        self.canvas.create_text(tx, ty, text=f"{float(w):.2g}", fill="#cbd5e1", font=("Segoe UI", int(9*self.scale_factor), "bold"))

    # ---------- Datei ----------
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
            # Nach Laden: Zoom zurücksetzen
            self.scale_factor = 1.0
            self.redraw()
        except Exception as ex:
            messagebox.showerror("Fehler", f"Konnte JSON nicht laden: {ex}")

    def new(self):
        if messagebox.askyesno("Neu", "Aktuelles Modell verwerfen und neues beginnen?"):
            self.model = InfluenceModel()
            self.scale_factor = 1.0
            self.redraw()

# Hilfsfunktion für X11‑Mausrad als Button‑4/5
class fake_wheel_event:
    def __init__(self, e, delta):
        self.widget = e.widget
        self.x = e.x
        self.y = e.y
        self.state = e.state
        self.delta = delta

def main():
    App().mainloop()

if __name__ == "__main__":
    main()
