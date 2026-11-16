"""
ARTOS / AURORA — Flight Details & Manual Runway Assignment Input Page
Preserves the authentic Artos visual styling, fonts, layout, and animations
while integrating AURORA's relational DBMS validation engine and Dallas (DFW) / Mumbai (BOM) maps.
"""

from datetime import datetime
import pygame
import sys
import subprocess
import os
import math

# Import AURORA database and validation engine
from db import execute, fetch_all, fetch_one
from validator import validate_manual_input

# Initialize Pygame
pygame.init()

# Set up the screen (Exact Artos 1000x1000)
screen_width = 1000
screen_height = 1000
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Input Flight Details & Manual Runway Assignment")

# Helper to create fallback surfaces if disk images are not present
def create_plane_surface():
    surf = pygame.Surface((80, 40), pygame.SRCALPHA)
    # Draw sleek white/cyan aircraft icon
    pygame.draw.polygon(surf, (240, 240, 240), [(75, 20), (35, 8), (40, 18), (10, 18), (5, 10), (0, 10), (5, 20), (0, 30), (5, 30), (10, 22), (40, 22), (35, 32)])
    pygame.draw.polygon(surf, (0, 200, 255), [(75, 20), (45, 18), (45, 22)])
    return surf

def create_map_thumbnail(map_id):
    surf = pygame.Surface((400, 300))
    surf.fill((10, 15, 10))
    # Green grid lines
    for x in range(0, 400, 20):
        pygame.draw.line(surf, (0, 50, 0), (x, 0), (x, 300), 1)
    for y in range(0, 300, 20):
        pygame.draw.line(surf, (0, 50, 0), (0, y), (400, y), 1)

    t_font = pygame.font.SysFont('Lucida Bright', 20, bold=True)
    if map_id == 1:
        # DFW Map preview (scale down 1000x1000 -> 400x300)
        # Runway 1: (125, 500) -> (600, 0)
        # Runway 2: (125, 200) -> (1000, 300)
        # Runway 3: (125, 120) -> (1000, 0)
        p = lambda pt: (int(pt[0] * 0.4), int(pt[1] * 0.3))
        pygame.draw.rect(surf, (80, 80, 80), (int(50 * 0.4), 0, int(100 * 0.4), 300))
        pygame.draw.line(surf, (25, 141, 200), p((125, 500)), p((600, 0)), 8)
        pygame.draw.line(surf, (25, 141, 200), p((125, 200)), p((1000, 300)), 8)
        pygame.draw.line(surf, (25, 141, 200), p((125, 120)), p((1000, 0)), 8)
        lbl = t_font.render("Dallas/Fort Worth (DFW)", True, (255, 255, 255))
        surf.blit(lbl, (20, 260))
    else:
        # BOM Map preview
        p = lambda pt: (int(pt[0] * 0.4), int(pt[1] * 0.3))
        pygame.draw.line(surf, (255, 255, 255), p((800, 600)), p((100, 200)), 8)
        pygame.draw.line(surf, (255, 255, 255), p((800, 600)), p((200, 500)), 8)
        lbl = t_font.render("Mumbai Chhatrapati (BOM)", True, (255, 255, 255))
        surf.blit(lbl, (20, 260))
    return surf

# Load background or fallback
try:
    background_image = pygame.image.load('input.jpg')
    background_image = pygame.transform.scale(background_image, (screen_width, screen_height))
except Exception:
    background_image = pygame.Surface((screen_width, screen_height))
    background_image.fill((100, 100, 100))

# Fonts (Exact Artos Lucida Bright font)
font_name = 'Lucida Bright'
font_size = 36
font_1 = pygame.font.SysFont(font_name, font_size)
font_small = pygame.font.SysFont(font_name, 22)
font_feedback = pygame.font.SysFont(font_name, 24, bold=True)
text_color = (0, 0, 0)

# Colors
input_box_color = (255, 255, 255)
focused_box_color = (173, 216, 230)  # Light blue for focused box
button_color = (255, 255, 255)
button_hover_color = (200, 200, 200)
cursor_color = (0, 0, 0)

