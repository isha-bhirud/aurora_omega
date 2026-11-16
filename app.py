"""
AURORA - Main Desktop Pygame Application
Integrates all operational views:
  1. Dashboard & Schedule
  2. Manual Runway Assignment & Validation Engine
  3. Artos 2D Radar Scope (Map 1 & Map 2)
  4. Fleet & Infrastructure Management
  5. Academic DBMS SQL Concept Demonstrator
"""

import pygame
import sys
from db import fetch_all, fetch_one, execute
from validator import validate_runway_assignment
from ui_components import (
    Button, StatCard, DataTable, ModalDialog,
    COLOR_BG, COLOR_PANEL, COLOR_ACCENT_CYAN, COLOR_RUNWAY_BLUE,
    COLOR_TEXT_WHITE, COLOR_TEXT_MUTED, COLOR_TEXT_YELLOW,
    COLOR_SUCCESS_GREEN, COLOR_ALERT_RED
)
from artos_radar import ArtosRadarView

WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
PRESET_CREDENTIALS = {
    "admin": {"password": "admin123", "role": "admin"},
    "user": {"password": "user123", "role": "user"},
}
USER_VIEW_TABS = {"DASHBOARD", "RADAR", "FLEET", "REPORTS"}
NAV_TABS = ("DASHBOARD", "ASSIGNMENT", "RADAR", "FLEET", "REPORTS")

