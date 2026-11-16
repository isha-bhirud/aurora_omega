"""
ARTOS 2.0 (Modernized Standalone Simulation Engine)
Updated to run seamlessly against AURORA's normalized MySQL database (`aurora_db`).
- Replaces hardcoded credentials with `.env`
- Uses parameterized queries
- Connects directly to real database runways, taxiways, and waypoints
"""

import pygame
import sys
import math
import random
from datetime import datetime
from db import fetch_all, fetch_one, execute
from ui_components import CompassHUD

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 1000
AIRCRAFT_RADIUS = 5
WAYPOINT_RADIUS = 5
WAYPOINT_THRESHOLD = 6
COLLISION_THRESHOLD = 25
RUNWAY_WIDTH = 20
TAXIWAY_WIDTH = 2
MESSAGE_BOX_WIDTH = 450
MAX_MESSAGES = 4
GRID_COLOR = (0, 70, 0)

class Aircraft:
    def __init__(self, flight_name, position, weight, depart_time):
        self.flight_name = flight_name
        self.weight = weight
        self.depart_time = depart_time
        self.position = list(position)
        self.waypoints = []
        self.current_waypoint = 0
        self.stop_time = 0
        self.delayed = False
        self.heading = 0.0
        self.message_list = []
        self.speed = 1.4

    def draw(self, screen, font):
        pygame.draw.circle(screen, (255, 50, 50), (int(self.position[0]), int(self.position[1])), AIRCRAFT_RADIUS)
        text_surf = font.render(self.flight_name, True, (255, 255, 255))
        screen.blit(text_surf, (int(self.position[0]) - 20, int(self.position[1]) - 16))

    def set_route(self, waypoints):
        self.waypoints = waypoints
        self.current_waypoint = 0

    def move_to_next_waypoint(self, messages):
        if self.current_waypoint < len(self.waypoints) and self.stop_time == 0 and not self.delayed:
            target = self.waypoints[self.current_waypoint]
            dx = target[0] - self.position[0]
            dy = target[1] - self.position[1]
            dist = math.hypot(dx, dy)

            if dist > WAYPOINT_THRESHOLD:
                self.position[0] += (dx / dist) * self.speed
                self.position[1] += (dy / dist) * self.speed
                self.heading = math.atan2(dy, dx)
            else:
                self.stop_time = 45
                self.current_waypoint += 1
                msg = f"{self.flight_name}: Cleared waypoint {self.current_waypoint}"
                messages.append(msg)
                self.message_list.append(msg)

    def check_collision(self, other):
        dist = math.hypot(self.position[0] - other.position[0], self.position[1] - other.position[1])
        return dist < COLLISION_THRESHOLD

    def update_stop_time(self):
        if self.stop_time > 0:
            self.stop_time -= 1

    def is_clicked(self, pos):
        return math.hypot(pos[0] - self.position[0], pos[1] - self.position[1]) <= (AIRCRAFT_RADIUS + 8)

