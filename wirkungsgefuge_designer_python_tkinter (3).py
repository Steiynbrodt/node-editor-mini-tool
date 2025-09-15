
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wirkungsgefüge Mini – Pro Build (ohne Zusatzpakete)
--------------------------------------------------
Verbesserungen:
- 🎯 Auswahl & Bearbeitung: Klick = Auswahl, F2 = Umbenennen, Entf = Löschen
- ➕ Knoten hinzufügen: Doppelklick ins Leere (oder Rechtsklick → Menü)
- 🔗 Kanten mit Gewicht: Shift+Drag Quelle→Ziel; Rechtsklick auf Kante: Gewicht ändern / löschen
- 🧭 Pan & Zoom: Rechtsklick+Ziehen = Pan, Strg + Mausrad = Zoom, 0 = 100% / Ansicht zentrieren
- 🧲 Raster & Snap: Taste G schaltet Snap ein/aus, dezentes Raster
- 🔙 Undo/Redo: Strg+Z / Strg+Y (modell- und ansichtsbasiert)
- 💾 JSON-Import/Export (Datei-Menü oder Strg+S / Strg+O)

Hinweise:
- Keine externen Bibliotheken notwendig (nur Tkinter + json + math)
- Koordinaten werden in Welt-Koordinaten gespeichert; Pan/Zoom sind rein visuell
"""

import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox
import json
import math
from copy import deepcopy

# ------------------ Datenmodell ------------------
class InfluenceModel:
    def __init__(self):
        # nodes: key -> {x, y, label}
        self.nodes = {}
        # edges: list of {src, dst, w}
        self.edges = []
        self.counter = 1

    def add_node(self, label, x, y):
        key = f"F{self.counter}"
        self.counter += 1
        self.nodes[key] = {"x": float(x), "y": float(y), "label": str(label)}
        return key

    def remove_node(self, key):
        if key in self.nodes:
            del self.nodes[key]
        self.edges = [e for e in self.edges if e["src"] != key and e["dst"] != key]

    def rename_node(self, key, new_label):
        if key in self.nodes:
            self.nodes[key]["label"] = str(new_label)

    def move_node(self, key, x, y):
        if key in self.nodes:
            self.nodes[key]["x"], self.nodes[key]["y"] = float(x), float(y)

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
        return {"nodes": self.nodes, "edges": self.edges, "counter": self.counter}

    def from_dict(self, d):
        self.nodes = d.get("nodes", {})
        self.edges = d.get("edges", [])
        self.counter = int(d.get("counter", max([int(k[1:]) for k in self.nodes] + [0]) + 1))

    # Deep copy helper for undo/redo
    def clone(self):
        m = InfluenceModel()
        m.nodes = deepcopy(self.nodes)
        m.edges = deepcopy(self.edges)
        m.counter = self.counter
        return m

# ------------------ App / View ------------------
class App(tk.Tk):
    R = 12          # Knotengröße (Radius)
    GRID = 24       # Rastergröße

    def __init__(self):
        super().__init__()
        self.title("Wirkungsgefüge – Pro Build")
        self.geometry("1000x680")
        self.configure(bg="#0b1220")

        # Model & View-State
        self.model = InfluenceModel()
        self.scale = 1.0  # Zoomfaktor
        self.offset = [0.0, 0.0]  # Pan-Offset in Pixeln (Bildschirm)
        self.snap = True
        self.hover_key = None
        self.sel_key = None
        self.dragging_node = None
        self.edge_from = None
        self.temp_line = None

        # Undo/Redo Stacks (speichern Model+View)
        self.undo_stack = []
        self.redo_stack = []

        # Demo
        a = self.model.add_node("Preis", 260, 220)
        b = self.model.add_node("Nachfrage", 520, 220)
        c = self.model.add_node("Angebot", 390, 380)
        self.model.add_edge(a, b, -0.8)
        self.model.add_edge(b, a, -0.4)
        self.model.add_edge(c, b, -0.7)
        self.model.add_edge(b, c, 0.6)

        # Canvas
        self.canvas = tk.Canvas(self, bg="#0b1020", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # Bindings
        self.canvas.bind("<Button-1>", self.on_left)
        self.canvas.bind("<Double-1>", self.on_double_left)
        self.canvas.bind("<B1-Motion>", self.on_drag_left)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_release)
        self.canvas.bind("<Button-3>", self.on_right)
        self.canvas.bind("<B3-Motion>", self.on_drag_right)  # Pan
        self.canvas.bind("<Motion>", self.on_motion)
        # Mouse wheel zoom (Windows/Linux)
        self.canvas.bind("<Control-MouseWheel>", self.on_wheel)
        # macOS (delta in e.delta is different); also support <Control-Button-4/5> fallback
        self.canvas.bind("<Control-Button-4>", lambda e: self.zoom_at(1.1, e.x, e.y))
        self.canvas.bind("<Control-Button-5>", lambda e: self.zoom_at(1/1.1, e.x, e.y))

        # Keyboard
        self.bind("<Delete>", self.k_delete)
        self.bind("<BackSpace>", self.k_delete)
        self.bind("<F2>", self.k_rename)
        self.bind("<Control-s>", self.save_json)
        self.bind("<Control-o>", self.load_json)
        self.bind("<Control-z>", self.k_undo)
        self.bind("<Control-y>", self.k_redo)
        self.bind("g", self.k_toggle_snap)
        self.bind("0", self.k_reset_view)

        # Menü
        menubar = tk.Menu(self)
        filem = tk.Menu(menubar, tearoff=False)
        filem.add_command(label="Neu", command=self.new)
        filem.add_command(label="Speichern…", command=self.save_json)
        filem.add_command(label="Laden…", command=self.load_json)
        filem.add_separator()
        filem.add_command(label="Beenden", command=self.destroy)
        menubar.add_cascade(label="Datei", menu=filem)

        helpm = tk.Menu(menubar, tearoff=False)
        helpm.add_command(label="Tastenkürzel", command=self.show_help)
        menubar.add_cascade(label="Hilfe", menu=helpm)
        self.config(menu=menubar)

        self.redraw()

    # ---------- Undo/Redo ----------
    def snapshot(self):
        return {
            "model": self.model.clone().to_dict(),
            "scale": self.scale,
            "offset": tuple(self.offset),
            "sel": self.sel_key,
        }

    def restore(self, snap):
        m = InfluenceModel()
        m.from_dict(deepcopy(snap["model"]))
        self.model = m
        self.scale = float(snap["scale"]) 
        self.offset = [float(snap["offset"][0]), float(snap["offset"][1])]
        self.sel_key = snap.get("sel")
        self.redraw()

    def push_undo(self):
        self.undo_stack.append(self.snapshot())
        self.redo_stack.clear()

    def k_undo(self, *_):
        if not self.undo_stack:
            return
        cur = self.snapshot()
        last = self.undo_stack.pop()
        self.redo_stack.append(cur)
        self.restore(last)

    def k_redo(self, *_):
        if not self.redo_stack:
            return
        cur = self.snapshot()
        nxt = self.redo_stack.pop()
        self.undo_stack.append(cur)
        self.restore(nxt)

    # ---------- Koordinaten-Helfer ----------
    def world_to_screen(self, x, y):
        return (x * self.scale + self.offset[0], y * self.scale + self.offset[1])

    def screen_to_world(self, sx, sy):
        return ((sx - self.offset[0]) / self.scale, (sy - self.offset[1]) / self.scale)

    # ---------- Hit Tests (in Weltkoords) ----------
    def hit_node_world(self, wx, wy):
        r = self.R / self.scale  # Radius in Weltkoords
        r2 = r * r
        for k, n in self.model.nodes.items():
            dx, dy = n["x"] - wx, n["y"] - wy
            if dx*dx + dy*dy <= r2:
                return k
        return None

    def hit_edge_world(self, wx, wy):
        def dist_seg(px, py, x1, y1, x2, y2):
            vx, vy = x2 - x1, y2 - y1
            if vx == 0 and vy == 0:
                return math.hypot(px - x1, py - y1)
            t = max(0, min(1, ((px - x1)*vx + (py - y1)*vy) / (vx*vx + vy*vy)))
            cx, cy = x1 + t*vx, y1 + t*vy
            return math.hypot(px - cx, py - cy)
        tol = 8 / self.scale
        for e in self.model.edges:
            if e["src"] not in self.model.nodes or e["dst"] not in self.model.nodes:
                continue
            a = self.model.nodes[e["src"]]
            b = self.model.nodes[e["dst"]]
            if dist_seg(wx, wy, a["x"], a["y"], b["x"], b["y"]) < tol:
                return e
        return None

    # ---------- Mouse & Keys ----------
    def on_motion(self, e):
        wx, wy = self.screen_to_world(e.x, e.y)
        self.hover_key = self.hit_node_world(wx, wy)
        self.canvas.config(cursor="hand2" if self.hover_key else ("fleur" if self._panning else "arrow"))

    def on_left(self, e):
        wx, wy = self.screen_to_world(e.x, e.y)
        k = self.hit_node_world(wx, wy)
        if k:
            if e.state & 0x0001:  # Shift → start edge
                self.edge_from = k
                self.temp_line = self.canvas.create_line(e.x, e.y, e.x, e.y, fill="#94a3b8", dash=(4, 2), arrow=tk.LAST, width=2)
            else:
                self.sel_key = k
                self.dragging_node = k
                self.drag_off = (wx - self.model.nodes[k]["x"], wy - self.model.nodes[k]["y"])  # offset
        else:
            # Leerer Klick → Auswahl leeren
            self.sel_key = None
            self.redraw()

    def on_double_left(self, e):
        wx, wy = self.screen_to_world(e.x, e.y)
        name = simpledialog.askstring("Neuer Faktor", "Name:")
        if not name:
            return
        if self.snap:
            wx = round(wx / self.GRID) * self.GRID
            wy = round(wy / self.GRID) * self.GRID
        self.push_undo()
        self.model.add_node(name, wx, wy)
        self.redraw()

    def on_drag_left(self, e):
        if self.dragging_node:
            wx, wy = self.screen_to_world(e.x, e.y)
            x = wx - self.drag_off[0]
            y = wy - self.drag_off[1]
            if self.snap:
                x = round(x / self.GRID) * self.GRID
                y = round(y / self.GRID) * self.GRID
            self.model.move_node(self.dragging_node, x, y)
            self.redraw()
        elif self.temp_line is not None and self.edge_from:
            # Live-Update der temporären Linie (in Screenspace)
            ax, ay = self.model.nodes[self.edge_from]["x"], self.model.nodes[self.edge_from]["y"]
            sx, sy = self.world_to_screen(ax, ay)
            self.canvas.coords(self.temp_line, sx, sy, e.x, e.y)

    def on_left_release(self, e):
        if self.dragging_node:
            self.push_undo()
            self.dragging_node = None
            return
        if self.temp_line is not None and self.edge_from:
            wx, wy = self.screen_to_world(e.x, e.y)
            target = self.hit_node_world(wx, wy)
            if target and target != self.edge_from:
                w = simpledialog.askfloat("Gewicht", f"Gewicht für {self.edge_from} → {target}:", initialvalue=1.0, minvalue=-10.0, maxvalue=10.0)
                if w is not None:
                    self.push_undo()
                    self.model.add_edge(self.edge_from, target, w)
            self.canvas.delete(self.temp_line)
            self.temp_line = None
            self.edge_from = None
            self.redraw()

    _panning = False
    _pan_start = (0, 0)
    def on_right(self, e):
        wx, wy = self.screen_to_world(e.x, e.y)
        k = self.hit_node_world(wx, wy)
        if k:
            return self.menu_node(k, e)
        edge = self.hit_edge_world(wx, wy)
        if edge:
            return self.menu_edge(edge, e)
        # Start pan
        self._panning = True
        self._pan_start = (e.x - self.offset[0], e.y - self.offset[1])

    def on_drag_right(self, e):
        if self._panning:
            self.offset[0] = e.x - self._pan_start[0]
            self.offset[1] = e.y - self._pan_start[1]
            self.redraw()

    def on_wheel(self, e):
        factor = 1.1 if e.delta > 0 else 1/1.1
        self.zoom_at(factor, e.x, e.y)

    def zoom_at(self, factor, sx, sy):
        # Zoom relative zum Mauspunkt (Screenspace)
        wx0, wy0 = self.screen_to_world(sx, sy)
        self.scale = max(0.2, min(5.0, self.scale * factor))
        sx2, sy2 = self.world_to_screen(wx0, wy0)
        # adjust offset so the point stays under cursor
        self.offset[0] += sx - sx2
        self.offset[1] += sy - sy2
        self.redraw()

    def k_delete(self, *_):
        if self.sel_key:
            self.push_undo()
            self.model.remove_node(self.sel_key)
            self.sel_key = None
            self.redraw()

    def k_rename(self, *_):
        if not self.sel_key:
            return
        cur = self.model.nodes[self.sel_key]["label"]
        new = simpledialog.askstring("Umbenennen", "Neuer Name:", initialvalue=cur)
        if new:
            self.push_undo()
            self.model.rename_node(self.sel_key, new)
            self.redraw()

    def k_toggle_snap(self, *_):
        self.snap = not self.snap
        messagebox.showinfo("Raster", f"Snap ist {'ein' if self.snap else 'aus'} (Taste G)")

    def k_reset_view(self, *_):
        self.scale = 1.0
        self.offset = [0.0, 0.0]
        self.redraw()

    # ---------- Menüs ----------
    def menu_node(self, key, e):
        m = tk.Menu(self, tearoff=False)
        m.add_command(label="Umbenennen…", command=lambda: self.k_rename())
        m.add_command(label="Löschen", command=lambda: self.k_delete())
        m.tk_popup(e.x_root, e.y_root)

    def menu_edge(self, edge, e):
        m = tk.Menu(self, tearoff=False)
        m.add_command(label="Gewicht ändern…", command=lambda: self.act_edit_weight(edge))
        m.add_command(label="Löschen", command=lambda: self.act_delete_edge(edge))
        m.tk_popup(e.x_root, e.y_root)

    # ---------- Aktionen ----------
    def act_edit_weight(self, edge):
        w = simpledialog.askfloat("Gewicht", f"Neues Gewicht {edge['src']} → {edge['dst']}:", initialvalue=edge['w'], minvalue=-10.0, maxvalue=10.0)
        if w is not None:
            self.push_undo()
            edge['w'] = float(w)
            self.redraw()

    def act_delete_edge(self, edge):
        self.push_undo()
        self.model.remove_edge(edge['src'], edge['dst'])
        self.redraw()

    # ---------- Zeichnen ----------
    def redraw(self):
        c = self.canvas
        c.delete("all")
        self.draw_grid(c)
        # Kanten zuerst
        for e in self.model.edges:
            if e['src'] in self.model.nodes and e['dst'] in self.model.nodes:
                a = self.model.nodes[e['src']]
                b = self.model.nodes[e['dst']]
                self.draw_edge(a['x'], a['y'], b['x'], b['y'], e['w'])
        # Knoten
        for k, n in self.model.nodes.items():
            self.draw_node(n['x'], n['y'], n['label'], selected=(k == self.sel_key), hover=(k == self.hover_key))

    def draw_grid(self, c):
        # dezentes Raster
        w = c.winfo_width() or 1000
        h = c.winfo_height() or 600
        step = self.GRID * self.scale
        if step < 12:  # zu dicht → kein Raster
            return
        # find start lines based on offset
        x0 = self.offset[0] % step
        y0 = self.offset[1] % step
        for x in frange(x0, w, step):
            c.create_line(x, 0, x, h, fill="#152238")
        for y in frange(y0, h, step):
            c.create_line(0, y, w, y, fill="#152238")

    def draw_node(self, x, y, label, selected=False, hover=False):
        sx, sy = self.world_to_screen(x, y)
        r = self.R
        # Halo/Selection
        if selected:
            self.canvas.create_oval(sx-r-5, sy-r-5, sx+r+5, sy+r+5, outline="#60a5fa", width=2)
        elif hover:
            self.canvas.create_oval(sx-r-4, sy-r-4, sx+r+4, sy+r+4, outline="#94a3b8")
        # Dot
        self.canvas.create_oval(sx-r, sy-r, sx+r, sy+r, fill="#1f2a44", outline="#93a7c1", width=1.5)
        # Label rechts daneben
        self.canvas.create_text(sx + r + 8, sy, text=label, fill="#e6edf3", anchor="w", font=("Segoe UI", 10, "bold"))

    def arrow_coords(self, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy)
        if dist == 0:
            return (x1, y1, x2, y2)
        ux, uy = dx / dist, dy / dist
        r = self.R / self.scale
        sx, sy = x1 + ux*r, y1 + uy*r
        ex, ey = x2 - ux*r, y2 - uy*r
        return (sx, sy, ex, ey)

    def draw_edge(self, x1, y1, x2, y2, w):
        sx, sy, ex, ey = self.arrow_coords(x1, y1, x2, y2)
        csx, csy = self.world_to_screen(sx, sy)
        cex, cey = self.world_to_screen(ex, ey)
        color = "#34d399" if float(w) >= 0 else "#fb7185"
        self.canvas.create_line(csx, csy, cex, cey, arrow=tk.LAST, width=2, fill=color, smooth=True)
        # Gewicht nahe Ziel
        tx, ty = (sx*0.3 + ex*0.7), (sy*0.3 + ey*0.7)
        tsx, tsy = self.world_to_screen(tx, ty)
        self.canvas.create_rectangle(tsx-12, tsy-8, tsx+12, tsy+8, fill="#0b1020", outline="")
        self.canvas.create_text(tsx, tsy, text=f"{float(w):.2g}", fill="#cbd5e1", font=("Segoe UI", 9, "bold"))

    # ---------- File ----------
    def save_json(self, *_):
        path = filedialog.asksaveasfilename(defaultextension=".json")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "model": self.model.to_dict(),
                "view": {"scale": self.scale, "offset": self.offset}
            }, f, indent=2, ensure_ascii=False)
        messagebox.showinfo("Speichern", f"Gespeichert: {path}")

    def load_json(self, *_):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.push_undo()
            self.model.from_dict(d.get("model", d))  # rückwärtskompatibel
            view = d.get("view")
            if view:
                self.scale = float(view.get("scale", 1.0))
                off = view.get("offset", [0.0, 0.0])
                self.offset = [float(off[0]), float(off[1])]
            self.redraw()
        except Exception as ex:
            messagebox.showerror("Fehler", f"Konnte JSON nicht laden: {ex}")

    def new(self):
        if messagebox.askyesno("Neu", "Aktuelles Modell verwerfen und neues beginnen?"):
            self.push_undo()
            self.model = InfluenceModel()
            self.scale = 1.0
            self.offset = [0.0, 0.0]
            self.sel_key = None
            self.redraw()

    def show_help(self):
        messagebox.showinfo(
            "Tastenkürzel",
            (
                "Klick: auswählen | Doppelklick: Knoten erstellen
"
                "Shift+Drag: Kante mit Gewicht | Rechtsklick: Menüs
"
                "Entf: Knoten löschen | F2: umbenennen
"
                "Strg+S: speichern | Strg+O: laden
"
                "Strg+Z / Strg+Y: Undo / Redo
"
                "Rechtsklick+Ziehen: Pan | Strg+Mausrad: Zoom | 0: Ansicht reset
"
                "G: Snap ans Raster an/aus"
            ),
        )


def frange(start, end, step):
    x = start
    while x <= end:
        yield x
        x += step


if __name__ == "__main__":
    App().mainloop()
