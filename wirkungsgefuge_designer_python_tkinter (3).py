#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wirkungsgefüge – Infinite Canvas + OneNote‑Navigation
+ Mini‑Map, Kategorien/Farben, Formen, Undo/Redo, Edge‑Stile & Labels
--------------------------------------------------------------------

Neu in dieser Version:
- **Mini‑Map (Overview)**: kleines Canvas unten rechts. Zeigt den ganzen Graphen
  im Überblick. Rotes Rechteck = aktueller Viewport. Klicken/ziehen zum
  Navigieren.
- **Knoten‑Kategorien & Farben**: vordefinierte Kategorien (mit Farbe) + freie
  Farbwahl. Form pro Knoten: Ellipse / Rechteck / Raute. Optional Icon/Text im
  Knoten.
- **Undo/Redo**: Strg+Z / Strg+Y für alle Modelländerungen (Hinzufügen,
  Verschieben, Umbenennen, Löschen, Stiländerungen …).
- **Edge‑Stile**: gestrichelt/solid, Dicke proportional zum |Gewicht|.
- **Edge‑Labels**: frei editierbares Label direkt auf der Kante, zusammen mit
  der Gewichts‑Zahl sichtbar.

Weiterhin vorhanden:
- Unendliche Zeichenfläche (Scrollregion dynamisch), Panning (Leertaste/Mitte),
  Zoom (Strg+Mausrad), JSON Save/Load.