# Input Rectangles:
# Flight Name, Flight Time, Aircraft Weight, Manual Runway Vector
rects = [
    pygame.Rect(520, 440, 450, 48),  # 0: Flight Name
    pygame.Rect(520, 530, 450, 48),  # 1: Time (HH:MM:SS)
    pygame.Rect(520, 620, 450, 48),  # 2: Weight in tons
    pygame.Rect(520, 710, 450, 48),  # 3: Manual Runway Vector
]

button_rect = pygame.Rect(520, 100, 250, 50)
next_button_rect = pygame.Rect(800, 100, 200, 50)
start_button_rect = pygame.Rect(400, 480, 200, 80)

# Cursor for typing
cursor_visible = True
cursor_timer = 0
cursor_blink_speed = 500  # milliseconds
last_time = pygame.time.get_ticks()

def insert_data(selected_map, aircraft_name, aircraft_time, aircraft_weight, runway_vector):
    """
    Validates manual input and runway assignment against AURORA DBMS rules.
    If valid, inserts record into aurora_db database and returns None.
    If invalid, returns the exact validation failure explanation.
    """
    if not aircraft_name.strip():
        return "Flight name cannot be empty."

    # Validate time format
    try:
        aircraft_time_obj = datetime.strptime(aircraft_time.strip(), "%H:%M:%S").time()
    except ValueError:
        return "Invalid time format. Use HH:MM:SS (e.g. 08:30:00)."

    # Validate aircraft weight
    try:
        aircraft_weight_int = int(aircraft_weight)
        if aircraft_weight_int <= 0:
            return "Aircraft weight must be a positive integer."
    except ValueError:
        return "Aircraft weight must be an integer."

    # Validate manual runway assignment using AURORA Validation Engine
    # Map 1 is DFW (airport_id = 1), Map 2 is BOM (airport_id = 3)
    airport_id = 1 if selected_map == 1 else 3
    val_res = validate_manual_input(
        airport_id=airport_id,
        aircraft_name=aircraft_name.strip(),
        time_str=aircraft_time.strip(),
        weight_tons=aircraft_weight_int,
        runway_vector=runway_vector.strip()
    )

    if not val_res.is_valid:
        # Return exact validation failure reason to display in red
        return val_res.reason

    # Insert into database (AURORA relational schema + legacy aircraft table compatibility)
    try:
        # 1. Ensure flight record exists
        flight_num = aircraft_name.strip().upper()
        row = fetch_one("SELECT flight_id FROM flight WHERE flight_number = %s", (flight_num,))
        if row:
            flight_id = row["flight_id"]
        else:
            # Create a demonstration flight entry
            dest_airport_id = 3 if airport_id == 1 else 1
            flight_id = execute(
                """INSERT INTO flight (flight_number, airline_id, aircraft_id, origin_airport_id, destination_airport_id, flight_type, flight_status, service_date)
                   VALUES (%s, 1, 1, %s, %s, 'PASSENGER', 'SCHEDULED', CURRENT_DATE)""",
                (flight_num, airport_id, dest_airport_id)
            )

        # 2. Insert flight operation
        sched_dt = f"2026-10-27 {aircraft_time.strip()}"
        op_id = execute(
            """INSERT INTO flight_operation (flight_id, airport_id, operation_type, scheduled_datetime, operation_status, notes)
               VALUES (%s, %s, 'TAKEOFF', %s, 'SCHEDULED', 'Manual user assignment in Artos UI')""",
            (flight_id, airport_id, sched_dt)
        )

        # 3. Insert confirmed runway assignment
        direction_id = val_res.details.get("direction_id", 1)
        execute(
            """INSERT INTO runway_assignment (operation_id, direction_id, assignment_status, assigned_by, remarks)
               VALUES (%s, %s, 'CONFIRMED', 'ARTOS_OPERATOR', %s)""",
            (op_id, direction_id, f"Manually assigned vector {runway_vector.strip()} verified by AURORA")
        )

        # 4. Insert into legacy aircraft table if present (ensures full backward compatibility)
        try:
            execute(
                """INSERT INTO aircraft (map_id, aircraft_name, aircraft_time, weight)
                   VALUES (%s, %s, %s, %s)""",
                (selected_map, flight_num, aircraft_time_obj.strftime("%H:%M:%S"), aircraft_weight_int)
            )
        except Exception:
            pass

        return None # None indicates success!

    except Exception as e:
        return f"Database error: {e}"

