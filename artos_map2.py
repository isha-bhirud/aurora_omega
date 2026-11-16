"""
ARTOS / AURORA — Map 2 Radar Scope Simulation
Chhatrapati Shivaji Maharaj International Airport (BOM / VABB, Mumbai)
Preserves authentic Artos window dimensions, grid spacing, coordinate alignment,
aircraft physics, collision avoidance, start button, and pathway/compass inspector.
"""

import pygame
import sys
import random
import math
import os
from datetime import datetime

# Import AURORA database manager
from db import fetch_all, fetch_one, execute

pygame.init()
pygame.font.init()

map_id = 2 # Mumbai (BOM)

# Exact Artos Constants for Map 2
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 1000
AIRCRAFT_RADIUS = 4
WAYPOINT_RADIUS = 5
WAYPOINT_THRESHOLD = 5
COLLISION_THRESHOLD = 25
RUNWAY_WIDTH = 20
TAXIWAY_WIDTH = 2
MESSAGE_BOX_WIDTH = 500
MAX_MESSAGES = 3
speed = 1.7
c = 0

messages = []
aircraft_list = []
clock = pygame.time.Clock()

current_position = (0, 0)
current_speed = speed

# Fonts (Exact Artos fonts)
font = pygame.font.SysFont('garamond', 24)
small_font = pygame.font.Font(None, 20)
header_font = pygame.font.Font(None, 36)
label_font = pygame.font.Font(None, 30)

class Aircraft:
    def __init__(self, flight_name, position, weight, depart_time):
        self.flight_name = flight_name
        self.weight = weight
        self.depart_time = depart_time
        self.position = list(position)
        self.waypoints2 = []
        self.current_waypoint = 0
        self.font = pygame.font.Font(None, 20)
        self.stop_time = 0
        self.message_displayed = False
        self.delayed = False
        self.heading = 0.0
        self.message_list = []

    @classmethod
    def spawn_aircraft(cls):
        flight_name = f"Flight{random.randint(1, 100)}"
        x = random.randrange(99, 750, 25)
        y = 600
        position = (x, y)
        weight = 0
        depart_time = None
        return cls(flight_name, position, weight, depart_time)

    def draw(self, surface):
        pygame.draw.circle(surface, (255, 0, 0), (int(self.position[0]), int(self.position[1])), AIRCRAFT_RADIUS, 0)
        # Artos Map 2 uses bright chartreuse for flight text
        text_surface = self.font.render(self.flight_name, True, (207, 250, 4))
        text_rect = text_surface.get_rect(center=(int(self.position[0]), int(self.position[1]) - AIRCRAFT_RADIUS - 5))
        surface.blit(text_surface, text_rect)

    def move_to_end_of_runway(self, runway):
        # Exact Artos Map 2 runway coordinate paths (Runway 9 and Runway 10)
        if runway in (1, 9):
            self.waypoints2 = [(800, 600), (800, 400), (170, 400), (100, 200)]
        elif runway in (2, 10):
            self.waypoints2 = [(800, 600), (800, 500), (200, 500)]
        else:
            self.waypoints2 = [(800, 600), (800, 400), (170, 400), (100, 200)]
        self.current_waypoint = 0

    def move_to_next_waypoint(self):
        if len(aircraft_list) > 2 and (self.current_waypoint == 0 or self.position[0] == 50):
            if self not in aircraft_list[-4::-1] and not self.message_displayed:
                if self.position[1] != self.position[1] + 50 and self.stop_time > 0:
                    self.position[1] = self.position[1] + 50
                    self.message_displayed = True
                    self.delayed = True

                self.stop_for_delay()
                d_str = self.depart_time.strftime("%H:%M:%S") if isinstance(self.depart_time, datetime) else str(self.depart_time)
                self.receive_message(f"Departure time: {d_str}")
                return

        if self.current_waypoint < len(self.waypoints2) and self.stop_time == 0 and not self.delayed:
            target = self.waypoints2[self.current_waypoint]
            dx = target[0] - self.position[0]
            dy = target[1] - self.position[1]
            distance = (dx ** 2 + dy ** 2) ** 0.5

            if distance > WAYPOINT_THRESHOLD:
                ratio = speed / distance
                self.position[0] += dx * ratio
                self.position[1] += dy * ratio
            else:
                self.stop_for_delay()
                self.current_waypoint += 1
                temp = f"Next waypoint : {target}"
                self.receive_message(temp)

            self.heading = round(math.atan2(target[1] - self.position[1], target[0] - self.position[0]), 3)

    def stop_for_delay(self):
        self.stop_time = 60

    def check_collision(self, other_aircraft):
        time_step = 1.0
        future_pos1 = (
            self.position[0] + speed * time_step * math.cos(self.heading),
            self.position[1] + speed * time_step * math.sin(self.heading)
        )
        future_pos2 = (
            other_aircraft.position[0] + speed * time_step * math.cos(other_aircraft.heading),
            other_aircraft.position[1] + speed * time_step * math.sin(other_aircraft.heading)
        )
        dist = math.hypot(future_pos2[0] - future_pos1[0], future_pos2[1] - future_pos1[1])
        return dist < COLLISION_THRESHOLD

    def stop_for_collision(self):
        self.stop_time = 3

    def update_stop_time(self):
        if self.stop_time > 0:
            self.stop_time -= 1

    def receive_message(self, message):
        messages.append(f"{self.flight_name}: {message}")
        self.message_list.append(message)

    def is_clicked(self, pos):
        aircraft_rect = pygame.Rect(self.position[0] - AIRCRAFT_RADIUS - 4, self.position[1] - AIRCRAFT_RADIUS - 4, 2 * AIRCRAFT_RADIUS + 8, 2 * AIRCRAFT_RADIUS + 8)
        return aircraft_rect.collidepoint(pos)

