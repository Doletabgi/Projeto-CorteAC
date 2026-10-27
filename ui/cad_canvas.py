"""
JobManager 2000 (Python Edition)
Interactive CAD Canvas Widget (Tkinter Dark Theme)
"""

import json
import tkinter as tk
from cad.geometry import transform_contour, point_in_polygon, rotate_point, polygon_bbox, polygons_collide
from cad.colors import get_color_for_size
from config import THEME

class CADCanvas(tk.Canvas):
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            bg=THEME["canvas_bg"],
            highlightthickness=0,
            cursor="crosshair",
            **kwargs
        )

        # Estado do Viewport
        self.zoom = 0.55
        self.pan_x = 120.0
        self.pan_y = 60.0

        # Dados da Mesa
        self.material = None
        self.placed_pieces = []
        self.selected_index = -1

        # Interação do Mouse
        self.dragged_index = -1
        self.drag_start_world = (0, 0)
        self.last_mouse = (0, 0)
        self.is_panning = False

        # Simulação de Corte CNC
        self.sim_running = False
        self.sim_piece_idx = 0
        self.sim_pt_idx = 0
        self.sim_head_pos = (0, 0)

        # Callbacks
        self.on_change = None

        # Bindings de Eventos
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<ButtonPress-1>", self.on_button1_down)
        self.bind("<B1-Motion>", self.on_button1_motion)
        self.bind("<ButtonRelease-1>", self.on_button1_up)

        self.bind("<ButtonPress-2>", self.on_pan_start)
        self.bind("<B2-Motion>", self.on_pan_motion)
        self.bind("<ButtonRelease-2>", self.on_pan_end)

        self.bind("<ButtonPress-3>", self.on_pan_start)
        self.bind("<B3-Motion>", self.on_pan_motion)
        self.bind("<ButtonRelease-3>", self.on_pan_end)

        # Zoom com Mouse Wheel (Windows e Linux)
        self.bind("<MouseWheel>", self.on_zoom_windows)
        self.bind("<Button-4>", lambda e: self.zoom_step(1.1, e.x, e.y))
        self.bind("<Button-5>", lambda e: self.zoom_step(0.9, e.x, e.y))

        # Atalhos de Teclado
        self.bind("<Escape>", self.cancel_drag)
        self.master.bind("<Escape>", self.cancel_drag)
        self.master.bind("<r>", lambda e: self.rotate_selected(45))
        self.master.bind("<R>", lambda e: self.rotate_selected(45))
        self.master.bind("<Delete>", lambda e: self.delete_selected())
        self.master.bind("<BackSpace>", lambda e: self.delete_selected())

    # =========================================================================
    # Conversões de Coordenadas
    # =========================================================================
    def world_to_screen(self, wx, wy):
        return (
            wx * self.zoom + self.pan_x,
            wy * self.zoom + self.pan_y
        )

    def screen_to_world(self, sx, sy):
        return (
            (sx - self.pan_x) / self.zoom,
            (sy - self.pan_y) / self.zoom
        )

    # =========================================================================
    # Zoom & Pan
    # =========================================================================
    def on_zoom_windows(self, event):
        factor = 1.12 if event.delta > 0 else 0.89
        self.zoom_step(factor, event.x, event.y)

    def zoom_step(self, factor, center_x, center_y):
        wx_before, wy_before = self.screen_to_world(center_x, center_y)
        new_zoom = max(0.15, min(self.zoom * factor, 3.5))
        self.zoom = new_zoom
        self.pan_x = center_x - wx_before * self.zoom
        self.pan_y = center_y - wy_before * self.zoom
        self.redraw()

    def on_pan_start(self, event):
        self.is_panning = True
        self.last_mouse = (event.x, event.y)
        self.config(cursor="fleur")

    def on_pan_motion(self, event):
        if self.is_panning:
            dx = event.x - self.last_mouse[0]
            dy = event.y - self.last_mouse[1]
            self.pan_x += dx
            self.pan_y += dy
            self.last_mouse = (event.x, event.y)
            self.redraw()

    def on_pan_end(self, event):
        self.is_panning = False
        self.config(cursor="crosshair")

    def reset_view(self):
        self.zoom = 0.55
        self.pan_x = 120.0
        self.pan_y = 60.0
        self.redraw()

    # =========================================================================
    # Manipulação de Peças
    # =========================================================================
    def set_material(self, mat):
        self.material = mat
        self.redraw()

    def set_pieces(self, pieces):
        self.placed_pieces = pieces
        self.selected_index = -1
        self.redraw()
        if self.on_change:
            self.on_change()

    def rotate_selected(self, deg=45):
        if 0 <= self.selected_index < len(self.placed_pieces):
            p = self.placed_pieces[self.selected_index]
            p["rotation"] = (p["rotation"] + deg) % 360
            self.redraw()
            if self.on_change:
                self.on_change()

    def delete_selected(self):
        if 0 <= self.selected_index < len(self.placed_pieces):
            self.placed_pieces.pop(self.selected_index)
            self.selected_index = -1
            self.redraw()
            if self.on_change:
                self.on_change()

    def clear_bed(self):
        self.placed_pieces.clear()
        self.selected_index = -1
        self.redraw()
        if self.on_change:
            self.on_change()

    def _resolve_piece_contour(self, piece: dict) -> list:
        """Resolve o contorno da peça ou retorna retângulo seguro caso ausente."""
        c = piece.get("contour")
        if c and len(c) >= 3:
            return list(c)
        if isinstance(piece.get("shape"), dict):
            sc = piece["shape"].get("contour")
            if sc and len(sc) >= 3:
                return list(sc)
            if piece["shape"].get("contour_json"):
                try:
                    sc = json.loads(piece["shape"]["contour_json"])
                    if sc and len(sc) >= 3:
                        return sc
                except Exception:
                    pass
        return [
            {"x": 0.0, "y": 0.0},
            {"x": 80.0, "y": 0.0},
            {"x": 80.0, "y": 50.0},
            {"x": 0.0, "y": 50.0}
        ]

    # =========================================================================
    # Eventos de Seleção e Arrastar
    # =========================================================================
    def on_button1_down(self, event):
        wx, wy = self.screen_to_world(event.x, event.y)

        # Checa colisão da peça de cima para baixo
        hit_idx = -1
        for i in range(len(self.placed_pieces) - 1, -1, -1):
            p = self.placed_pieces[i]
            contour = self._resolve_piece_contour(p)
            rot = float(p.get("rotation", p.get("angle", 0.0)))
            poly = transform_contour(contour, p["x"], p["y"], rot)
            if point_in_polygon(wx, wy, poly):
                hit_idx = i
                break

        if hit_idx != -1:
            self.selected_index = hit_idx
            self.dragged_index = hit_idx
            p = self.placed_pieces[hit_idx]
            self.drag_start_world = (wx - p["x"], wy - p["y"])
            self._pre_drag_pos = (p["x"], p["y"])
            self._drag_last_screen = (event.x, event.y)
            self._drag_colliding_others = set()

            self.redraw()
            if self.on_change:
                self.on_change()

            # Desenha ghost outline na posição original
            self.delete("drag_ghost")
            contour = self._resolve_piece_contour(p)
            rot = float(p.get("rotation", p.get("angle", 0.0)))
            orig_poly = transform_contour(contour, p["x"], p["y"], rot)
            ghost_coords = []
            for pt in orig_poly:
                sx, sy = self.world_to_screen(pt["x"], pt["y"])
                ghost_coords.extend([sx, sy])
            if len(ghost_coords) >= 6:
                self.create_polygon(
                    ghost_coords,
                    fill="",
                    outline="#64748b",
                    dash=(4, 3),
                    width=1.5,
                    tags=("drag_ghost",)
                )
                self.tag_raise(f"piece_{hit_idx}")
        else:
            self.selected_index = -1
            self.dragged_index = -1
            self._pre_drag_pos = None
            self.delete("drag_ghost")
            self.redraw()
            if self.on_change:
                self.on_change()

    def on_button1_motion(self, event):
        if 0 <= self.dragged_index < len(self.placed_pieces):
            last_sx, last_sy = getattr(self, "_drag_last_screen", (event.x, event.y))
            dx = event.x - last_sx
            dy = event.y - last_sy
            self._drag_last_screen = (event.x, event.y)

            # Fast-path: deslocamento imediato via canvas.move sem recriar cena
            self.move(f"piece_{self.dragged_index}", dx, dy)

            # Atualiza coordenadas lógicas da peça
            wx, wy = self.screen_to_world(event.x, event.y)
            p = self.placed_pieces[self.dragged_index]
            p["x"] = round(wx - self.drag_start_world[0])
            p["y"] = round(wy - self.drag_start_world[1])

            # Checagem em tempo real de colisão
            contour = self._resolve_piece_contour(p)
            rot = float(p.get("rotation", p.get("angle", 0.0)))
            curr_poly = transform_contour(contour, p["x"], p["y"], rot)
            curr_bbox = polygon_bbox(curr_poly)

            prev_colliding = getattr(self, "_drag_colliding_others", set())
            new_colliding = set()
            is_colliding = False

            if self.material:
                mw = self.material["width_mm"]
                mh = self.material["height_mm"]
                if curr_bbox[0] < -0.01 or curr_bbox[1] < -0.01 or curr_bbox[2] > mw + 0.01 or curr_bbox[3] > mh + 0.01:
                    is_colliding = True

            for j, other in enumerate(self.placed_pieces):
                if j == self.dragged_index:
                    continue
                o_contour = self._resolve_piece_contour(other)
                o_rot = float(other.get("rotation", other.get("angle", 0.0)))
                o_poly = transform_contour(o_contour, other["x"], other["y"], o_rot)
                o_bbox = polygon_bbox(o_poly)
                if polygons_collide(curr_poly, o_poly, gap=0.0, bbox_a=curr_bbox, bbox_b=o_bbox):
                    is_colliding = True
                    new_colliding.add(j)

            # Restaura contorno das peças que saíram da colisão
            for j in prev_colliding - new_colliding:
                if 0 <= j < len(self.placed_pieces):
                    o_p = self.placed_pieces[j]
                    s_val = str(o_p.get("size") or (o_p.get("shape", {}).get("size") if isinstance(o_p.get("shape"), dict) else "") or o_p.get("name") or "41")
                    base_col = get_color_for_size(s_val, j)
                    self.itemconfig(f"piece_poly_{j}", outline=base_col, width=2.0)

            # Destaca novas peças colididas em âmbar
            for j in new_colliding:
                self.itemconfig(f"piece_poly_{j}", outline="#f59e0b", width=2.5)
            self._drag_colliding_others = new_colliding

            # Feedback de colisão na peça arrastada
            if is_colliding:
                self.itemconfig(f"piece_poly_{self.dragged_index}", outline="#ef4444", width=3.0)
            else:
                self.itemconfig(f"piece_poly_{self.dragged_index}", outline="#22c55e", width=2.5)

            self.tag_raise(f"piece_{self.dragged_index}")

    def on_button1_up(self, event):
        self.delete("drag_ghost")
        # Restaura qualquer peça destacada em âmbar
        for j in getattr(self, "_drag_colliding_others", set()):
            if 0 <= j < len(self.placed_pieces):
                o_p = self.placed_pieces[j]
                s_val = str(o_p.get("size") or (o_p.get("shape", {}).get("size") if isinstance(o_p.get("shape"), dict) else "") or o_p.get("name") or "41")
                base_col = get_color_for_size(s_val, j)
                self.itemconfig(f"piece_poly_{j}", outline=base_col, width=2.0)
        self._drag_colliding_others = set()

        if 0 <= self.dragged_index < len(self.placed_pieces) and hasattr(self, "_pre_drag_pos") and self._pre_drag_pos:
            p_curr = self.placed_pieces[self.dragged_index]
            contour = p_curr.get("contour") or (p_curr.get("shape", {}).get("contour") if isinstance(p_curr.get("shape"), dict) else [])
            rot = float(p_curr.get("rotation", p_curr.get("angle", 0.0)))
            poly_curr = transform_contour(contour, p_curr["x"], p_curr["y"], rot)
            bbox_curr = polygon_bbox(poly_curr)
            has_collision = False

            if self.material:
                mw = self.material["width_mm"]
                mh = self.material["height_mm"]
                if bbox_curr[0] < -0.01 or bbox_curr[1] < -0.01 or bbox_curr[2] > mw + 0.01 or bbox_curr[3] > mh + 0.01:
                    has_collision = True

            if not has_collision:
                for j, other in enumerate(self.placed_pieces):
                    if j == self.dragged_index:
                        continue
                    o_contour = other.get("contour") or (other.get("shape", {}).get("contour") if isinstance(other.get("shape"), dict) else [])
                    o_rot = float(other.get("rotation", other.get("angle", 0.0)))
                    other_poly = transform_contour(o_contour, other["x"], other["y"], o_rot)
                    other_bbox = polygon_bbox(other_poly)
                    if polygons_collide(poly_curr, other_poly, gap=0.0, bbox_a=bbox_curr, bbox_b=other_bbox):
                        has_collision = True
                        break

            if has_collision:
                # Regra Estrita: JAMAIS uma peça poderá ficar sobreposta a outra!
                p_curr["x"], p_curr["y"] = self._pre_drag_pos

            self.redraw()
            if self.on_change:
                self.on_change()

        self.dragged_index = -1
        self._pre_drag_pos = None

    def cancel_drag(self, event=None):
        if 0 <= self.dragged_index < len(self.placed_pieces) and hasattr(self, "_pre_drag_pos") and self._pre_drag_pos:
            self.delete("drag_ghost")
            for j in getattr(self, "_drag_colliding_others", set()):
                if 0 <= j < len(self.placed_pieces):
                    o_p = self.placed_pieces[j]
                    s_val = str(o_p.get("size") or (o_p.get("shape", {}).get("size") if isinstance(o_p.get("shape"), dict) else "") or o_p.get("name") or "41")
                    base_col = get_color_for_size(s_val, j)
                    self.itemconfig(f"piece_poly_{j}", outline=base_col, width=2.0)
            self._drag_colliding_others = set()
            p = self.placed_pieces[self.dragged_index]
            p["x"], p["y"] = self._pre_drag_pos
            self.dragged_index = -1
            self._pre_drag_pos = None
            self.redraw()
            if self.on_change:
                self.on_change()

    # =========================================================================
    # Simulação de Corte
    # =========================================================================
    def start_simulation(self):
        if not self.placed_pieces:
            return
        self.sim_running = True
        self.sim_piece_idx = 0
        self.sim_pt_idx = 0
        self._sim_step()

    def stop_simulation(self):
        self.sim_running = False
        self.redraw()

    def _sim_step(self):
        if not self.sim_running or not self.placed_pieces:
            return

        if self.sim_piece_idx >= len(self.placed_pieces):
            self.sim_running = False
            self.redraw()
            return

        p = self.placed_pieces[self.sim_piece_idx]
        poly = transform_contour(p["shape"]["contour"], p["x"], p["y"], p["rotation"])
        pt = poly[self.sim_pt_idx]
        self.sim_head_pos = (pt["x"], pt["y"])

        self.sim_pt_idx += 1
        if self.sim_pt_idx >= len(poly):
            self.sim_pt_idx = 0
            self.sim_piece_idx += 1

        self.redraw()
        self.after(40, self._sim_step)

    # =========================================================================
    # Renderização da Mesa CAD
    # =========================================================================
    def redraw_all(self):
        self.redraw()

    def redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()

        if not self.material:
            return

        mw = self.material["width_mm"]
        mh = self.material["height_mm"]

        # 1. Desenha Grade Milimétrica (Grid)
        step = 100.0  # mm
        cur_x = 0
        while cur_x <= mw:
            sx1, sy1 = self.world_to_screen(cur_x, 0)
            sx2, sy2 = self.world_to_screen(cur_x, mh)
            self.create_line(sx1, sy1, sx2, sy2, fill=THEME["canvas_grid"], width=1)
            cur_x += step

        cur_y = 0
        while cur_y <= mh:
            sx1, sy1 = self.world_to_screen(0, cur_y)
            sx2, sy2 = self.world_to_screen(mw, cur_y)
            self.create_line(sx1, sy1, sx2, sy2, fill=THEME["canvas_grid"], width=1)
            cur_y += step

        # 2. Desenha Contorno da Mesa de Material
        sx1, sy1 = self.world_to_screen(0, 0)
        sx2, sy2 = self.world_to_screen(mw, mh)
        self.create_rectangle(
            sx1, sy1, sx2, sy2,
            outline="#0a246a",
            fill=THEME["canvas_bed"],
            width=2
        )

        # Dimensões da mesa em preto nítido
        self.create_text(
            (sx1 + sx2) / 2, sy1 - 14,
            text=f"{mw} mm", fill=THEME["text_main"], font=("Segoe UI", 9, "bold")
        )
        self.create_text(
            sx1 - 30, (sy1 + sy2) / 2,
            text=f"{mh} mm", fill=THEME["text_main"], font=("Segoe UI", 9, "bold")
        )

        # 3. Detecção Ativa de Colisão e Desenho de Peças Aninhadas
        colliding_indices = set()
        num_pieces = len(self.placed_pieces)
        cached_geoms = []
        for p in self.placed_pieces:
            contour = self._resolve_piece_contour(p)
            rot = float(p.get("rotation", p.get("angle", 0.0)))
            px = float(p.get("x", 0.0))
            py = float(p.get("y", 0.0))
            poly = transform_contour(contour, px, py, rot) if contour else []
            bbox = polygon_bbox(poly) if poly else (0, 0, 0, 0)
            cached_geoms.append((poly, bbox))

        for i in range(num_pieces):
            poly_i, bbox_i = cached_geoms[i]
            for j in range(i + 1, num_pieces):
                poly_j, bbox_j = cached_geoms[j]
                if polygons_collide(poly_i, poly_j, gap=0.0, bbox_a=bbox_i, bbox_b=bbox_j):
                    colliding_indices.add(i)
                    colliding_indices.add(j)

        for idx, p in enumerate(self.placed_pieces):
            is_selected = (idx == self.selected_index)
            is_colliding = (idx in colliding_indices)
            poly, _ = cached_geoms[idx]

            # Converte polígono para coordenadas de tela
            screen_coords = []
            for pt in poly:
                sx, sy = self.world_to_screen(pt["x"], pt["y"])
                screen_coords.extend([sx, sy])

            # Contorno de corte (Fill & Stroke clássico com alerta de colisão)
            if is_colliding:
                fill_col = "#fee2e2"
                outline_col = "#dc2626"
                line_width = 3.0
            elif is_selected:
                fill_col = "#dbeafe"
                outline_col = "#0a246a"
                line_width = 2.5
            else:
                size_val = str(p.get("size") or (p.get("shape", {}).get("size") if isinstance(p.get("shape"), dict) else "") or p.get("name") or "41")
                piece_col = get_color_for_size(size_val, idx)
                fill_col = "#ffffff"
                outline_col = piece_col
                line_width = 2.0

            if len(screen_coords) >= 6:
                self.create_polygon(
                    screen_coords,
                    fill=fill_col,
                    outline=outline_col,
                    width=line_width,
                    tags=(f"piece_{idx}", f"piece_poly_{idx}", "piece_item")
                )

            # Furações (Punches) em verde/vermelho nítido
            holes = p.get("holes") or (p.get("shape", {}).get("holes") if isinstance(p.get("shape"), dict) else []) or []
            for hole in holes:
                rx, ry = rotate_point(hole["x"], hole["y"], p.get("rotation", 0.0))
                hx = p["x"] + rx
                hy = p["y"] + ry
                hsx, hsy = self.world_to_screen(hx, hy)
                hr = max(2, hole.get("r", 2.0) * self.zoom)
                self.create_oval(
                    hsx - hr, hsy - hr, hsx + hr, hsy + hr,
                    fill="#22c55e", outline="#008000", width=1.5,
                    tags=(f"piece_{idx}", "piece_item")
                )

            # Rótulo da Peça com o NÚMERO
            size_val = str(p.get("size") or (p.get("shape", {}).get("size") if isinstance(p.get("shape"), dict) else "") or p.get("name") or "41")
            piece_col = get_color_for_size(size_val, idx)
            p_id = p.get("id", idx + 1)
            p_name = p.get("name") or (p.get("shape", {}).get("name") if isinstance(p.get("shape"), dict) else "Peça")
            lbl_sx, lbl_sy = self.world_to_screen(p["x"] + 20, p["y"] + 30)
            self.create_text(
                lbl_sx, lbl_sy,
                text=f"#{p_id} [Nº {size_val}] {p_name}",
                fill="#dc2626" if is_colliding else (piece_col if not is_selected else "#0a246a"),
                font=("Segoe UI", 8, "bold" if (is_selected or is_colliding) else "normal"),
                anchor="w",
                tags=(f"piece_{idx}", f"piece_txt_{idx}", "piece_item")
            )

        # 4. Cabeçote CNC se Simulação estiver Ativa (Mira vermelha clássica)
        if self.sim_running:
            hx, hy = self.world_to_screen(self.sim_head_pos[0], self.sim_head_pos[1])
            self.create_oval(hx - 12, hy - 12, hx + 12, hy + 12, fill="#fca5a5", outline="#dc2626")
            self.create_oval(hx - 5, hy - 5, hx + 5, hy + 5, fill="#dc2626", outline="#991b1b")
            self.create_line(hx - 16, hy, hx + 16, hy, fill="#dc2626", width=2)
            self.create_line(hx, hy - 16, hx, hy + 16, fill="#dc2626", width=2)

        # 5. Barra de Informações do Canvas (HUD inferior)
        col_status = f" | ⚠️ ALERTA: {len(colliding_indices)} PEÇAS COM SOBREPOSIÇÃO!" if colliding_indices else " | COLISÕES: 0 (OK)"
        self.create_text(
            15, h - 15,
            text=f"ZOOM: {int(self.zoom * 100)}% | PEÇAS: {len(self.placed_pieces)}{col_status}",
            fill="#dc2626" if colliding_indices else THEME["text_main"],
            font=("Segoe UI", 8, "bold"),
            anchor="w"
        )