def fade_out(duration=600):
    fade_surface = pygame.Surface((screen_width, screen_height))
    fade_surface.fill((0, 0, 0))
    for alpha in range(0, 255, 10):
        fade_surface.set_alpha(alpha)
        screen.blit(fade_surface, (0, 0))
        pygame.display.flip()
        pygame.time.delay(duration // 40)

def fade_in(duration=400):
    fade_surface = pygame.Surface((screen_width, screen_height))
    fade_surface.fill((0, 0, 0))
    for alpha in range(255, -1, -10):
        fade_surface.set_alpha(alpha)
        screen.blit(fade_surface, (0, 0))
        pygame.display.flip()
        pygame.time.delay(duration // 40)

def start_screen():
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if start_button_rect.collidepoint(event.pos):
                    fade_out()
                    return

        screen.fill((30, 30, 30))
        # Exact Artos start screen titles
        screen.blit(font_1.render("Class 12 Computer Project", True, (255, 255, 255)), (350, 230))
        screen.blit(font_1.render("By Ishita and Sanjana, 12'B'", True, (255, 255, 255)), (350, 330))

        # AURORA system subtitle
        sub = font_small.render("AURORA — Aircraft & Unified Runway Operations Records Archive", True, (180, 220, 255))
        screen.blit(sub, sub.get_rect(center=(screen_width // 2, 410)))

        is_hover = start_button_rect.collidepoint(pygame.mouse.get_pos())
        s_btn_color = button_hover_color if is_hover else button_color
        pygame.draw.rect(screen, s_btn_color, start_button_rect)
        pygame.draw.rect(screen, (0, 0, 0), start_button_rect, 2)
        start_text = font_1.render("Start", True, text_color)
        start_text_rect = start_text.get_rect(center=start_button_rect.center)
        screen.blit(start_text, start_text_rect)

        pygame.display.flip()

def move_airplane():
    # Try loading airplane image, fallback to crisp procedural aircraft
    try:
        airplane_image = pygame.image.load('planeicon.png')
    except Exception:
        airplane_image = create_plane_surface()

    airplane_rect = airplane_image.get_rect(topleft=(50, 250))
    speed = 12

    while airplane_rect.x < screen_width:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        screen.fill((0, 0, 0))
        screen.blit(airplane_image, airplane_rect)
        pygame.display.flip()
        airplane_rect.x += speed
        pygame.time.delay(20)

def map_selection_screen():
    fade_in()

    # Try loading map preview images, fallback to generated airfield scopes
    try:
        map1im = pygame.image.load('map1.png')
        map1im = pygame.transform.scale(map1im, (400, 300))
    except Exception:
        map1im = create_map_thumbnail(1)

    try:
        map2im = pygame.image.load('map2.png')
        map2im = pygame.transform.scale(map2im, (400, 300))
    except Exception:
        map2im = create_map_thumbnail(2)

    map1_button_rect = pygame.Rect(190, 420, 300, 80)
    map2_button_rect = pygame.Rect(510, 420, 300, 80)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if map1_button_rect.collidepoint(event.pos):
                    fade_out()
                    return 1  # Dallas/Fort Worth (DFW)
                elif map2_button_rect.collidepoint(event.pos):
                    fade_out()
                    return 2  # Mumbai (BOM)

        screen.fill((50, 50, 50))

        # Draw map previews
        screen.blit(map1im, (80, 80))
        screen.blit(map2im, (510, 80))

        mouse_pos = pygame.mouse.get_pos()

        # Map 1 Button (DFW)
        m1_col = button_hover_color if map1_button_rect.collidepoint(mouse_pos) else button_color
        pygame.draw.rect(screen, m1_col, map1_button_rect)
        pygame.draw.rect(screen, (0, 0, 0), map1_button_rect, 2)
        map1_text = font_1.render("Map 1 (DFW)", True, text_color)
        screen.blit(map1_text, map1_text.get_rect(center=map1_button_rect.center))

        # Map 2 Button (BOM)
        m2_col = button_hover_color if map2_button_rect.collidepoint(mouse_pos) else button_color
        pygame.draw.rect(screen, m2_col, map2_button_rect)
        pygame.draw.rect(screen, (0, 0, 0), map2_button_rect, 2)
        map2_text = font_1.render("Map 2 (BOM)", True, text_color)
        screen.blit(map2_text, map2_text.get_rect(center=map2_button_rect.center))

        # Subtitle
        sub1 = font_small.render("Dallas/Fort Worth International", True, (200, 200, 200))
        sub2 = font_small.render("Mumbai Chhatrapati Shivaji", True, (200, 200, 200))
        screen.blit(sub1, sub1.get_rect(center=(map1_button_rect.centerx, 520)))
        screen.blit(sub2, sub2.get_rect(center=(map2_button_rect.centerx, 520)))

        pygame.display.flip()

def main(selected_map):
    # 4 input fields: Flight Name, Time, Weight, Manual Runway Vector
    input_texts = ["", "", "", ""]
    focused_rect = None
    submitted = False
    error_message = None

    global cursor_visible, cursor_timer, last_time

    fade_in()

    # Predefined vector pills for quick-click selection
    if selected_map == 1:
        vectors = ["17L", "35R", "17C", "35C", "18R", "36L"]
        airport_desc = "Map: 1 (Dallas/Fort Worth - DFW)"
    else:
        vectors = ["09", "27", "14", "32"]
        airport_desc = "Map: 2 (Mumbai - BOM)"

    vector_pills = []
    pill_w = 65
    pill_h = 32
    start_px = 520
    for i, v in enumerate(vectors):
        r = pygame.Rect(start_px + i * (pill_w + 8), 768, pill_w, pill_h)
        vector_pills.append((r, v))

    while True:
        current_time = pygame.time.get_ticks()
        time_delta = current_time - last_time

        if time_delta > cursor_blink_speed:
            cursor_visible = not cursor_visible
            last_time = current_time

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Check vector quick-selection pills
                pill_clicked = False
                for pill_rect, v_name in vector_pills:
                    if pill_rect.collidepoint(event.pos):
                        input_texts[3] = v_name
                        focused_rect = 3
                        pill_clicked = True
                        break

                if pill_clicked:
                    continue

                # Submit or Next Input button
                if next_button_rect.collidepoint(event.pos) or button_rect.collidepoint(event.pos):
                    error_message = insert_data(selected_map, *input_texts)
                    if error_message is None:
                        submitted = True
                        print("Data entered successfully. Manual Runway Assignment verified by AURORA!")
                        if next_button_rect.collidepoint(event.pos):
                            # Reset for next entry
                            input_texts = ["", "", "", ""]
                        else:
                            # Submit clicked -> Transition to radar scope
                            fade_out(400)
                            base_dir = os.path.dirname(os.path.abspath(__file__))
                            if selected_map == 1:
                                script_path = os.path.join(base_dir, "artos_map1.py")
                            else:
                                script_path = os.path.join(base_dir, "artos_map2.py")

                            print(f"Running radar simulation script: {script_path}")
                            subprocess.Popen([sys.executable, script_path, str(selected_map)])
                            pygame.quit()
                            sys.exit()
                    else:
                        print(f"Validation error: {error_message}")

                else:
                    for i, rect in enumerate(rects):
                        if rect.collidepoint(event.pos):
                            focused_rect = i
                            break
                    else:
                        focused_rect = None

            elif event.type == pygame.KEYDOWN:
                if focused_rect is not None:
                    if event.key == pygame.K_BACKSPACE:
                        input_texts[focused_rect] = input_texts[focused_rect][:-1]
                    elif event.key == pygame.K_TAB:
                        focused_rect = (focused_rect + 1) % len(rects)
                    elif event.key != pygame.K_RETURN:
                        input_texts[focused_rect] += event.unicode

        # Render background
        screen.blit(background_image, (0, 0))

        # Top Buttons with hover effect
        mouse_pos = pygame.mouse.get_pos()
        sub_col = button_hover_color if button_rect.collidepoint(mouse_pos) else button_color
        nxt_col = button_hover_color if next_button_rect.collidepoint(mouse_pos) else button_color

        pygame.draw.rect(screen, sub_col, button_rect)
        pygame.draw.rect(screen, (0, 0, 0), button_rect, 2)
        button_text = font_1.render("Submit", True, text_color)
        screen.blit(button_text, button_text.get_rect(center=button_rect.center))

        pygame.draw.rect(screen, nxt_col, next_button_rect)
        pygame.draw.rect(screen, (0, 0, 0), next_button_rect, 2)
        reload_text = font_1.render("Next Input", True, text_color)
        screen.blit(reload_text, reload_text.get_rect(center=next_button_rect.center))

        # Airport & Map Details Label
        screen.blit(font_1.render(airport_desc, True, (255, 255, 255)), (20, 350))

        # Input field labels (Authentic Artos positions)
        screen.blit(font_1.render("Enter name of flight:", True, (255, 255, 255)), (20, 440))
        screen.blit(font_1.render("Enter time (HH:MM:SS):", True, (255, 255, 255)), (20, 530))
        screen.blit(font_1.render("Enter weight in tons:", True, (255, 255, 255)), (20, 620))
        screen.blit(font_1.render("Manual Runway Vector:", True, (255, 255, 255)), (20, 710))

        # Render text input boxes
        for i, (rect, text) in enumerate(zip(rects, input_texts)):
            box_color = focused_box_color if focused_rect == i else input_box_color
            pygame.draw.rect(screen, box_color, rect)
            pygame.draw.rect(screen, (0, 0, 0), rect, 2)

            text_surface = font_1.render(text, True, text_color)
            screen.blit(text_surface, (rect.x + 8, rect.y + 4))

            # Cursor
            if focused_rect == i and cursor_visible:
                cursor_x_pos = rect.x + 8 + text_surface.get_width() + 2
                pygame.draw.line(screen, cursor_color, (cursor_x_pos, rect.y + 6), (cursor_x_pos, rect.y + 40), 2)

        # Draw quick-select runway pills
        for pill_rect, v_name in vector_pills:
            is_active = (input_texts[3].strip().upper() == v_name)
            p_col = (100, 200, 255) if is_active else (230, 230, 230)
            if pill_rect.collidepoint(mouse_pos) and not is_active:
                p_col = (190, 225, 255)
            pygame.draw.rect(screen, p_col, pill_rect, border_radius=4)
            pygame.draw.rect(screen, (0, 0, 0), pill_rect, 1, border_radius=4)
            p_txt = font_small.render(v_name, True, (0, 0, 0))
            screen.blit(p_txt, p_txt.get_rect(center=pill_rect.center))

        # Status & Validation Feedback Message Box
        if submitted:
            success_surface = font_feedback.render("Submitted Successfully — Runway Vector Confirmed!", True, (0, 255, 0))
            screen.blit(success_surface, (screen_width // 2 - success_surface.get_width() // 2, 230))
        elif error_message:
            # Wrap or render error message cleanly
            err_color = (255, 50, 50)
            if len(error_message) > 65:
                line1 = error_message[:65]
                line2 = error_message[65:]
                e1 = font_small.render(line1, True, err_color)
                e2 = font_small.render(line2, True, err_color)
                screen.blit(e1, (screen_width // 2 - e1.get_width() // 2, 220))
                screen.blit(e2, (screen_width // 2 - e2.get_width() // 2, 250))
            else:
                err_surface = font_feedback.render(error_message, True, err_color)
                screen.blit(err_surface, (screen_width // 2 - err_surface.get_width() // 2, 230))

        pygame.display.flip()

if __name__ == "__main__":
    start_screen()
    move_airplane()
    selected_map = map_selection_screen()
    print(f"Map {selected_map} selected! Running input screen...")
    main(selected_map)