def draw_taxiways(surface):
    rows = fetch_all("SELECT taxiway_name, start_x, start_y, end_x, end_y FROM taxiway WHERE airport_id = 3")
    if not rows:
        # Default Map 2 Artos geometry
        rows = [
            {"start_x": 100, "start_y": 600, "end_x": 1000, "end_y": 600},
            {"start_x": 800, "start_y": 200, "end_x": 800, "end_y": 600},
            {"start_x": 100, "start_y": 200, "end_x": 200, "end_y": 500},
            {"start_x": 800, "start_y": 400, "end_x": 170, "end_y": 400}
        ]
    for tw in rows:
        start_pos = (tw["start_x"], tw["start_y"])
        end_pos = (tw["end_x"], tw["end_y"])
        pygame.draw.line(surface, (0, 255, 255), start_pos, end_pos, TAXIWAY_WIDTH)

def draw_runways(surface):
    rows = fetch_all("SELECT runway_designation, start_x, start_y, end_x, end_y FROM runway WHERE airport_id = 3")
    if not rows:
        rows = [
            {"runway_designation": "09/27", "start_x": 800, "start_y": 600, "end_x": 100, "end_y": 200},
            {"runway_designation": "14/32", "start_x": 800, "start_y": 600, "end_x": 200, "end_y": 500}
        ]
    runway_labels = []
    for rw in rows:
        start_x, start_y = int(rw["start_x"]), int(rw["start_y"])
        end_x, end_y = int(rw["end_x"]), int(rw["end_y"])
        # Artos Map 2 uses pure white for runways
        pygame.draw.line(surface, (255, 255, 255), (start_x, start_y), (end_x, end_y), RUNWAY_WIDTH)
        angle = -math.degrees(math.atan2(end_y - start_y, end_x - start_x))
        runway_labels.append((f"Runway {rw['runway_designation']}", (start_x + end_x) // 2, (start_y + end_y) // 2, angle))
    return runway_labels

def draw_grid(surface):
    grid_color = (0, 70, 0)
    grid_spacing = 30
    for x in range(0, WINDOW_WIDTH, grid_spacing):
        pygame.draw.line(surface, grid_color, (x, 0), (x, WINDOW_HEIGHT), 1)
    for y in range(0, WINDOW_HEIGHT, grid_spacing):
        pygame.draw.line(surface, grid_color, (0, y), (WINDOW_WIDTH, y), 1)

def draw_waypoints(surface):
    rows = fetch_all("SELECT pos_x, pos_y FROM map_feature WHERE map_id = 2")
    if not rows:
        coords = [(800, 600), (800, 400), (800, 200), (170, 400), (200, 500), (100, 200), (995, 500), (995, 200)]
    else:
        coords = [(r["pos_x"], r["pos_y"]) for r in rows]
    for x, y in coords:
        pygame.draw.circle(surface, (255, 0, 0), (x, y), WAYPOINT_RADIUS)

def draw_labels(surface):
    label_positions = []

    def is_overlapping(new_rect):
        for existing_rect in label_positions:
            if new_rect.colliderect(existing_rect):
                return True
        return False

    def adjust_position(text_rect):
        if text_rect.right > WINDOW_WIDTH:
            text_rect.x -= text_rect.right - WINDOW_WIDTH
        if text_rect.bottom > WINDOW_HEIGHT:
            text_rect.y -= text_rect.bottom - WINDOW_HEIGHT
        if text_rect.left < 0:
            text_rect.x = 0
        if text_rect.top < 0:
            text_rect.y = 0

        while is_overlapping(text_rect):
            text_rect.y += 10
            if text_rect.bottom > WINDOW_HEIGHT:
                text_rect.y = 0
                text_rect.x += 20
                if text_rect.right > WINDOW_WIDTH:
                    text_rect.x = 0
        label_positions.append(text_rect)
        return text_rect

    # Waypoint labels
    rows = fetch_all("SELECT feature_name, pos_x, pos_y FROM map_feature WHERE map_id = 2")
    if rows:
        for wp in rows:
            text_surf = small_font.render(wp["feature_name"], True, (255, 250, 15))
            text_rect = text_surf.get_rect(center=(wp["pos_x"], wp["pos_y"] - WAYPOINT_RADIUS - 10))
            adjusted = adjust_position(text_rect)
            surface.blit(text_surf, adjusted)

    # Taxiway labels
    tw_rows = fetch_all("SELECT taxiway_name, start_x, start_y, end_x, end_y FROM taxiway WHERE airport_id = 3")
    if tw_rows:
        for tw in tw_rows:
            mid_x = (tw["start_x"] + tw["end_x"]) // 2
            mid_y = (tw["start_y"] + tw["end_y"]) // 2
            text_surf = small_font.render(tw["taxiway_name"], True, (0, 255, 255))
            text_rect = text_surf.get_rect(center=(mid_x, mid_y))
            adjusted = adjust_position(text_rect)
            surface.blit(text_surf, adjusted)

def draw_runwaylabels(surface, labels):
    for text, x, y, angle in labels:
        text_surface = label_font.render(text, True, (2, 0, 0))
        text_surface_rotated = pygame.transform.rotate(text_surface, angle)
        text_rect = text_surface_rotated.get_rect(center=(x, y))
        surface.blit(text_surface_rotated, text_rect)

def collision_avoidance():
    for i in range(len(aircraft_list)):
        for j in range(i + 1, len(aircraft_list)):
            if aircraft_list[i].check_collision(aircraft_list[j]):
                aircraft_list[i].stop_for_collision()

def get_aircraft_info():
    aircraft_info = []
    # 1. User entered flights for map 2 (legacy ARTOS schema only)
    try:
        rows = fetch_all("SELECT aircraft_name, weight, aircraft_time FROM aircraft WHERE map_id = 2")
        if rows:
            for r in rows:
                name = r["aircraft_name"]
                weight = r["weight"]
                d_time = r["aircraft_time"]
                aircraft_info.append((name, weight, d_time))
    except Exception:
        pass  # AURORA schema does not have these legacy columns — skip gracefully

    # 2. Operations for Mumbai BOM (Airport ID 3)
    db_ops = fetch_all("""
        SELECT f.flight_number, act.max_takeoff_weight, fo.scheduled_datetime
        FROM flight_operation fo
        JOIN flight f ON fo.flight_id = f.flight_id
        JOIN aircraft ac ON f.aircraft_id = ac.aircraft_id
        JOIN aircraft_type act ON ac.type_id = act.type_id
        WHERE fo.airport_id = 3
        ORDER BY fo.scheduled_datetime ASC
        LIMIT 6
    """)
    for op in db_ops:
        name = op["flight_number"]
        weight = int(op["max_takeoff_weight"] / 1000)
        d_time = str(op["scheduled_datetime"]).split()[-1]
        aircraft_info.append((name, weight, d_time))

    if not aircraft_info:
        aircraft_info = [
            ("AI-101", 170, "08:15:00"),
            ("AI-102", 185, "09:30:00"),
            ("EK-500", 350, "01:45:00")
        ]
    return aircraft_info

def setup_simulation():
    ac_list = []
    info_list = get_aircraft_info()
    ltemp = [9, 10]

    for idx, info in enumerate(info_list):
        spawn_x = random.randrange(99, 750, 25)
        spawn_y = 600
        ac = Aircraft(info[0], (spawn_x, spawn_y), info[1], info[2])
        if ltemp:
            rw_choice = ltemp.pop(0)
        else:
            rw_choice = random.choice([9, 10])
        ac.move_to_end_of_runway(rw_choice)
        ac_list.append(ac)

    ac_list.sort(key=lambda x: str(x.depart_time))
    return ac_list

def display_messages(surface):
    message_box_height = 100
    message_box_surface = pygame.Surface((MESSAGE_BOX_WIDTH, message_box_height), pygame.SRCALPHA)
    message_box_surface.fill((200, 200, 200, 140))

    y_offset = 10
    for message in messages[-MAX_MESSAGES:]:
        flight_name, _, message_text = message.partition(":")
        flight_surface = small_font.render(flight_name + ":", True, (255, 0, 0))
        flight_rect = flight_surface.get_rect(topleft=(40, y_offset))
        message_box_surface.blit(flight_surface, flight_rect)

        text_surface = small_font.render(message_text, True, (0, 0, 0))
        text_rect = text_surface.get_rect(topleft=(flight_rect.right + 5, y_offset))
        message_box_surface.blit(text_surface, text_rect)
        y_offset += 28

    surface.blit(message_box_surface, (0, 0))

def draw_start_button(surface):
    surface.fill((255, 255, 255))

    # Title & Airport Banner
    t1 = header_font.render("Chhatrapati Shivaji Maharaj (BOM) Radar Scope", True, (20, 20, 20))
    t2 = font.render("Mumbai Coastal Airfield Simulation • Map 2", True, (80, 80, 80))
    surface.blit(t1, t1.get_rect(center=(500, 220)))
    surface.blit(t2, t2.get_rect(center=(500, 260)))

    # Start button
    start_button_rect = pygame.Rect(400, 420, 200, 55)
    mouse_pos = pygame.mouse.get_pos()
    btn_color = (200, 225, 255) if start_button_rect.collidepoint(mouse_pos) else (25, 141, 200)
    pygame.draw.rect(surface, btn_color, start_button_rect, border_radius=6)
    pygame.draw.rect(surface, (0, 0, 0), start_button_rect, 2, border_radius=6)

    btn_txt = header_font.render("Start Simulation", True, (255, 255, 255))
    surface.blit(btn_txt, btn_txt.get_rect(center=start_button_rect.center))

def draw_compass(surface, heading):
    # Map 2 compass center is (90, 450)
    compass_center = (90, 450)
    compass_radius = 50
    pygame.draw.circle(surface, (255, 255, 255), compass_center, compass_radius, 1)

    directions = ['W', 'N', 'E', 'S']
    angle_offset = [0, 90, 180, 270]
    for direction, angle in zip(directions, angle_offset):
        angle_rad = math.radians(angle)
        x = compass_center[0] + (compass_radius - 12) * math.cos(angle_rad)
        y = compass_center[1] - (compass_radius - 12) * math.sin(angle_rad)
        text_surface = font.render(direction, True, (255, 255, 255))
        surface.blit(text_surface, (x - 8, y - 8))

    compass_heading_length = compass_radius - 8
    end_x = compass_center[0] + compass_heading_length * math.cos(heading)
    end_y = compass_center[1] + compass_heading_length * math.sin(heading)
    pygame.draw.line(surface, (255, 255, 0), compass_center, (end_x, end_y), 2)

def display_flight_details(surface, current_position, current_heading, current_speed, message_list, waypoints, depart_time, weight):
    box_x, box_y, box_width, box_height = 150, 600, 360, 120
    pygame.draw.rect(surface, (0, 0, 0), (box_x, box_y, box_width, box_height), 0)
    pygame.draw.rect(surface, (255, 255, 255), (box_x, box_y, box_width, box_height), 2)

    deg_heading = int(math.degrees(current_heading)) % 360
    details = [
        f"Position: ({int(current_position[0])}, {int(current_position[1])})",
        f"Heading: {deg_heading}°",
        f"Speed: {current_speed} knots",
        f"Depart Time: {depart_time}",
        f"Weight: {weight} tons"
    ]
    for i, detail in enumerate(details):
        text_surface = font.render(detail, True, (255, 200, 255))
        surface.blit(text_surface, (box_x + 10, box_y + 8 + i * 21))

    # Message Log Box
    box2_x, box2_y = 680, 400
    box2_width, box2_height = 300, 350
    pygame.draw.rect(surface, (0, 0, 0), (box2_x, box2_y, box2_width, box2_height), 0)
    pygame.draw.rect(surface, (255, 255, 255), (box2_x, box2_y, box2_width, box2_height), 2)

    log_heading_surface = font.render("Message Log", True, (255, 200, 255))
    surface.blit(log_heading_surface, (box2_x + 10, box2_y + 8))
    for i, message in enumerate(message_list[-8:]):
        message_surface = small_font.render(message, True, (255, 220, 255))
        surface.blit(message_surface, (box2_x + 10, box2_y + 35 + i * 22))

def show_aircraft_pathway(aircraft):
    running = True
    pathway_screen = pygame.display.get_surface()

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                running = False

        pathway_screen.fill((0, 0, 0))
        draw_grid(pathway_screen)

        runway_labels = draw_runways(pathway_screen)
        draw_taxiways(pathway_screen)
        draw_waypoints(pathway_screen)
        draw_runwaylabels(pathway_screen, runway_labels)
        draw_labels(pathway_screen)

        # Highlight pathway line connecting waypoints
        wp_list = aircraft.waypoints2
        for i in range(len(wp_list) - 1):
            start_wp = wp_list[i]
            end_wp = wp_list[i + 1]
            pygame.draw.line(pathway_screen, (255, 255, 0), start_wp, end_wp, 12)
            pygame.draw.line(pathway_screen, (0, 0, 0), start_wp, end_wp, 3)

        # Waypoint circles
        for wp in wp_list:
            pygame.draw.circle(pathway_screen, (0, 255, 0), wp, 8)

        # Current position and heading
        pos = (int(aircraft.position[0]), int(aircraft.position[1]))
        pygame.draw.circle(pathway_screen, (255, 0, 0), pos, 7)
        heading_length = 50
        end_x = pos[0] + heading_length * math.cos(aircraft.heading)
        end_y = pos[1] + heading_length * math.sin(aircraft.heading)
        pygame.draw.line(pathway_screen, (255, 150, 150), pos, (int(end_x), int(end_y)), 2)

        draw_compass(pathway_screen, aircraft.heading)
        display_flight_details(
            pathway_screen, aircraft.position, aircraft.heading, speed,
            aircraft.message_list, aircraft.waypoints2, aircraft.depart_time, aircraft.weight
        )

        esc_hint = small_font.render("Click or press ESC to return to Radar", True, (200, 200, 200))
        pathway_screen.blit(esc_hint, (WINDOW_WIDTH // 2 - esc_hint.get_width() // 2, 20))

        pygame.display.flip()
        clock.tick(30)

def main():
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("ARTOS / AURORA — Mumbai Chhatrapati Shivaji (BOM) Sector Radar Scope")

    global aircraft_list
    simulation = "waiting_for_click"

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if simulation == "waiting_for_click":
                    start_btn_rect = pygame.Rect(400, 420, 200, 55)
                    if start_btn_rect.collidepoint(event.pos):
                        print("Start button clicked. Launching BOM radar simulation...")
                        aircraft_list = setup_simulation()
                        simulation = "running"
                elif simulation == "running":
                    for aircraft in aircraft_list:
                        if aircraft.is_clicked(event.pos):
                            show_aircraft_pathway(aircraft)

        if simulation == "waiting_for_click":
            draw_start_button(screen)
        elif simulation == "running":
            collision_avoidance()
            screen.fill((0, 0, 0))
            draw_grid(screen)

            runway_labels = draw_runways(screen)
            draw_taxiways(screen)
            draw_waypoints(screen)
            draw_runwaylabels(screen, runway_labels)
            draw_labels(screen)

            for aircraft in aircraft_list:
                aircraft.move_to_next_waypoint()
                aircraft.update_stop_time()
                aircraft.draw(screen)

            display_messages(screen)

            # Airfield header badge
            badge = small_font.render("AIRFIELD: Mumbai (BOM) | Map 2 Scope", True, (150, 255, 150))
            screen.blit(badge, (WINDOW_WIDTH - badge.get_width() - 15, 15))

        pygame.display.flip()
        clock.tick(30)

if __name__ == "__main__":
    main()
