"""
AURORA - Artos 2D Radar Simulation & Airport Map Visualizer
Faithfully preserves and elevates the Pygame radar engine from ARTOS:
- Loads airport infrastructure directly from MySQL (aurora_db)
- Renders runways (thick blue strips), taxiways (cyan lines), and waypoints (red/yellow)
- Supports switching between Map 1 (DFW Hub) and Map 2 (BOM Hub)
- Interactive aircraft telemetry and waypoint route viewer
"""

import pygame
import math
from db import fetch_all, fetch_one
from ui_components import CompassHUD, COLOR_GRID, COLOR_ACCENT_CYAN, COLOR_RUNWAY_BLUE, COLOR_TEXT_YELLOW, COLOR_TEXT_MUTED, COLOR_SUCCESS_GREEN

class ArtosRadarView:
    def __init__(self, rect):
        self.rect = pygame.Rect(rect)
        self.airports = []
        self.current_airport_id = None
        self.runways = []
        self.taxiways = []
        self.waypoints = []
        self.terminals = []
        self.stands = []
        self.aircraft_markers = []
        self.selected_aircraft = None
        self.compass = CompassHUD(center=(self.rect.right - 70, self.rect.y + 70), radius=38)
        self.messages = ["SYSTEM: Markers reference assigned runways; no live positions are stored"]
        self.load_map_data()

    def set_airport(self, airport_id):
        if not any(a["airport_id"] == airport_id for a in self.airports):
            return False
        if airport_id == self.current_airport_id:
            return True
        self.current_airport_id = airport_id
        self.selected_aircraft = None
        self.aircraft_markers = []
        self.load_map_data()
        airport = next(a for a in self.airports if a["airport_id"] == airport_id)
        self.messages.append(f"SCOPE: {airport['iata_code']} / {airport['icao_code']}")
        self.messages = self.messages[-12:]
        return True

    def load_map_data(self):
        # Scope selection is limited to airports with an active, configured map.
        # Airports such as LHR may have runway records without a map layout.
        self.airports = fetch_all("""
            SELECT ap.airport_id, ap.iata_code, ap.icao_code, ap.airport_name
            FROM airport ap
            WHERE EXISTS (
                SELECT 1 FROM airport_map am
                WHERE am.airport_id = ap.airport_id AND am.map_status = 'ACTIVE'
            )
            ORDER BY ap.iata_code
        """)
        if self.current_airport_id is None or not any(a["airport_id"] == self.current_airport_id for a in self.airports):
            self.current_airport_id = self.airports[0]["airport_id"] if self.airports else None
        if self.current_airport_id is None:
            self.runways, self.taxiways, self.waypoints = [], [], []
            self.terminals, self.stands, self.aircraft_markers = [], [], []
            return
        # 1. Runways from aurora_db
        rw_query = """
        SELECT runway_id, runway_designation, start_x, start_y, end_x, end_y, runway_status, surface_type, runway_length
        FROM runway
        WHERE airport_id = %s
        """
        self.runways = fetch_all(rw_query, (self.current_airport_id,))

        # 2. Taxiways from aurora_db
        tw_query = """
        SELECT taxiway_id, taxiway_name, start_x, start_y, end_x, end_y, surface_type
        FROM taxiway
        WHERE airport_id = %s
        """
        self.taxiways = fetch_all(tw_query, (self.current_airport_id,))

        # 3. Waypoints from map_feature in aurora_db
        wp_query = """
        SELECT mf.feature_id, mf.feature_name, mf.pos_x, mf.pos_y
        FROM map_feature mf
        JOIN airport_map am ON mf.map_id = am.map_id
        WHERE am.airport_id = %s
        """
        self.waypoints = fetch_all(wp_query, (self.current_airport_id,))

        self.terminals = fetch_all("""SELECT terminal_id, terminal_name, terminal_type
            FROM terminal WHERE airport_id = %s ORDER BY terminal_name""", (self.current_airport_id,))
        self.stands = fetch_all("""SELECT stand_id, stand_code, max_aircraft_size, stand_status
            FROM aircraft_stand WHERE airport_id = %s ORDER BY stand_code""", (self.current_airport_id,))

        # 4. Active flights at this station
        ac_query = """
        SELECT 
          fo.operation_id, fo.operation_type, fo.scheduled_datetime,
          f.flight_number, ac.registration_number, act.model, act.max_takeoff_weight,
          rd.designation AS assigned_direction, rd.heading AS assigned_heading,
          rw.runway_designation,
          rw.start_x, rw.start_y, rw.end_x, rw.end_y
        FROM flight_operation fo
        JOIN flight f ON fo.flight_id = f.flight_id
        JOIN aircraft ac ON f.aircraft_id = ac.aircraft_id
        JOIN aircraft_type act ON ac.type_id = act.type_id
        LEFT JOIN runway_assignment ra ON fo.operation_id = ra.operation_id
        LEFT JOIN runway_direction rd ON ra.direction_id = rd.direction_id
        LEFT JOIN runway rw ON rd.runway_id = rw.runway_id
        WHERE fo.airport_id = %s AND ra.assignment_id IS NOT NULL
          AND rw.airport_id = fo.airport_id
        ORDER BY fo.scheduled_datetime, fo.operation_id
        LIMIT 12
        """
        active_ops = fetch_all(ac_query, (self.current_airport_id,))

        self.aircraft_markers = []
        for op in active_ops:
            if op.get("start_x") is None or op.get("end_x") is None:
                continue
            # This marker references a runway assignment, not a live aircraft position.
            # The schema has no aircraft-position field, so no live location is implied.
            px = (float(op["start_x"]) + float(op["end_x"])) / 2
            py = (float(op["start_y"]) + float(op["end_y"])) / 2
            heading = float(op["assigned_heading"])

            self.aircraft_markers.append({
                "op": op,
                "x": px,
                "y": py,
                "heading": heading
            })

    def _coordinate_transform(self):
        """Fit actual infrastructure coordinates without stretching the layout."""
        points = []
        for item in self.runways + self.taxiways:
            points.extend(((item["start_x"], item["start_y"]), (item["end_x"], item["end_y"])))
        points.extend((wp["pos_x"], wp["pos_y"]) for wp in self.waypoints)
        if not points:
            return lambda x, y: (self.rect.centerx, self.rect.centery)
        min_x, max_x = min(float(p[0]) for p in points), max(float(p[0]) for p in points)
        min_y, max_y = min(float(p[1]) for p in points), max(float(p[1]) for p in points)
        span_x, span_y = max(max_x - min_x, 1.0), max(max_y - min_y, 1.0)
        pad = 42
        scale = min((self.rect.width - 2 * pad) / span_x, (self.rect.height - 2 * pad) / span_y)
        used_w, used_h = span_x * scale, span_y * scale
        left, top = self.rect.x + (self.rect.width - used_w) / 2, self.rect.y + (self.rect.height - used_h) / 2
        return lambda x, y: (int(left + (float(x) - min_x) * scale), int(top + (float(y) - min_y) * scale))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            # Check if an aircraft marker was clicked
            for ac in self.aircraft_markers:
                # Map coordinates relative to rect
                sx, sy = self._coordinate_transform()(ac["x"], ac["y"])
                if math.hypot(mx - sx, my - sy) < 14:
                    self.selected_aircraft = ac
                    self.messages.append(f"PILOT: {ac['op']['flight_number']} reporting inbound beacon.")
                    return True
            # Clicking elsewhere deselects
            if self.rect.collidepoint(event.pos):
                self.selected_aircraft = None
        return False

    def draw(self, surface, font_main, font_small):
        # Clip drawing to radar sub-rectangle
        clip_rect = surface.get_clip()
        surface.set_clip(self.rect)

        # 1. Background
        pygame.draw.rect(surface, (0, 0, 0), self.rect)

        # 2. Radar Grid lines (0, 70, 0)
        grid_spacing = 35
        for x in range(self.rect.x, self.rect.right, grid_spacing):
            pygame.draw.line(surface, COLOR_GRID, (x, self.rect.y), (x, self.rect.bottom), 1)
        for y in range(self.rect.y, self.rect.bottom, grid_spacing):
            pygame.draw.line(surface, COLOR_GRID, (self.rect.x, y), (self.rect.right, y), 1)

        to_screen = self._coordinate_transform()

        airport = next((a for a in self.airports if a["airport_id"] == self.current_airport_id), None)
        if airport:
            meta = f"{airport['iata_code']} / {airport['icao_code']}   |   {len(self.terminals)} TERMINALS   |   {len(self.stands)} STANDS"
            meta_surface = font_small.render(meta, True, (185, 202, 212))
            meta_rect = pygame.Rect(self.rect.x + 10, self.rect.y + 10,
                                    meta_surface.get_width() + 16, meta_surface.get_height() + 10)
            pygame.draw.rect(surface, (15, 24, 32), meta_rect)
            pygame.draw.rect(surface, (48, 64, 79), meta_rect, 1)
            surface.blit(meta_surface, (meta_rect.x + 8, meta_rect.y + 5))
        marker_note = font_small.render("AIRCRAFT MARKERS: RUNWAY ASSIGNMENT REFERENCES", True, COLOR_TEXT_MUTED)
        surface.blit(marker_note, (self.rect.x + 10, self.rect.y + 42))

        # 4. Draw Taxiways (Cyan paths)
        for tw in self.taxiways:
            p1 = to_screen(tw["start_x"], tw["start_y"])
            p2 = to_screen(tw["end_x"], tw["end_y"])
            pygame.draw.line(surface, (42, 168, 177), p1, p2, 4)
            # Label
            mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
            lbl = font_small.render(tw["taxiway_name"], True, COLOR_ACCENT_CYAN)
            surface.blit(lbl, (mid[0] + 4, mid[1] - 8))

        # 5. Draw Runways (Thick blue strips)
        for rw in self.runways:
            p1 = to_screen(rw["start_x"], rw["start_y"])
            p2 = to_screen(rw["end_x"], rw["end_y"])
            pygame.draw.line(surface, (42, 94, 130), p1, p2, 18)
            # Centerline dashed effect
            pygame.draw.line(surface, (240, 240, 240), p1, p2, 2)

            # Runway labels
            mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
            lbl = font_small.render(f"RWY {rw['runway_designation']}", True, (255, 255, 255))
            surface.blit(lbl, (mid[0] - 25, mid[1] - 20))

        # 6. Draw Waypoints (Red circles with yellow labels)
        for wp in self.waypoints:
            p = to_screen(wp["pos_x"], wp["pos_y"])
            pygame.draw.circle(surface, (255, 0, 0), p, 5)
            pygame.draw.circle(surface, COLOR_TEXT_YELLOW, p, 2)
            lbl = font_small.render(wp["feature_name"], True, COLOR_TEXT_YELLOW)
            surface.blit(lbl, (p[0] + 6, p[1] - 6))

        # 7. Draw Aircraft Markers
        for ac in self.aircraft_markers:
            p = to_screen(ac["x"], ac["y"])
            is_sel = (self.selected_aircraft == ac)
            dot_color = (255, 205, 85) if is_sel else COLOR_SUCCESS_GREEN

            # Pulsing target circle
            pygame.draw.circle(surface, dot_color, p, 7 if is_sel else 5)
            if is_sel:
                pygame.draw.circle(surface, (0, 255, 255), p, 12, 1)

            # Heading vector line
            h_rad = math.radians(ac["heading"])
            end_x = p[0] + 25 * math.cos(h_rad)
            end_y = p[1] - 25 * math.sin(h_rad)
            pygame.draw.line(surface, (255, 200, 200), p, (int(end_x), int(end_y)), 2)

            # Flight text tag
            tag_str = f"{ac['op']['flight_number']} ({ac['op']['model'][:6]})"
            t_surf = font_small.render(tag_str, True, (255, 255, 255))
            surface.blit(t_surf, (p[0] - 20, p[1] - 18))

        # 8. Compass HUD (Top Right)
        active_heading = self.selected_aircraft["heading"] if self.selected_aircraft else 0
        self.compass.draw(surface, active_heading, font_small)

        # 9. Tactical Message Log Box (Bottom Right)
        msg_box_rect = pygame.Rect(self.rect.right - 340, self.rect.bottom - 110, 330, 100)
        pygame.draw.rect(surface, (15, 25, 35, 220), msg_box_rect, border_radius=4)
        pygame.draw.rect(surface, (0, 100, 150), msg_box_rect, width=1, border_radius=4)

        log_hdr = font_small.render("ATC RADAR COMMUNICATIONS LOG", True, COLOR_ACCENT_CYAN)
        surface.blit(log_hdr, (msg_box_rect.x + 8, msg_box_rect.y + 6))
        for idx, m in enumerate(self.messages[-3:]):
            m_surf = font_small.render(m, True, (220, 230, 240))
            surface.blit(m_surf, (msg_box_rect.x + 8, msg_box_rect.y + 28 + (idx * 20)))

        # 10. Selected Aircraft Details Panel (Bottom Left overlay)
        if self.selected_aircraft:
            op = self.selected_aircraft["op"]
            panel_rect = pygame.Rect(self.rect.x + 20, self.rect.bottom - 150, 360, 135)
            pygame.draw.rect(surface, (15, 24, 34), panel_rect, border_radius=6)
            pygame.draw.rect(surface, COLOR_ACCENT_CYAN, panel_rect, width=1, border_radius=6)

            title = font_main.render(f"TARGET: {op['flight_number']} [{op['registration_number']}]", True, COLOR_TEXT_YELLOW)
            surface.blit(title, (panel_rect.x + 12, panel_rect.y + 10))

            info_lines = [
                f"Airframe Type: {op['model']} (MTOW {float(op['max_takeoff_weight']):,.0f} kg)",
                f"Operation: {op['operation_type']} @ {op['scheduled_datetime']}",
                f"Assigned Vector: {op['assigned_direction'] or 'UNASSIGNED'} ({op['runway_designation'] or 'PENDING'})",
                f"Assigned Direction Heading: {self.selected_aircraft['heading']:.1f}°"
            ]
            for idx, ln in enumerate(info_lines):
                ln_surf = font_small.render(ln, True, (230, 240, 250))
                surface.blit(ln_surf, (panel_rect.x + 12, panel_rect.y + 38 + (idx * 22)))

        # Scope Border
        if not self.runways:
            empty = font_main.render("No runway layout is recorded for this airport.", True, COLOR_TEXT_MUTED)
            surface.blit(empty, (self.rect.centerx - empty.get_width() // 2,
                                 self.rect.centery - empty.get_height() // 2))
        pygame.draw.rect(surface, (40, 60, 85), self.rect, width=1)
        surface.set_clip(clip_rect)