def run_simulation(airport_id=1):
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption(f"ARTOS 2.0 — Airport Scope (Airport ID: {airport_id})")
    clock = pygame.time.Clock()

    font = pygame.font.SysFont("Lucida Bright, Arial", 16)
    font_bold = pygame.font.SysFont("Lucida Bright, Arial", 18, bold=True)
    compass = CompassHUD(center=(WINDOW_WIDTH - 80, 80), radius=45)

    # 1. Fetch runways from aurora_db
    runways = fetch_all("""
        SELECT runway_id, runway_designation, start_x, start_y, end_x, end_y
        FROM runway WHERE airport_id = %s
    """, (airport_id,))

    # 2. Fetch taxiways from aurora_db
    taxiways = fetch_all("""
        SELECT taxiway_name, start_x, start_y, end_x, end_y
        FROM taxiway WHERE airport_id = %s
    """, (airport_id,))

    # 3. Fetch waypoints from aurora_db
    waypoints_data = fetch_all("""
        SELECT mf.feature_name, mf.pos_x, mf.pos_y
        FROM map_feature mf
        JOIN airport_map am ON mf.map_id = am.map_id
        WHERE am.airport_id = %s
    """, (airport_id,))

    # 4. Spawn active aircraft from flight_operation
    ops = fetch_all("""
        SELECT f.flight_number, act.max_takeoff_weight, fo.scheduled_datetime, fo.operation_type
        FROM flight_operation fo
        JOIN flight f ON fo.flight_id = f.flight_id
        JOIN aircraft ac ON f.aircraft_id = ac.aircraft_id
        JOIN aircraft_type act ON ac.type_id = act.type_id
        WHERE fo.airport_id = %s
        LIMIT 5
    """, (airport_id,))

    aircraft_list = []
    messages = [f"SYSTEM: Radar Scope Active (Airport ID: {airport_id})"]

    wp_coords = [(w["pos_x"], w["pos_y"]) for w in waypoints_data]
    if not wp_coords:
        wp_coords = [(125, 200), (300, 200), (600, 0)]

    for idx, op in enumerate(ops):
        start_pos = (125, 200 + idx * 80)
        ac = Aircraft(op["flight_number"], start_pos, op["max_takeoff_weight"], str(op["scheduled_datetime"]))
        # Build route through available waypoints
        route = [start_pos] + wp_coords[idx % len(wp_coords): idx % len(wp_coords) + 3]
        if runways:
            rw = runways[idx % len(runways)]
            route.append((rw["start_x"], rw["start_y"]))
            route.append((rw["end_x"], rw["end_y"]))
        ac.set_route(route)
        aircraft_list.append(ac)

    running = True
    selected_ac = None

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
                break
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clicked_any = False
                for ac in aircraft_list:
                    if ac.is_clicked(event.pos):
                        selected_ac = ac
                        messages.append(f"RADAR: Selected {ac.flight_name}")
                        clicked_any = True
                        break
                if not clicked_any:
                    selected_ac = None

        # Collision detection
        for i in range(len(aircraft_list)):
            for j in range(i + 1, len(aircraft_list)):
                if aircraft_list[i].check_collision(aircraft_list[j]):
                    aircraft_list[i].stop_time = 30
                    aircraft_list[j].stop_time = 30

        # Background
        screen.fill((0, 0, 0))

        # Grid lines (0, 70, 0)
        for x in range(0, WINDOW_WIDTH, 35):
            pygame.draw.line(screen, GRID_COLOR, (x, 0), (x, WINDOW_HEIGHT), 1)
        for y in range(0, WINDOW_HEIGHT, 35):
            pygame.draw.line(screen, GRID_COLOR, (0, y), (WINDOW_WIDTH, y), 1)

        # Apron zone
        pygame.draw.rect(screen, (30, 40, 35), (50, 0, 100, WINDOW_HEIGHT))

        # Taxiways
        for tw in taxiways:
            p1 = (tw["start_x"], tw["start_y"])
            p2 = (tw["end_x"], tw["end_y"])
            pygame.draw.line(screen, (0, 255, 255), p1, p2, TAXIWAY_WIDTH)
            mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
            lbl = font.render(tw["taxiway_name"], True, (0, 255, 255))
            screen.blit(lbl, mid)

        # Runways
        for rw in runways:
            p1 = (rw["start_x"], rw["start_y"])
            p2 = (rw["end_x"], rw["end_y"])
            pygame.draw.line(screen, (25, 141, 200), p1, p2, RUNWAY_WIDTH)
            pygame.draw.line(screen, (255, 255, 255), p1, p2, 2)
            mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
            lbl = font.render(f"Runway {rw['runway_designation']}", True, (255, 255, 255))
            screen.blit(lbl, (mid[0] - 20, mid[1] - 20))

        # Waypoints
        for wp in waypoints_data:
            p = (wp["pos_x"], wp["pos_y"])
            pygame.draw.circle(screen, (255, 0, 0), p, WAYPOINT_RADIUS)
            lbl = font.render(wp["feature_name"], True, (255, 250, 15))
            screen.blit(lbl, (p[0] + 6, p[1] - 6))

        # Aircraft
        for ac in aircraft_list:
            ac.move_to_next_waypoint(messages)
            ac.update_stop_time()
            ac.draw(screen, font)

        # Compass HUD
        active_h = math.degrees(selected_ac.heading) if selected_ac else 90
        compass.draw(screen, active_h, font)

        # Message box (Bottom Right)
        msg_rect = pygame.Rect(WINDOW_WIDTH - MESSAGE_BOX_WIDTH, WINDOW_HEIGHT - 120, MESSAGE_BOX_WIDTH, 110)
        pygame.draw.rect(screen, (20, 28, 38, 220), msg_rect, border_radius=4)
        pygame.draw.rect(screen, (0, 150, 200), msg_rect, width=1, border_radius=4)
        hdr = font_bold.render("ATC FLIGHT LOGS", True, (0, 255, 255))
        screen.blit(hdr, (msg_rect.x + 10, msg_rect.y + 8))
        for idx, m in enumerate(messages[-MAX_MESSAGES:]):
            m_surf = font.render(m, True, (220, 230, 240))
            screen.blit(m_surf, (msg_rect.x + 10, msg_rect.y + 30 + (idx * 18)))

        # Selected aircraft pathway
        if selected_ac and len(selected_ac.waypoints) > 1:
            for k in range(len(selected_ac.waypoints) - 1):
                pygame.draw.line(screen, (255, 255, 0), selected_ac.waypoints[k], selected_ac.waypoints[k + 1], 2)

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()

if __name__ == "__main__":
    ap_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run_simulation(ap_id)
