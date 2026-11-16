"""
AURORA - Pygame Reusable UI Components
Theme: Aviation Radar & Flight Control (Dark Navy, Radar Green, Cyan, Amber)
Preserves and elevates the visual language of ARTOS.
"""

import pygame
import math

# Color Palette
COLOR_BG = (10, 15, 20)             # Deep cockpit night black
COLOR_PANEL = (18, 25, 35)          # Tactical dark panel
COLOR_GRID = (0, 70, 0)             # Artos radar green grid line
COLOR_ACCENT_CYAN = (0, 255, 255)   # Artos taxiway cyan
COLOR_RUNWAY_BLUE = (25, 141, 200)  # Artos runway vector blue
COLOR_TEXT_WHITE = (240, 245, 250)
COLOR_TEXT_MUTED = (140, 155, 175)
COLOR_TEXT_YELLOW = (255, 250, 15)  # Artos waypoint yellow
COLOR_SUCCESS_GREEN = (40, 200, 80)
COLOR_ALERT_RED = (240, 60, 60)
COLOR_BTN_NORMAL = (30, 45, 65)
COLOR_BTN_HOVER = (45, 70, 100)
COLOR_BTN_ACTIVE = (0, 160, 220)

class Button:
    def __init__(self, rect, text, font, on_click=None, bg_color=COLOR_BTN_NORMAL, active=False):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.font = font
        self.on_click = on_click
        self.bg_color = bg_color
        self.active = active
        self.hovered = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                if self.on_click:
                    self.on_click()
                return True
        return False

    def draw(self, surface):
        if self.active:
            color = COLOR_BTN_ACTIVE
            border_color = COLOR_ACCENT_CYAN
        elif self.hovered:
            color = COLOR_BTN_HOVER
            border_color = (100, 180, 255)
        else:
            color = self.bg_color
            border_color = (60, 80, 110)

        pygame.draw.rect(surface, color, self.rect, border_radius=4)
        pygame.draw.rect(surface, border_color, self.rect, width=1, border_radius=4)

        text_surf = self.font.render(self.text, True, COLOR_TEXT_WHITE if not self.active else (0, 0, 0))
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

class StatCard:
    def __init__(self, rect, label, value, subtext="", color=COLOR_ACCENT_CYAN):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.value = str(value)
        self.subtext = subtext
        self.color = color

    def draw(self, surface, font_label, font_val, font_sub):
        pygame.draw.rect(surface, (17, 25, 34), self.rect)
        pygame.draw.rect(surface, (48, 64, 79), self.rect, width=1)
        pygame.draw.line(surface, self.color, (self.rect.x + 1, self.rect.y + 1),
                         (self.rect.right - 2, self.rect.y + 1), 2)

        lbl_surf = font_label.render(self.label.upper(), True, COLOR_TEXT_MUTED)
        surface.blit(lbl_surf, (self.rect.x + 12, self.rect.y + 13))

        val_surf = font_val.render(self.value, True, COLOR_TEXT_WHITE)
        surface.blit(val_surf, (self.rect.x + 12, self.rect.y + 34))

        if self.subtext:
            sub_surf = font_sub.render(self.subtext, True, self.color)
            surface.blit(sub_surf, (self.rect.x + 12, self.rect.bottom - sub_surf.get_height() - 10))