class AuroraApp:
    def __init__(self):
        pygame.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("AURORA — Aircraft & Runway Operations Archive (Artos 2.0 Engine)")
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_title = pygame.font.SysFont("Segoe UI, Arial", 20, bold=True)
        self.font_hdr = pygame.font.SysFont("Segoe UI, Arial", 15, bold=True)
        self.font_main = pygame.font.SysFont("Segoe UI, Arial", 13)
        self.font_sub = pygame.font.SysFont("Segoe UI, Arial", 11)
        self.font_card_val = pygame.font.SysFont("Segoe UI, Arial", 24, bold=True)

        # State
        self.current_tab = "DASHBOARD"
        self.active_modal = None
        self.stats = {}
        self.authenticated = False
        self.current_user = None
        self.current_role = None
        self.login_username = ""
        self.login_password = ""
        self.login_focus = "username"
        self.login_error = ""
        self.login_username_rect = pygame.Rect(400, 300, 400, 42)
        self.login_password_rect = pygame.Rect(400, 370, 400, 42)
        self.login_button = Button((500, 440, 200, 42), "SIGN IN", self.font_hdr,
                                   on_click=self.login, bg_color=(20, 80, 120))

        # Top Nav Buttons
        nav_y = 10
        btn_w = 175
        self.nav_buttons = [
            Button((20 + i * (btn_w + 10), nav_y, btn_w, 36), title, self.font_hdr,
                   on_click=lambda t=key: self.set_tab(t), active=(key == "DASHBOARD"))
            for i, (title, key) in enumerate([
                ("1. DASHBOARD", "DASHBOARD"),
                ("2. RUNWAY ASSIGNMENT", "ASSIGNMENT"),
                ("3. RADAR SCOPE", "RADAR"),
                ("4. FLEET & AIRPORTS", "FLEET"),
                ("5. DBMS SQL REPORTS", "REPORTS")
            ])
        ]
        self.logout_button = Button((1035, nav_y, 145, 36), "LOG OUT", self.font_hdr,
                                    on_click=self.logout, bg_color=(90, 45, 45))

        # Views & Data
        self.radar_view = ArtosRadarView((20, 95, WINDOW_WIDTH - 40, WINDOW_HEIGHT - 115))
        self.radar_airport_buttons = []
        self.refresh_radar_airport_buttons()
        self.init_dashboard_view()
        self.init_assignment_view()
        self.init_fleet_view()
        self.init_reports_view()

        # Refresh Initial Data
        self.refresh_all_data()

    def set_tab(self, tab_key):
        if not self.authenticated:
            return
        if self.current_role == "user" and tab_key not in USER_VIEW_TABS:
            return
        self.current_tab = tab_key
        for btn in self.nav_buttons:
            btn.active = (btn.text.endswith(tab_key) or 
                          (tab_key == "DASHBOARD" and "DASHBOARD" in btn.text) or
                          (tab_key == "ASSIGNMENT" and "ASSIGNMENT" in btn.text) or
                          (tab_key == "RADAR" and "RADAR" in btn.text) or
                          (tab_key == "FLEET" and "FLEET" in btn.text) or
                          (tab_key == "REPORTS" and "REPORTS" in btn.text))
        if tab_key == "DASHBOARD":
            self.refresh_dashboard()
        elif tab_key == "ASSIGNMENT":
            self.refresh_assignment_data()
        elif tab_key == "FLEET":
            self.refresh_fleet_data()
        elif tab_key == "RADAR":
            self.radar_view.load_map_data()
            self.refresh_radar_airport_buttons()

    def login(self):
        account = PRESET_CREDENTIALS.get(self.login_username.strip().lower())
        if not account or self.login_password != account["password"]:
            self.login_error = "Username or password is incorrect."
            return
        self.authenticated = True
        self.current_user = self.login_username.strip().lower()
        self.current_role = account["role"]
        self.login_password = ""
        self.login_error = ""
        self.current_tab = "DASHBOARD"
        self.refresh_dashboard()
        if self.current_role == "user":
            self.refresh_fleet_data()
            self.load_report(self.current_report_key)

    def logout(self):
        self.authenticated = False
        self.current_user = None
        self.current_role = None
        self.login_username = ""
        self.login_password = ""
        self.login_focus = "username"
        self.login_error = ""

    def handle_login_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.login_username_rect.collidepoint(event.pos):
                self.login_focus = "username"
                return
            if self.login_password_rect.collidepoint(event.pos):
                self.login_focus = "password"
                return
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_TAB:
            self.login_focus = "password" if self.login_focus == "username" else "username"
        elif event.key == pygame.K_RETURN:
            self.login()
        elif event.key == pygame.K_BACKSPACE:
            if self.login_focus == "username":
                self.login_username = self.login_username[:-1]
            else:
                self.login_password = self.login_password[:-1]
        elif event.unicode and event.unicode.isprintable():
            if self.login_focus == "username" and len(self.login_username) < 40:
                self.login_username += event.unicode
            elif self.login_focus == "password" and len(self.login_password) < 64:
                self.login_password += event.unicode

    def refresh_radar_airport_buttons(self):
        airports = self.radar_view.airports
        gap, left, width = 8, 20, 150
        available = WINDOW_WIDTH - 2 * left
        width = min(width, max(92, (available - max(0, len(airports) - 1) * gap) // max(1, len(airports))))
        self.radar_airport_buttons = [
            Button((left + idx * (width + gap), 60, width, 28), f"{airport['iata_code']}  {airport['icao_code']}",
                   self.font_sub, on_click=lambda aid=airport["airport_id"]: self.select_radar_airport(aid),
                   active=(airport["airport_id"] == self.radar_view.current_airport_id))
            for idx, airport in enumerate(airports)
        ]

    def select_radar_airport(self, airport_id):
        if self.radar_view.set_airport(airport_id):
            for button, airport in zip(self.radar_airport_buttons, self.radar_view.airports):
                button.active = airport["airport_id"] == airport_id

    def show_modal(self, title, message, is_success):
        self.active_modal = ModalDialog(title, message, is_success, on_close=self.close_modal)

    def close_modal(self):
        self.active_modal = None

    # =========================================================================
    # VIEW INITIALIZERS & DATA LOADERS
    # =========================================================================
    def init_dashboard_view(self):
        # Schedule Table
        cols = ["ID", "FLIGHT", "AIRLINE", "TYPE", "STATION", "SCHEDULED TIME", "ASSIGNED VECTOR", "STATUS"]
        widths = [45, 95, 170, 90, 80, 210, 160, 110]
        self.schedule_table = DataTable((20, 215, WINDOW_WIDTH - 40, WINDOW_HEIGHT - 235), cols, widths, self.font_main)

    def init_assignment_view(self):
        # Operations List Table (Left)
        op_cols = ["ID", "FLIGHT", "STATION", "TYPE", "SCHEDULED TIME", "ASSIGNED"]
        op_widths = [40, 90, 75, 85, 190, 120]
        self.assign_op_table = DataTable((20, 105, 620, WINDOW_HEIGHT - 125), op_cols, op_widths, self.font_main)

        # Available Directions Table (Right)
        dir_cols = ["DIR ID", "VECTOR", "RWY", "AIRPORT", "LAND", "T/O", "ILS", "CATEGORY"]
        dir_widths = [60, 65, 75, 70, 55, 55, 50, 80]
        self.assign_dir_table = DataTable((660, 105, 520, 360), dir_cols, dir_widths, self.font_main)

        # Action Buttons
        self.btn_validate = Button((660, 485, 250, 42), "CHECK VALIDATION RULES", self.font_hdr,
                                   on_click=self.on_validate_assignment, bg_color=(20, 80, 120))
        self.btn_confirm = Button((930, 485, 250, 42), "CONFIRM ASSIGNMENT", self.font_hdr,
                                  on_click=self.on_confirm_assignment, bg_color=(30, 120, 60))
        self.btn_cancel_assignment = Button((660, 540, 250, 36), "CANCEL CURRENT VECTOR", self.font_main,
                                           on_click=self.on_cancel_assignment, bg_color=(120, 40, 40))

    def init_fleet_view(self):
        self.fleet_subtab = "AIRCRAFT"
        self.fleet_buttons = [
            Button((20, 60, 140, 30), "AIRCRAFT FLEET", self.font_sub,
                   on_click=lambda: self.set_fleet_subtab("AIRCRAFT"), active=True),
            Button((170, 60, 140, 30), "AIRCRAFT TYPES", self.font_sub,
                   on_click=lambda: self.set_fleet_subtab("TYPES")),
            Button((320, 60, 140, 30), "AIRLINES", self.font_sub,
                   on_click=lambda: self.set_fleet_subtab("AIRLINES")),
            Button((470, 60, 140, 30), "AIRPORTS", self.font_sub,
                   on_click=lambda: self.set_fleet_subtab("AIRPORTS"))
        ]
        self.fleet_table = DataTable((20, 105, WINDOW_WIDTH - 40, WINDOW_HEIGHT - 125), [], [], self.font_main)

    def set_fleet_subtab(self, subtab):
        self.fleet_subtab = subtab
        for b in self.fleet_buttons:
            b.active = (subtab in b.text)
        self.refresh_fleet_data()

    def init_reports_view(self):
        self.current_report_key = "UNASSIGNED"
        self.report_buttons = [
            Button((20, 60, 220, 30), "1. UNASSIGNED (ANTI-JOIN)", self.font_sub,
                   on_click=lambda: self.load_report("UNASSIGNED"), active=True),
            Button((250, 60, 220, 30), "2. COMPATIBILITY MATRIX", self.font_sub,
                   on_click=lambda: self.load_report("COMPATIBILITY")),
            Button((480, 60, 220, 30), "3. OPERATOR FLEET AGG", self.font_sub,
                   on_click=lambda: self.load_report("OPERATOR_AGG")),
            Button((710, 60, 220, 30), "4. INFRASTRUCTURE STATS", self.font_sub,
                   on_click=lambda: self.load_report("INFRASTRUCTURE")),
            Button((940, 60, 220, 30), "5. AUDIT TRAIL LOGS", self.font_sub,
                   on_click=lambda: self.load_report("AUDIT"))
        ]
        self.report_title = "Unassigned Operations (Outer Anti-Join)"
        self.report_sql = "SELECT fo.operation_id, f.flight_number... FROM flight_operation fo LEFT JOIN runway_assignment ra..."
        self.report_table = DataTable((20, 160, WINDOW_WIDTH - 40, WINDOW_HEIGHT - 180), [], [], self.font_main)

    def refresh_all_data(self):
        try:
            self.refresh_dashboard()
            self.refresh_assignment_data()
            self.refresh_fleet_data()
            self.load_report(self.current_report_key)
        except Exception as e:
            print(f"Initial DB connect warning: {e}")

    def refresh_dashboard(self):
        # Stats counts
        try:
            ac_res = fetch_one("SELECT COUNT(*) AS total, SUM(CASE WHEN aircraft_status='ACTIVE' THEN 1 ELSE 0 END) AS active FROM aircraft") or {}
            ap_res = fetch_one("SELECT COUNT(*) AS cnt FROM airport") or {}
            rw_res = fetch_one("SELECT COUNT(*) AS cnt FROM runway") or {}
            infra_res = fetch_one("""
                SELECT (SELECT COUNT(*) FROM terminal) AS terminals,
                       (SELECT COUNT(*) FROM aircraft_stand) AS stands
            """) or {}
            op_res = fetch_one("SELECT COUNT(fo.operation_id) AS total, SUM(CASE WHEN ra.assignment_id IS NULL THEN 1 ELSE 0 END) AS unassigned FROM flight_operation fo LEFT JOIN runway_assignment ra ON fo.operation_id = ra.operation_id") or {}

            self.stats = {
                "total_ac": ac_res.get("total", 0),
                "active_ac": ac_res.get("active", 0),
                "airports": ap_res.get("cnt", 0),
                "runways": rw_res.get("cnt", 0),
                "terminals": infra_res.get("terminals", 0),
                "stands": infra_res.get("stands", 0),
                "total_ops": op_res.get("total", 0),
                "unassigned_ops": op_res.get("unassigned", 0)
            }

            # Operations list
            ops = fetch_all("""
            SELECT 
              fo.operation_id, f.flight_number, al.airline_name, fo.operation_type,
              ap.iata_code AS station, fo.scheduled_datetime,
              COALESCE(rd.designation, 'UNASSIGNED') AS assigned_vector,
              fo.operation_status
            FROM flight_operation fo
            JOIN flight f ON fo.flight_id = f.flight_id
            JOIN airline al ON f.airline_id = al.airline_id
            JOIN airport ap ON fo.airport_id = ap.airport_id
            LEFT JOIN runway_assignment ra ON fo.operation_id = ra.operation_id
            LEFT JOIN runway_direction rd ON ra.direction_id = rd.direction_id
            ORDER BY fo.scheduled_datetime ASC
            """)
            table_rows = [
                [r["operation_id"], r["flight_number"], r["airline_name"][:18], r["operation_type"],
                 r["station"], str(r["scheduled_datetime"]), r["assigned_vector"], r["operation_status"]]
                for r in ops
            ]
            self.schedule_table.set_data(table_rows)
        except Exception as e:
            print(f"Error refreshing dashboard: {e}")

    def refresh_assignment_data(self):
        try:
            ops = fetch_all("""
            SELECT 
              fo.operation_id, f.flight_number, ap.iata_code AS station,
              fo.operation_type, fo.scheduled_datetime,
              COALESCE(rd.designation, 'NONE') AS assigned
            FROM flight_operation fo
            JOIN flight f ON fo.flight_id = f.flight_id
            JOIN airport ap ON fo.airport_id = ap.airport_id
            LEFT JOIN runway_assignment ra ON fo.operation_id = ra.operation_id
            LEFT JOIN runway_direction rd ON ra.direction_id = rd.direction_id
            ORDER BY (ra.assignment_id IS NOT NULL), fo.scheduled_datetime ASC
            """)
            self.assign_op_table.set_data([
                [r["operation_id"], r["flight_number"], r["station"], r["operation_type"],
                 str(r["scheduled_datetime"]), r["assigned"]]
                for r in ops
            ])

            dirs = fetch_all("""
            SELECT 
              rd.direction_id, rd.designation, rw.runway_designation,
              ap.iata_code AS airport_code,
              CASE WHEN rd.landing_permitted=1 THEN 'YES' ELSE 'NO' END AS land,
              CASE WHEN rd.takeoff_permitted=1 THEN 'YES' ELSE 'NO' END AS to_perm,
              CASE WHEN rd.ils_available=1 THEN 'YES' ELSE 'NO' END AS ils,
              rd.approach_category
            FROM runway_direction rd
            JOIN runway rw ON rd.runway_id = rw.runway_id
            JOIN airport ap ON rw.airport_id = ap.airport_id
            ORDER BY ap.iata_code, rd.designation
            """)
            self.assign_dir_table.set_data([
                [r["direction_id"], r["designation"], r["runway_designation"], r["airport_code"],
                 r["land"], r["to_perm"], r["ils"], r["approach_category"]]
                for r in dirs
            ])
        except Exception as e:
            print(f"Error refreshing assignment data: {e}")

    def refresh_fleet_data(self):
        try:
            if self.fleet_subtab == "AIRCRAFT":
                rows = fetch_all("""
                SELECT ac.aircraft_id, ac.registration_number, act.model, al.airline_name,
                       ac.aircraft_status, ac.manufacturing_date
                FROM aircraft ac
                JOIN aircraft_type act ON ac.type_id = act.type_id
                JOIN airline al ON ac.operator_airline_id = al.airline_id
                ORDER BY ac.registration_number
                """)
                cols = ["ID", "REGISTRATION", "MODEL", "OPERATOR AIRLINE", "STATUS", "MANUFACTURED"]
                widths = [50, 140, 220, 280, 140, 160]
                self.fleet_table.columns = cols
                self.fleet_table.col_widths = widths
                self.fleet_table.set_data([[r["aircraft_id"], r["registration_number"], r["model"],
                                            r["airline_name"], r["aircraft_status"], str(r["manufacturing_date"])]
                                           for r in rows])

            elif self.fleet_subtab == "TYPES":
                rows = fetch_all("""
                SELECT type_id, manufacturer, model, variant, aircraft_category,
                       passenger_capacity, max_takeoff_weight, min_runway_length
                FROM aircraft_type ORDER BY manufacturer, model
                """)
                cols = ["ID", "MANUFACTURER", "MODEL", "VARIANT", "CAT", "PAX", "MTOW (KG)", "MIN RWY (M)"]
                widths = [45, 160, 180, 160, 100, 70, 140, 130]
                self.fleet_table.columns = cols
                self.fleet_table.col_widths = widths
                self.fleet_table.set_data([[r["type_id"], r["manufacturer"], r["model"], r["variant"],
                                            r["aircraft_category"], r["passenger_capacity"],
                                            f"{float(r['max_takeoff_weight']):,.0f}", f"{float(r['min_runway_length']):,.0f}"]
                                           for r in rows])

            elif self.fleet_subtab == "AIRLINES":
                rows = fetch_all("SELECT airline_id, airline_name, iata_code, icao_code, country, callsign, operating_status FROM airline")
                cols = ["ID", "AIRLINE NAME", "IATA", "ICAO", "COUNTRY", "CALLSIGN", "STATUS"]
                widths = [50, 260, 80, 80, 180, 160, 120]
                self.fleet_table.columns = cols
                self.fleet_table.col_widths = widths
                self.fleet_table.set_data([[r["airline_id"], r["airline_name"], r["iata_code"],
                                            r["icao_code"], r["country"], r["callsign"], r["operating_status"]]
                                           for r in rows])

            elif self.fleet_subtab == "AIRPORTS":
                rows = fetch_all("""
                SELECT ap.airport_id, ap.iata_code, ap.icao_code, ap.airport_name, ap.city, ap.country,
                       ap.elevation, COUNT(rw.runway_id) AS runways_cnt
                FROM airport ap
                LEFT JOIN runway rw ON ap.airport_id = rw.airport_id
                GROUP BY ap.airport_id, ap.iata_code, ap.icao_code, ap.airport_name, ap.city, ap.country, ap.elevation
                """)
                cols = ["ID", "IATA", "ICAO", "AIRPORT NAME", "CITY", "COUNTRY", "ELEV (M)", "RUNWAYS"]
                widths = [45, 75, 75, 300, 160, 140, 95, 90]
                self.fleet_table.columns = cols
                self.fleet_table.col_widths = widths
                self.fleet_table.set_data([[r["airport_id"], r["iata_code"], r["icao_code"],
                                            r["airport_name"], r["city"], r["country"],
                                            f"{float(r['elevation']):.1f}", r["runways_cnt"]]
                                           for r in rows])
        except Exception as e:
            print(f"Error in fleet data: {e}")

    def load_report(self, report_key):
        self.current_report_key = report_key
        for b in self.report_buttons:
            b.active = (report_key in b.text or 
                        (report_key == "UNASSIGNED" and "UNASSIGNED" in b.text) or
                        (report_key == "COMPATIBILITY" and "COMPATIBILITY" in b.text) or
                        (report_key == "OPERATOR_AGG" and "OPERATOR" in b.text) or
                        (report_key == "INFRASTRUCTURE" and "INFRASTRUCTURE" in b.text) or
                        (report_key == "AUDIT" and "AUDIT" in b.text))
        try:
            if report_key == "UNASSIGNED":
                self.report_title = "Unassigned Operations (Outer Anti-Join)"
                self.report_sql = "SELECT fo.operation_id, f.flight_number, al.airline_name, ap.iata_code, fo.scheduled_datetime FROM flight_operation fo LEFT JOIN runway_assignment ra ON fo.operation_id = ra.operation_id WHERE ra.assignment_id IS NULL"
                rows = fetch_all("""
                SELECT fo.operation_id, f.flight_number, al.airline_name, ap.iata_code,
                       fo.operation_type, fo.scheduled_datetime, fo.operation_status
                FROM flight_operation fo
                JOIN flight f ON fo.flight_id = f.flight_id
                JOIN airline al ON f.airline_id = al.airline_id
                JOIN airport ap ON fo.airport_id = ap.airport_id
                LEFT JOIN runway_assignment ra ON fo.operation_id = ra.operation_id
                WHERE ra.assignment_id IS NULL
                """)
                cols = ["OP ID", "FLIGHT", "AIRLINE", "AIRPORT", "TYPE", "SCHEDULED TIME", "STATUS"]
                widths = [60, 110, 220, 95, 100, 220, 140]
                self.report_table.columns = cols
                self.report_table.col_widths = widths
                self.report_table.set_data([[r["operation_id"], r["flight_number"], r["airline_name"],
                                             r["iata_code"], r["operation_type"], str(r["scheduled_datetime"]), r["operation_status"]]
                                            for r in rows])

            elif report_key == "COMPATIBILITY":
                self.report_title = "Aircraft-Runway Compatibility Matrix (Relational Intersect)"
                self.report_sql = "SELECT act.model, ap.iata_code, rw.runway_designation, arc.landing_eligible, arc.takeoff_eligible, arc.remarks FROM aircraft_runway_compatibility arc JOIN aircraft_type act..."
                rows = fetch_all("""
                SELECT act.model, ap.iata_code, rw.runway_designation,
                       CASE WHEN arc.landing_eligible=1 THEN 'YES' ELSE 'NO' END AS landing_ok,
                       CASE WHEN arc.takeoff_eligible=1 THEN 'YES' ELSE 'NO' END AS takeoff_ok,
                       COALESCE(arc.remarks, 'Certified standard') AS remarks
                FROM aircraft_runway_compatibility arc
                JOIN aircraft_type act ON arc.type_id = act.type_id
                JOIN runway rw ON arc.runway_id = rw.runway_id
                JOIN airport ap ON rw.airport_id = ap.airport_id
                ORDER BY act.model, ap.iata_code
                """)
                cols = ["AIRCRAFT MODEL", "AIRPORT", "RUNWAY", "LANDING OK", "TAKEOFF OK", "RESTRICTIONS / REMARKS"]
                widths = [190, 85, 95, 105, 105, 420]
                self.report_table.columns = cols
                self.report_table.col_widths = widths
                self.report_table.set_data([[r["model"], r["iata_code"], r["runway_designation"],
                                             r["landing_ok"], r["takeoff_ok"], r["remarks"][:55]]
                                            for r in rows])

            elif report_key == "OPERATOR_AGG":
                self.report_title = "Aircraft Fleet Aggregation by Airline (GROUP BY & HAVING)"
                self.report_sql = "SELECT al.airline_name, act.aircraft_category, COUNT(ac.aircraft_id) AS airframes, SUM(CASE WHEN ac.aircraft_status='ACTIVE' THEN 1 ELSE 0 END) AS active_frames FROM aircraft ac GROUP BY al.airline_name, act.aircraft_category"
                rows = fetch_all("""
                SELECT al.airline_name, act.aircraft_category,
                       COUNT(ac.aircraft_id) AS total_frames,
                       SUM(CASE WHEN ac.aircraft_status='ACTIVE' THEN 1 ELSE 0 END) AS active_frames
                FROM aircraft ac
                JOIN airline al ON ac.operator_airline_id = al.airline_id
                JOIN aircraft_type act ON ac.type_id = act.type_id
                GROUP BY al.airline_name, act.aircraft_category
                ORDER BY al.airline_name
                """)
                cols = ["AIRLINE NAME", "AIRCRAFT CATEGORY", "TOTAL FLEET COUNT", "ACTIVE FLEET COUNT"]
                widths = [320, 220, 200, 200]
                self.report_table.columns = cols
                self.report_table.col_widths = widths
                self.report_table.set_data([[r["airline_name"], r["aircraft_category"], r["total_frames"], r["active_frames"]]
                                            for r in rows])

            elif report_key == "INFRASTRUCTURE":
                self.report_title = "Airport Infrastructure Summary (Relational View Integration)"
                self.report_sql = "SELECT * FROM view_airport_infrastructure_summary"
                rows = fetch_all("SELECT * FROM view_airport_infrastructure_summary")
                cols = ["IATA", "ICAO", "AIRPORT NAME", "CITY", "RUNWAYS", "DIRECTIONS", "TAXIWAYS", "TERMINALS", "STANDS"]
                widths = [75, 75, 290, 150, 85, 90, 85, 90, 80]
                self.report_table.columns = cols
                self.report_table.col_widths = widths
                self.report_table.set_data([[r["iata_code"], r["icao_code"], r["airport_name"],
                                             r["city"], r["runway_count"], r["direction_count"],
                                             r["taxiway_count"], r["terminal_count"], r["stand_count"]]
                                            for r in rows])

            elif report_key == "AUDIT":
                self.report_title = "Assignment Audit Trail (Automatic Trigger Log)"
                self.report_sql = "SELECT aa.audit_id, f.flight_number, aa.old_status, aa.new_status, aa.action_type, aa.changed_by, aa.changed_at FROM assignment_audit aa JOIN flight_operation fo..."
                rows = fetch_all("""
                SELECT aa.audit_id, f.flight_number, fo.operation_type,
                       COALESCE(aa.old_status, 'NULL') AS old_st,
                       aa.new_status, aa.action_type, aa.changed_by, aa.changed_at
                FROM assignment_audit aa
                JOIN flight_operation fo ON aa.operation_id = fo.operation_id
                JOIN flight f ON fo.flight_id = f.flight_id
                ORDER BY aa.changed_at DESC
                LIMIT 50
                """)
                cols = ["AUDIT ID", "FLIGHT", "OPERATION", "OLD STATUS", "NEW STATUS", "ACTION", "OPERATOR", "TIMESTAMP"]
                widths = [75, 110, 120, 110, 110, 95, 150, 220]
                self.report_table.columns = cols
                self.report_table.col_widths = widths
                self.report_table.set_data([[r["audit_id"], r["flight_number"], r["operation_type"],
                                             r["old_st"], r["new_status"], r["action_type"],
                                             r["changed_by"], str(r["changed_at"])]
                                            for r in rows])
        except Exception as e:
            print(f"Error loading report {report_key}: {e}")

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================
    def on_validate_assignment(self):
        sel_op = self.assign_op_table.get_selected_row()
        sel_dir = self.assign_dir_table.get_selected_row()

        if not sel_op:
            self.show_modal("SELECTION REQUIRED", "Please select a flight operation row on the left table.", False)
            return
        if not sel_dir:
            self.show_modal("SELECTION REQUIRED", "Please select a candidate runway direction row on the right table.", False)
            return

        op_id = sel_op[0]
        dir_id = sel_dir[0]
        result = validate_runway_assignment(op_id, dir_id)

        title = "RULE VALIDATION PASSED" if result.is_valid else "VALIDATION REJECTED"
        self.show_modal(title, result.reason, result.is_valid)

    def on_confirm_assignment(self):
        sel_op = self.assign_op_table.get_selected_row()
        sel_dir = self.assign_dir_table.get_selected_row()

        if not sel_op or not sel_dir:
            self.show_modal("SELECTION ERROR", "Please select both a flight operation and a candidate runway vector.", False)
            return

        op_id = sel_op[0]
        dir_id = sel_dir[0]
        result = validate_runway_assignment(op_id, dir_id)

        if not result.is_valid:
            self.show_modal("CANNOT COMMIT INVALID ASSIGNMENT", result.reason, False)
            return

        # Commit to MySQL
        try:
            existing = fetch_one("SELECT assignment_id FROM runway_assignment WHERE operation_id = %s", (op_id,))
            if existing:
                execute("""
                UPDATE runway_assignment
                SET direction_id = %s, assignment_status = 'CONFIRMED', assignment_datetime = NOW(), assigned_by = 'PYGAME_ATC'
                WHERE operation_id = %s
                """, (dir_id, op_id))
            else:
                execute("""
                INSERT INTO runway_assignment (operation_id, direction_id, assignment_status, assigned_by, remarks)
                VALUES (%s, %s, 'CONFIRMED', 'PYGAME_ATC', 'Manual assignment validated and saved')
                """, (op_id, dir_id))

            self.show_modal("ASSIGNMENT RECORDED", 
                            f"Runway direction vector {sel_dir[1]} on {sel_dir[2]} confirmed for {sel_op[1]}! Audit log triggered.", True)
            self.refresh_assignment_data()
            self.refresh_dashboard()
        except Exception as e:
            self.show_modal("DATABASE ERROR", f"Transaction failed: {e}", False)

    def on_cancel_assignment(self):
        sel_op = self.assign_op_table.get_selected_row()
        if not sel_op:
            self.show_modal("SELECTION ERROR", "Select an operation on the left to cancel its runway assignment.", False)
            return
        op_id = sel_op[0]
        try:
            execute("DELETE FROM runway_assignment WHERE operation_id = %s", (op_id,))
            self.show_modal("ASSIGNMENT CANCELLED", f"Cleared runway vector for Operation {sel_op[1]}. Audit trigger recorded.", True)
            self.refresh_assignment_data()
            self.refresh_dashboard()
        except Exception as e:
            self.show_modal("ERROR", f"Failed to cancel: {e}", False)

    # =========================================================================
    # MAIN LOOP & DRAW ROUTINES
    # =========================================================================
    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    break

                # Modal takes precedence
                if self.active_modal:
                    self.active_modal.handle_event(event)
                    continue

                if not self.authenticated:
                    self.login_button.handle_event(event)
                    self.handle_login_event(event)
                    continue

                # Top Nav
                for btn in self.nav_buttons:
                    btn.handle_event(event)
                self.logout_button.handle_event(event)

                # Route to active view
                if self.current_tab == "DASHBOARD":
                    self.schedule_table.handle_event(event)
                elif self.current_tab == "ASSIGNMENT":
                    self.assign_op_table.handle_event(event)
                    self.assign_dir_table.handle_event(event)
                    self.btn_validate.handle_event(event)
                    self.btn_confirm.handle_event(event)
                    self.btn_cancel_assignment.handle_event(event)
                elif self.current_tab == "RADAR":
                    for btn in self.radar_airport_buttons:
                        btn.handle_event(event)
                    self.radar_view.handle_event(event)
                elif self.current_tab == "FLEET":
                    for b in self.fleet_buttons:
                        b.handle_event(event)
                    self.fleet_table.handle_event(event)
                elif self.current_tab == "REPORTS":
                    for b in self.report_buttons:
                        b.handle_event(event)
                    self.report_table.handle_event(event)

            self.draw()
            pygame.display.flip()
            self.clock.tick(30)

        pygame.quit()
        sys.exit()

    def draw(self):
        self.screen.fill(COLOR_BG)

        if not self.authenticated:
            self.draw_login()
            return

        # Top Bar
        pygame.draw.rect(self.screen, COLOR_PANEL, (0, 0, WINDOW_WIDTH, 56))
        pygame.draw.line(self.screen, (35, 50, 70), (0, 56), (WINDOW_WIDTH, 56), 1)

        visible_tabs = USER_VIEW_TABS if self.current_role == "user" else set(NAV_TABS)
        for btn, tab_key in zip(self.nav_buttons, NAV_TABS):
            if tab_key in visible_tabs:
                btn.draw(self.screen)
        self.logout_button.draw(self.screen)

        # Draw Active Tab
        if self.current_tab == "DASHBOARD":
            self.draw_dashboard()
        elif self.current_tab == "ASSIGNMENT":
            self.draw_assignment()
        elif self.current_tab == "RADAR":
            self.draw_radar()
        elif self.current_tab == "FLEET":
            self.draw_fleet()
        elif self.current_tab == "REPORTS":
            self.draw_reports()

        # Modal Dialog (if open)
        if self.active_modal:
            self.active_modal.draw(self.screen, self.font_hdr, self.font_main, self.font_hdr)

    def draw_login(self):
        self.screen.fill(COLOR_BG)
        pygame.draw.rect(self.screen, COLOR_PANEL, (0, 0, WINDOW_WIDTH, 56))
        pygame.draw.line(self.screen, (35, 50, 70), (0, 56), (WINDOW_WIDTH, 56), 1)
        title = self.font_title.render("AURORA  |  OPERATIONS ACCESS", True, COLOR_TEXT_WHITE)
        self.screen.blit(title, title.get_rect(center=(WINDOW_WIDTH // 2, 190)))

        for label, rect, value, field_name in (
            ("USERNAME", self.login_username_rect, self.login_username, "username"),
            ("PASSWORD", self.login_password_rect, "•" * len(self.login_password), "password"),
        ):
            caption = self.font_sub.render(label, True, COLOR_TEXT_MUTED)
            self.screen.blit(caption, (rect.x, rect.y - 20))
            border = COLOR_ACCENT_CYAN if self.login_focus == field_name else (60, 80, 110)
            pygame.draw.rect(self.screen, (17, 25, 34), rect)
            pygame.draw.rect(self.screen, border, rect, width=1)
            text = self.font_main.render(value, True, COLOR_TEXT_WHITE)
            self.screen.blit(text, (rect.x + 12, rect.y + 13))

        self.login_button.draw(self.screen)
        credentials = self.font_main.render(
            "Preset access: admin / admin123     |     user / user123", True, COLOR_TEXT_MUTED)
        self.screen.blit(credentials, credentials.get_rect(center=(WINDOW_WIDTH // 2, 520)))
        if self.login_error:
            error = self.font_main.render(self.login_error, True, COLOR_ALERT_RED)
            self.screen.blit(error, error.get_rect(center=(WINDOW_WIDTH // 2, 495)))

    def draw_dashboard(self):
        # Stat Cards
        margin, card_gap = 20, 12
        card_w = (WINDOW_WIDTH - 2 * margin - 5 * card_gap) // 6
        card_data = [
            ("Total Aircraft", self.stats.get("total_ac", 0), "Registered fleet", COLOR_ACCENT_CYAN),
            ("Active Aircraft", self.stats.get("active_ac", 0), "Operational", COLOR_SUCCESS_GREEN),
            ("Airports", self.stats.get("airports", 0), "Stations", (111, 160, 188)),
            ("Runways", self.stats.get("runways", 0), "Physical runways", COLOR_RUNWAY_BLUE),
            ("Scheduled Ops", self.stats.get("total_ops", 0), "Landing and takeoff", (200, 173, 90)),
            ("Unassigned Ops", self.stats.get("unassigned_ops", 0), "Awaiting assignment", COLOR_ALERT_RED),
        ]
        cards = [StatCard((margin + i * (card_w + card_gap), 70, card_w, 100), *data)
                 for i, data in enumerate(card_data)]
        for c in cards:
            c.draw(self.screen, self.font_sub, self.font_card_val, self.font_sub)

        # Section Header
        hdr = self.font_hdr.render("UPCOMING LANDING & TAKEOFF SCHEDULE (PREDEFINED OPERATIONS)", True, COLOR_TEXT_WHITE)
        self.screen.blit(hdr, (20, 188))
        self.schedule_table.draw(self.screen)

    def draw_assignment(self):
        lbl1 = self.font_hdr.render("1. SELECT FLIGHT OPERATION TO ASSIGN", True, COLOR_TEXT_YELLOW)
        self.screen.blit(lbl1, (20, 78))
        self.assign_op_table.draw(self.screen)

        lbl2 = self.font_hdr.render("2. SELECT CANDIDATE RUNWAY DIRECTION VECTOR", True, COLOR_ACCENT_CYAN)
        self.screen.blit(lbl2, (660, 78))
        self.assign_dir_table.draw(self.screen)

        self.btn_validate.draw(self.screen)
        self.btn_confirm.draw(self.screen)
        self.btn_cancel_assignment.draw(self.screen)

        # Explanatory prompt box
        exp_rect = pygame.Rect(660, 590, 520, 150)
        pygame.draw.rect(self.screen, COLOR_PANEL, exp_rect, border_radius=6)
        pygame.draw.rect(self.screen, (40, 55, 75), exp_rect, width=1, border_radius=6)
        info_t = self.font_hdr.render("ACADEMIC DBMS VALIDATION RULES ENFORCED:", True, COLOR_ACCENT_CYAN)
        self.screen.blit(info_t, (exp_rect.x + 14, exp_rect.y + 12))
        rules = [
            "• Airport Alignment: Vector must belong to operation's station airport.",
            "• Direction Eligibility: Landing vs Takeoff permitted flags checked.",
            "• Airframe Compatibility: Aircraft type MTOW / runway length compatibility certified.",
            "• Operational Status: Physical runway must be OPEN (not CLOSED/RESTRICTED).",
            "• Restriction Window: Checks no scheduled maintenance or noise curfews overlap.",
            "• Referential Integrity: Updates are committed atomically with trigger audit logging."
        ]
        for idx, r in enumerate(rules):
            r_surf = self.font_sub.render(r, True, COLOR_TEXT_MUTED)
            self.screen.blit(r_surf, (exp_rect.x + 14, exp_rect.y + 36 + (idx * 17)))

    def draw_radar(self):
        for button in self.radar_airport_buttons:
            button.draw(self.screen)

        # Radar Scope
        self.radar_view.draw(self.screen, self.font_hdr, self.font_sub)

    def draw_fleet(self):
        for b in self.fleet_buttons:
            b.draw(self.screen)
        self.fleet_table.draw(self.screen)

    def draw_reports(self):
        for b in self.report_buttons:
            b.draw(self.screen)

        # Query Title & SQL
        t_surf = self.font_hdr.render(f"SQL DEMONSTRATION: {self.report_title}", True, COLOR_TEXT_YELLOW)
        self.screen.blit(t_surf, (20, 102))

        sql_box = pygame.Rect(20, 124, WINDOW_WIDTH - 40, 26)
        pygame.draw.rect(self.screen, (15, 20, 28), sql_box, border_radius=4)
        sql_surf = self.font_sub.render(f"SQL: {self.report_sql[:145]}...", True, COLOR_ACCENT_CYAN)
        self.screen.blit(sql_surf, (sql_box.x + 8, sql_box.y + 6))

        self.report_table.draw(self.screen)