Steuerung (Auszug)
------------------
- Faktor hinzufügen: Linksklick ins Leere → Namen eingeben
- Faktor verschieben: Linksklick halten und ziehen
- Kante anlegen: Shift+Linksklick auf Quelle → über Ziel loslassen
- Kontextmenüs: Rechtsklick auf Knoten/Kante/Canvas
- Pannen: Leertaste halten und ziehen ODER Mittelklick
- Zoomen: Strg + Mausrad (um Mausfokus)
- Undo/Redo: Strg+Z / Strg+Y
"""

import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox, colorchooser
import json
import math
import copy

# ----------------------------- Datenmodell -----------------------------

CATEGORY_PRESETS = {
    "Ökonomie": "#1e88e5",
    "Soziales": "#22c55e",
    "Umwelt": "#b45309",
    "Politik": "#9333ea",
    "Technologie": "#0ea5e9",
    "Sonstiges": "#64748b",
}

NODE_SHAPES = ["ellipse", "rect", "diamond"]

class InfluenceModel:
    def __init__(self):
        # nodes: key -> dict(x, y, label, color, category, shape, icon)
        self.nodes = {}
        # edges: list of dict(src, dst, w, style, label)
        self.edges = []
        self.counter = 1

    # ----- Nodes -----
    def add_node(self, label, x, y, *, color="#1f2a44", category="Sonstiges", shape="ellipse", icon=""):
        key = f"F{self.counter}"
        self.counter += 1
        self.nodes[key] = {
            "x": float(x), "y": float(y), "label": str(label),
            "color": color, "category": category, "shape": shape, "icon": icon
        }
        return key

    def remove_node(self, key):
        if key in self.nodes:
            del self.nodes[key]
        self.edges = [e for e in self.edges if e["src"] != key and e["dst"] != key]

    def rename_node(self, key, new_label):
        self.nodes[key]["label"] = str(new_label)

    def move_node(self, key, x, y):
        self.nodes[key]["x"] = float(x)
        self.nodes[key]["y"] = float(y)

    def set_node_color(self, key, color):
        self.nodes[key]["color"] = color

    def set_node_category(self, key, cat):
        self.nodes[key]["category"] = cat
        # Wenn Kategorie eine vordefinierte Farbe hat, übernehmen
        if cat in CATEGORY_PRESETS:
            self.nodes[key]["color"] = CATEGORY_PRESETS[cat]

    def set_node_shape(self, key, shape):
        if shape in NODE_SHAPES:
            self.nodes[key]["shape"] = shape

    def set_node_icon(self, key, icon_text):
        self.nodes[key]["icon"] = icon_text or ""

    # ----- Edges -----
    def add_edge(self, src, dst, w=1.0, *, style="solid", label=""):
        if src == dst:
            return
        for e in self.edges:
            if e["src"] == src and e["dst"] == dst:
                e["w"], e["style"], e["label"] = float(w), style, label
                return
        self.edges.append({"src": src, "dst": dst, "w": float(w), "style": style, "label": label})

    def remove_edge(self, src, dst):
        self.edges = [e for e in self.edges if not (e["src"] == src and e["dst"] == dst)]

    def set_edge_style(self, edge, style):
        if style in ("solid", "dashed"):
            edge["style"] = style

    def set_edge_label(self, edge, text):
        edge["label"] = text or ""

    # ----- (De)Serialisierung -----
    def to_dict(self):
        return {"nodes": self.nodes, "edges": self.edges, "counter": self.counter}

    def from_dict(self, d):
        self.nodes = d.get("nodes", {})
        self.edges = d.get("edges", [])
        self.counter = d.get("counter", 1)

# ------------------------------- App UI --------------------------------

class App(tk.Tk):
    BASE_R = 12

    def __init__(self):
        super().__init__()
        self.title("Wirkungsgefüge – Infinite Canvas + Overview")
        self.geometry("1200x780")
        self.configure(bg="#0b1220")

        self.model = InfluenceModel()
        # Demo‑Knoten
        a = self.model.add_node("Preis", 260, 220, category="Ökonomie")
        b = self.model.add_node("Nachfrage", 520, 220, category="Ökonomie")
        c = self.model.add_node("Angebot", 390, 380, category="Ökonomie")
        self.model.add_edge(a, b, -0.8, style="dashed", label="Preis→Nachfrage")
        self.model.add_edge(b, a, -0.4, style="dashed")
        self.model.add_edge(c, b, -0.7, style="solid", label="Angebot fördert")
        self.model.add_edge(b, c, 0.6, style="solid")

        # Zoom
        self.scale_factor = 1.0

        # Undo/Redo Stacks (Zustandssnapshots des Modells)
        self.undo_stack = []
        self.redo_stack = []

        # Layout
        self.container = tk.Frame(self, bg="#0b1220")
        self.container.pack(fill="both", expand=True)
        self.hbar = tk.Scrollbar(self.container, orient="horizontal")
        self.vbar = tk.Scrollbar(self.container, orient="vertical")

        # wir intercepten scrollcommands, um Overview zu aktualisieren
        def _xcmd(*args):
            self.hbar.set(*args)
            self.draw_overview()
        def _ycmd(*args):
            self.vbar.set(*args)
            self.draw_overview()

        self.canvas = tk.Canvas(
            self.container, bg="#0b1020", highlightthickness=0,
            xscrollcommand=_xcmd, yscrollcommand=_ycmd
        )
        self.hbar.config(command=self.canvas.xview)
        self.vbar.config(command=self.canvas.yview)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar.grid(row=1, column=0, sticky="ew")
        self.container.rowconfigure(0, weight=1)
        self.container.columnconfigure(0, weight=1)

        # Mini‑Map (Overview)
        self.ov_w, self.ov_h = 240, 170
        self.ov_margin = 8
        self.ov = tk.Canvas(self.container, width=self.ov_w, height=self.ov_h,
                             bg="#0b0f1a", highlightthickness=1, highlightbackground="#2c3b57")
        # rechts unten platzieren
        self.ov.place(relx=1.0, rely=1.0, x=-14, y=-14, anchor="se")
        self.ov.bind("<Button-1>", self.ov_click)
        self.ov.bind("<B1-Motion>", self.ov_drag)

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
        self.canvas.bind("<Configure>", lambda e: self.draw_overview())

        # Panning/Zoom
        self.canvas.bind("<Button-2>", self.pan_start)
        self.canvas.bind("<B2-Motion>", self.pan_move)
        self.canvas.bind("<ButtonRelease-2>", self.pan_end)
        self.bind("<KeyPress-space>", self.space_down)
        self.bind("<KeyRelease-space>", self.space_up)
        self.canvas.bind("<Control-MouseWheel>", self.on_zoom)
        self.canvas.bind("<Control-Button-4>", lambda e: self.on_zoom(fake_wheel_event(e, delta=120)))
        self.canvas.bind("<Control-Button-5>", lambda e: self.on_zoom(fake_wheel_event(e, delta=-120)))
        self.canvas.bind("<MouseWheel>", self.on_scroll)
        self.canvas.bind("<Shift-MouseWheel>", self.on_scroll_h)
        self.canvas.bind("<Button-4>", lambda e: self.on_scroll(fake_wheel_event(e, delta=120)))
        self.canvas.bind("<Button-5>", lambda e: self.on_scroll(fake_wheel_event(e, delta=-120)))

        # Datei & Undo/Redo Shortcuts
        self.bind("<Control-s>", self.save_json)
        self.bind("<Control-o>", self.load_json)
        self.bind("<Control-z>", self.undo)
        self.bind("<Control-y>", self.redo)

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

    # --------------------------- Undo/Redo ---------------------------
    def snapshot(self):
        return copy.deepcopy(self.model.to_dict())

    def restore(self, state):
        self.model.from_dict(copy.deepcopy(state))
        self.redraw()

    def push_undo(self):
        self.undo_stack.append(self.snapshot())
        # Bei neuer Aktion Redo verwerfen
        self.redo_stack.clear()

    def undo(self, *_):
        if not self.undo_stack:
            return
        cur = self.snapshot()
        prev = self.undo_stack.pop()
        self.redo_stack.append(cur)
        self.restore(prev)

    def redo(self, *_):
        if not self.redo_stack:
            return
        cur = self.snapshot()
        nxt = self.redo_stack.pop()
        self.undo_stack.append(cur)
        self.restore(nxt)

    # ------------------------- Koordinaten --------------------------
    def world_xy(self, e):
        return (self.canvas.canvasx(e.x), self.canvas.canvasy(e.y))

    def current_radius(self):
        return self.BASE_R * self.scale_factor

    def update_scrollregion(self, pad=2000):
        bbox = self.canvas.bbox("all")
        if bbox is None:
            self.canvas.configure(scrollregion=(-pad, -pad, pad, pad))
            return
        x1, y1, x2, y2 = bbox
        self.canvas.configure(scrollregion=(x1 - pad, y1 - pad, x2 + pad, y2 + pad))

    # --------------------------- Hit‑Tests ---------------------------
    def hit_node(self, x, y):
        r2 = self.current_radius() ** 2
        for k, n in self.model.nodes.items():
            nx, ny = n["x"], n["y"]
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
            x1, y1 = self.model.nodes[e["src"]]["x"], self.model.nodes[e["src"]]["y"]
            x2, y2 = self.model.nodes[e["dst"]]["x"], self.model.nodes[e["dst"]]["y"]
            if dist_seg(x, y, x1, y1, x2, y2) < max(8 * self.scale_factor, 6):
                return e
        return None

    # ----------------------------- Maus -----------------------------
    def on_left(self, e):
        wx, wy = self.world_xy(e)
        k = self.hit_node(wx, wy)
        if k:
            if e.state & 0x0001:  # Shift → Kantenstart
                self.edge_from = k
                self.temp_line = self.canvas.create_line(wx, wy, wx, wy, fill="#94a3b8", dash=(4, 2), arrow=tk.LAST, width=2)
            else:
                self.drag_key = k
                self.push_undo()
        else:
            name = simpledialog.askstring("Neuer Faktor", "Name:")
            if name:
                self.push_undo()
                self.model.add_node(name, wx, wy)
                self.redraw()

    def on_drag(self, e):
        wx, wy = self.world_xy(e)
        if self.drag_key:
            self.model.move_node(self.drag_key, wx, wy)
            self.redraw()
        elif self.temp_line is not None and self.edge_from:
            x0, y0 = self.model.nodes[self.edge_from]["x"], self.model.nodes[self.edge_from]["y"]
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
                    self.push_undo()
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

    # --------------------------- Panning/Zoom --------------------------
    def pan_start(self, e):
        self.is_panning = True
        self.canvas.config(cursor="fleur")
        self.canvas.scan_mark(e.x, e.y)

    def pan_move(self, e):
        if self.is_panning:
            self.canvas.scan_dragto(e.x, e.y, gain=1)
            self.draw_overview()

    def pan_end(self, e):
        self.is_panning = False
        self.canvas.config(cursor="arrow")

    def space_down(self, _):
        self.canvas.bind("<Button-1>", self.pan_start)
        self.canvas.bind("<B1-Motion>", self.pan_move)
        self.canvas.bind("<ButtonRelease-1>", self.pan_end)

    def space_up(self, _):
        self.canvas.bind("<Button-1>", self.on_left)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        if self.is_panning:
            self.is_panning = False
            self.canvas.config(cursor="arrow")

    def on_scroll(self, e):
        if not (e.state & 0x0004):  # keine Ctrl-Taste
            direction = -1 if e.delta > 0 else 1
            self.canvas.yview_scroll(direction, "units")
            self.draw_overview()

    def on_scroll_h(self, e):
        direction = -1 if e.delta > 0 else 1
        self.canvas.xview_scroll(direction, "units")
        self.draw_overview()

    def on_zoom(self, e):
        wx, wy = self.world_xy(e)
        step = 1 if e.delta > 0 else -1
        factor = 1.1 if step > 0 else (1/1.1)
        self.apply_zoom(factor, origin=(wx, wy))

    def apply_zoom(self, factor, origin=(0, 0)):
        if factor <= 0:
            return
        ox, oy = origin
        self.push_undo()
        self.canvas.scale("all", ox, oy, factor, factor)
        self.scale_factor *= factor
        for k, n in list(self.model.nodes.items()):
            nx = ox + (n["x"] - ox) * factor
            ny = oy + (n["y"] - oy) * factor
            n["x"], n["y"] = nx, ny
        self.redraw(rebuild=False)  # Re-Layout dynamischer Teile

    # ---------------------------- Menüs -----------------------------
    def menu_node(self, key, e):
        m = tk.Menu(self, tearoff=False)
        m.add_command(label="Umbenennen…", command=lambda: self.act_rename_node(key))
        # Kategorien‑Submenu
        catm = tk.Menu(m, tearoff=False)
        for cat, col in CATEGORY_PRESETS.items():
            catm.add_command(label=f"{cat}", command=lambda c=cat: self.act_set_category(key, c))
        m.add_cascade(label="Kategorie", menu=catm)
        # Farbe wählen
        m.add_command(label="Farbe wählen…", command=lambda: self.act_pick_color(key))
        # Form‑Submenu
        shapem = tk.Menu(m, tearoff=False)
        for sh in NODE_SHAPES:
            shapem.add_command(label=sh.capitalize(), command=lambda s=sh: self.act_set_shape(key, s))
        m.add_cascade(label="Form", menu=shapem)
        # Icon/Text setzen
        m.add_command(label="Icon/Text im Knoten…", command=lambda: self.act_set_icon(key))
        m.add_separator()
        m.add_command(label="Löschen", command=lambda: self.act_delete_node(key))
        m.tk_popup(e.x_root, e.y_root)

    def menu_edge(self, edge, e):
        m = tk.Menu(self, tearoff=False)
        m.add_command(label="Gewicht ändern…", command=lambda: self.act_edit_weight(edge))
        m.add_command(label="Label setzen…", command=lambda: self.act_set_edge_label(edge))
        stylem = tk.Menu(m, tearoff=False)
        stylem.add_command(label="Solide", command=lambda: self.act_edge_style(edge, "solid"))
        stylem.add_command(label="Gestrichelt", command=lambda: self.act_edge_style(edge, "dashed"))
        m.add_cascade(label="Linienstil", menu=stylem)
        m.add_separator()
        m.add_command(label="Löschen", command=lambda: self.act_delete_edge(edge))
        m.tk_popup(e.x_root, e.y_root)

    def menu_canvas(self, wx, wy, e):
        m = tk.Menu(self, tearoff=False)
        m.add_command(label="Faktor hier hinzufügen", command=lambda: self.act_add_node_at(wx, wy))
        m.tk_popup(e.x_root, e.y_root)

    # ---------------------------- Actions ----------------------------
    def act_add_node_at(self, x, y):
        name = simpledialog.askstring("Neuer Faktor", "Name:")
        if name:
            self.push_undo()
            self.model.add_node(name, x, y)
            self.redraw()

    def act_delete_node(self, key):
        if messagebox.askyesno("Löschen bestätigen", "Diesen Faktor mit allen Kanten löschen?"):
            self.push_undo()
            self.model.remove_node(key)
            self.redraw()

    def act_rename_node(self, key):
        cur = self.model.nodes[key]["label"]
        new = simpledialog.askstring("Umbenennen", "Neuer Name:", initialvalue=cur)
        if new:
            self.push_undo()
            self.model.rename_node(key, new)
            self.redraw()

    def act_pick_color(self, key):
        col = colorchooser.askcolor(title="Farbe wählen")[1]
        if col:
            self.push_undo()
            self.model.set_node_color(key, col)
            self.redraw()

    def act_set_category(self, key, cat):
        self.push_undo()
        self.model.set_node_category(key, cat)
        self.redraw()

    def act_set_shape(self, key, shape):
        self.push_undo()
        self.model.set_node_shape(key, shape)
        self.redraw()

    def act_set_icon(self, key):
        cur = self.model.nodes[key].get("icon", "")
        ic = simpledialog.askstring("Icon/Text", "Emoji/Text (z. B. 📈):", initialvalue=cur)
        if ic is not None:
            self.push_undo()
            self.model.set_node_icon(key, ic)
            self.redraw()

    def act_edit_weight(self, edge):
        w = simpledialog.askfloat("Gewicht", f"Neues Gewicht {edge['src']} → {edge['dst']}:", initialvalue=edge['w'], minvalue=-10.0, maxvalue=10.0)
        if w is not None:
            self.push_undo()
            edge['w'] = float(w)
            self.redraw()

    def act_set_edge_label(self, edge):
        cur = edge.get("label", "")
        lab = simpledialog.askstring("Kantenlabel", "Label:", initialvalue=cur)
        if lab is not None:
            self.push_undo()
            self.model.set_edge_label(edge, lab)
            self.redraw()

    def act_edge_style(self, edge, style):
        self.push_undo()
        self.model.set_edge_style(edge, style)
        self.redraw()

    def act_delete_edge(self, edge):
        self.push_undo()
        self.model.remove_edge(edge['src'], edge['dst'])
        self.redraw()

    # --------------------------- Zeichnung ----------------------------
    def redraw(self, rebuild=True):
        c = self.canvas
        if rebuild:
            c.delete("all")
            # Edges unter Knoten zeichnen
            for e in self.model.edges:
                if e['src'] in self.model.nodes and e['dst'] in self.model.nodes:
                    s = self.model.nodes[e['src']]
                    t = self.model.nodes[e['dst']]
                    self.draw_edge(s['x'], s['y'], t['x'], t['y'], e)
            # Nodes obenauf
            for k, n in self.model.nodes.items():
                self.draw_node(n['x'], n['y'], n, highlight=(k == self.hover_key))
        else:
            c.delete("hover")
            if self.hover_key and self.hover_key in self.model.nodes:
                n = self.model.nodes[self.hover_key]
                self.draw_node(n['x'], n['y'], n, highlight=True)
        self.update_scrollregion()
        self.draw_overview()

    def draw_node(self, x, y, node, highlight=False):
        r = self.current_radius()
        if highlight:
            self.canvas.create_oval(x-r-4, y-r-4, x+r+4, y+r+4, fill="", outline="#60a5fa", tags=("hover",))
        fill = node.get("color", "#1f2a44")
        shape = node.get("shape", "ellipse")
        if shape == "ellipse":
            self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=fill, outline="#93a7c1", width=1.5)
        elif shape == "rect":
            self.canvas.create_rectangle(x-r, y-r, x+r, y+r, fill=fill, outline="#93a7c1", width=1.5)
        elif shape == "diamond":
            pts = [x, y-r, x+r, y, x, y+r, x-r, y]
            self.canvas.create_polygon(pts, fill=fill, outline="#93a7c1", width=1.5)
        # Label & Icon
        icon = node.get("icon", "")
        text = (icon + " ") if icon else ""
        text += node.get("label", "")
        self.canvas.create_text(x + r + 8, y, text=text, fill="#e6edf3", anchor="w", font=("Segoe UI", int(10*self.scale_factor), "bold"))

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

    def draw_edge(self, x1, y1, x2, y2, e):
        sx, sy, ex, ey = self.arrow_coords(x1, y1, x2, y2)
        w = float(e.get("w", 0.0))
        width = max(1.5*self.scale_factor, 1) + max(abs(w), 0) * 0.6 * self.scale_factor
        color = "#34d399" if w >= 0 else "#fb7185"
        dash = (6, 4) if e.get("style", "solid") == "dashed" else None
        self.canvas.create_line(sx, sy, ex, ey, arrow=tk.LAST, width=width, fill=color, smooth=True, dash=dash)
        # Label + Gewicht mittig auf der Kante
        tx, ty = (sx + ex)/2, (sy + ey)/2
        lab = e.get("label", "")
        text = lab.strip()
        if text:
            text += "  "
        text += f"{w:.2g}"
        pad = 6 * self.scale_factor
        bbox = (tx - 6*pad, ty - 2*pad, tx + 6*pad, ty + 2*pad)
        self.canvas.create_rectangle(*bbox, fill="#0b1020", outline="")
        self.canvas.create_text(tx, ty, text=text, fill="#cbd5e1", font=("Segoe UI", int(9*self.scale_factor), "bold"))

    # ---------------------------- Datei I/O ---------------------------
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
            self.push_undo()
            self.model.from_dict(d)
            self.scale_factor = 1.0
            self.redraw()
        except Exception as ex:
            messagebox.showerror("Fehler", f"Konnte JSON nicht laden: {ex}")

    def new(self):
        if messagebox.askyesno("Neu", "Aktuelles Modell verwerfen und neues beginnen?"):
            self.push_undo()
            self.model = InfluenceModel()
            self.scale_factor = 1.0
            self.redraw()

    # --------------------------- Mini‑Map -----------------------------
    def world_bounds(self):
        sr = self.canvas.cget("scrollregion")
        if not sr:
            return (-2000, -2000, 2000, 2000)
        x1, y1, x2, y2 = map(float, sr.split())
        return (x1, y1, x2, y2)

    def view_bounds(self):
        x1, y1 = self.canvas.canvasx(0), self.canvas.canvasy(0)
        x2 = self.canvas.canvasx(self.canvas.winfo_width())
        y2 = self.canvas.canvasy(self.canvas.winfo_height())
        return (x1, y1, x2, y2)

    def draw_overview(self):
        ov = self.ov
        ov.delete("all")
        W, H = self.ov_w, self.ov_h
        ov.create_rectangle(0, 0, W, H, fill="#0b0f1a", outline="#2c3b57")
        # Mapping Welt→Overview
        wx1, wy1, wx2, wy2 = self.world_bounds()
        if wx1 >= wx2 or wy1 >= wy2:
            return
        M = self.ov_margin
        ww, wh = wx2 - wx1, wy2 - wy1
        sx = (W - 2*M) / ww
        sy = (H - 2*M) / wh
        s = min(sx, sy)
        ox = M - wx1 * s
        oy = M - wy1 * s

        def map_pt(x, y):
            return (x * s + ox, y * s + oy)

        # Edges
        for e in self.model.edges:
            if e['src'] not in self.model.nodes or e['dst'] not in self.model.nodes:
                continue
            sN, tN = self.model.nodes[e['src']], self.model.nodes[e['dst']]
            x1, y1 = map_pt(sN['x'], sN['y'])
            x2, y2 = map_pt(tN['x'], tN['y'])
            ov.create_line(x1, y1, x2, y2, fill="#5b6c86")
        # Nodes
        r = max(2, int(self.current_radius() * s))
        for n in self.model.nodes.values():
            x, y = map_pt(n['x'], n['y'])
            ov.create_oval(x-r, y-r, x+r, y+r, fill=n.get('color', '#1f2a44'), outline="#93a7c1")

        # Viewport‑Rechteck
        vx1, vy1, vx2, vy2 = self.view_bounds()
        px1, py1 = map_pt(vx1, vy1)
        px2, py2 = map_pt(vx2, vy2)
        self.ov_rect = ov.create_rectangle(px1, py1, px2, py2, outline="#ef4444", width=2)

    def ov_click(self, e):
        self.ov_drag(e)

    def ov_drag(self, e):
        # e.x/e.y → Zielmittelpunkt in Welt, dann Canvas darauf ausrichten
        wx1, wy1, wx2, wy2 = self.world_bounds()
        if wx1 >= wx2 or wy1 >= wy2:
            return
        M = self.ov_margin
        W, H = self.ov_w, self.ov_h
        ww, wh = wx2 - wx1, wy2 - wy1
        s = min((W - 2*M)/ww, (H - 2*M)/wh)
        ox = M - wx1 * s
        oy = M - wy1 * s
        # fwd: world→ov  | inv: ov→world
        wx = (e.x - ox) / s
        wy = (e.y - oy) / s
        # Setze xview/yview so, dass Mittelpunkt ≈ wx/wy ist
        vx1, vy1, vx2, vy2 = self.view_bounds()
        vw, vh = vx2 - vx1, vy2 - vy1
        nx1, ny1 = wx - vw/2, wy - vh/2
        # in Scrollregion clampen
        nx1 = max(wx1, min(nx1, wx2 - vw))
        ny1 = max(wy1, min(ny1, wy2 - vh))
        # in fractions für xview_moveto umrechnen
        fx = (nx1 - wx1) / (wx2 - wx1)
        fy = (ny1 - wy1) / (wy2 - wy1)
        self.canvas.xview_moveto(fx)
        self.canvas.yview_moveto(fy)
        self.draw_overview()

# ------------------------------ Helpers ------------------------------

class fake_wheel_event:
    def __init__(self, e, delta):
        self.widget = e.widget
        self.x = e.x
        self.y = e.y
        self.state = e.state
        self.delta = delta

# ------------------------------- Start -------------------------------

def main():
    App().mainloop()

if __name__ == "__main__":
    main()