class DataTable:
    def __init__(self, rect, columns, col_widths, font, row_height=28):
        self.rect = pygame.Rect(rect)
        self.columns = columns
        self.col_widths = col_widths
        self.font = font
        self.row_height = row_height
        self.rows = []
        self.selected_index = -1
        self.scroll_offset = 0

    def set_data(self, rows):
        self.rows = rows
        self.selected_index = -1
        self.scroll_offset = 0

    def get_selected_row(self):
        if 0 <= self.selected_index < len(self.rows):
            return self.rows[self.selected_index]
        return None

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.rect.collidepoint(event.pos):
                y_click = event.pos[1] - (self.rect.y + self.row_height)
                if y_click >= 0:
                    clicked_idx = self.scroll_offset + (y_click // self.row_height)
                    if 0 <= clicked_idx < len(self.rows):
                        self.selected_index = clicked_idx
                        return True
            elif event.button == 4: # Scroll Up
                self.scroll_offset = max(0, self.scroll_offset - 1)
            elif event.button == 5: # Scroll Down
                max_visible = (self.rect.height - self.row_height) // self.row_height
                if len(self.rows) > max_visible:
                    self.scroll_offset = min(len(self.rows) - max_visible, self.scroll_offset + 1)
        return False

    def draw(self, surface):
        # Background
        pygame.draw.rect(surface, COLOR_PANEL, self.rect, border_radius=6)
        pygame.draw.rect(surface, (45, 60, 80), self.rect, width=1, border_radius=6)

        # Header background
        header_rect = pygame.Rect(self.rect.x, self.rect.y, self.rect.width, self.row_height)
        pygame.draw.rect(surface, (25, 38, 55), header_rect, border_top_left_radius=6, border_top_right_radius=6)
        pygame.draw.line(surface, COLOR_ACCENT_CYAN, (self.rect.x, self.rect.y + self.row_height), 
                         (self.rect.right, self.rect.y + self.row_height), 1)

        # Header titles
        curr_x = self.rect.x + 8
        for col_name, width in zip(self.columns, self.col_widths):
            h_surf = self.font.render(col_name, True, COLOR_ACCENT_CYAN)
            surface.blit(h_surf, (curr_x, self.rect.y + 6))
            curr_x += width

        # Rows
        max_visible = (self.rect.height - self.row_height) // self.row_height
        visible_rows = self.rows[self.scroll_offset : self.scroll_offset + max_visible]

        for i, row in enumerate(visible_rows):
            actual_idx = self.scroll_offset + i
            y_pos = self.rect.y + self.row_height + (i * self.row_height)
            row_rect = pygame.Rect(self.rect.x + 2, y_pos, self.rect.width - 4, self.row_height - 2)

            if actual_idx == self.selected_index:
                pygame.draw.rect(surface, (30, 80, 120), row_rect, border_radius=3)
                pygame.draw.rect(surface, COLOR_ACCENT_CYAN, row_rect, width=1, border_radius=3)
            elif i % 2 == 1:
                pygame.draw.rect(surface, (14, 20, 28), row_rect)

            curr_x = self.rect.x + 8
            for val, width in zip(row, self.col_widths):
                val_str = str(val) if val is not None else "-"
                # Shorten if too long
                if len(val_str) > 28:
                    val_str = val_str[:25] + "..."
                txt_color = COLOR_TEXT_WHITE if actual_idx == self.selected_index else (210, 220, 230)
                txt_surf = self.font.render(val_str, True, txt_color)
                surface.blit(txt_surf, (curr_x, y_pos + 5))
                curr_x += width

class CompassHUD:
    """Adapted and modernized from Artos draw_compass function."""
    def __init__(self, center=(900, 100), radius=50):
        self.center = center
        self.radius = radius

    def draw(self, surface, heading, font):
        cx, cy = self.center
        # Draw outer circle
        pygame.draw.circle(surface, (15, 25, 35), (cx, cy), self.radius)
        pygame.draw.circle(surface, COLOR_TEXT_WHITE, (cx, cy), self.radius, 1)

        # Cardinal labels
        dirs = [('N', 0), ('E', 90), ('S', 180), ('W', 270)]
        for lbl, deg in dirs:
            rad = math.radians(deg - 90)
            lx = cx + (self.radius - 12) * math.cos(rad)
            ly = cy + (self.radius - 12) * math.sin(rad)
            t_surf = font.render(lbl, True, COLOR_TEXT_YELLOW if lbl == 'N' else COLOR_TEXT_WHITE)
            t_rect = t_surf.get_rect(center=(lx, ly))
            surface.blit(t_surf, t_rect)

        # Heading needle
        h_rad = math.radians(heading - 90)
        nx = cx + (self.radius - 6) * math.cos(h_rad)
        ny = cy + (self.radius - 6) * math.sin(h_rad)
        pygame.draw.line(surface, COLOR_TEXT_YELLOW, (cx, cy), (nx, ny), 2)
        pygame.draw.circle(surface, COLOR_TEXT_YELLOW, (cx, cy), 3)

class ModalDialog:
    def __init__(self, title, message, is_success=True, on_close=None):
        self.title = title
        self.message = message
        self.is_success = is_success
        self.on_close = on_close
        self.rect = pygame.Rect(200, 250, 600, 260)
        self.ok_btn = None

    def handle_event(self, event):
        if self.ok_btn and self.ok_btn.handle_event(event):
            return True
        return False

    def draw(self, surface, font_title, font_body, font_btn):
        # Dim background
        dim_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        dim_surface.fill((0, 0, 0, 180))
        surface.blit(dim_surface, (0, 0))

        # Modal Box
        pygame.draw.rect(surface, (20, 28, 38), self.rect, border_radius=8)
        border_col = COLOR_SUCCESS_GREEN if self.is_success else COLOR_ALERT_RED
        pygame.draw.rect(surface, border_col, self.rect, width=2, border_radius=8)

        # Header title
        title_surf = font_title.render(self.title, True, border_col)
        surface.blit(title_surf, (self.rect.x + 20, self.rect.y + 18))

        # Message with wrapping
        words = self.message.split(' ')
        lines = []
        cur_line = []
        for word in words:
            test_line = ' '.join(cur_line + [word])
            if font_body.size(test_line)[0] > (self.rect.width - 40):
                lines.append(' '.join(cur_line))
                cur_line = [word]
            else:
                cur_line.append(word)
        if cur_line:
            lines.append(' '.join(cur_line))

        for idx, line in enumerate(lines[:6]):
            line_surf = font_body.render(line, True, COLOR_TEXT_WHITE)
            surface.blit(line_surf, (self.rect.x + 20, self.rect.y + 60 + (idx * 22)))

        # OK button
        btn_rect = pygame.Rect(self.rect.centerx - 60, self.rect.bottom - 45, 120, 32)
        if not self.ok_btn:
            self.ok_btn = Button(btn_rect, "CLOSE", font_btn, on_click=self.on_close, bg_color=border_col)
        self.ok_btn.draw(surface)
