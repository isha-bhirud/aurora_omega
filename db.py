"""
AURORA - Unified Database Access Layer
Supports MySQL (primary) with automatic SQLite fallback when MySQL server is offline.
Ensures zero-crash out-of-the-box execution for the Pygame application.
"""

import os
import sqlite3
from contextlib import contextmanager

def load_env(env_path=".env"):
    """Loads environment variables from .env file."""
    if not os.path.exists(env_path):
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

load_env()

# Database mode state: 'mysql' or 'sqlite'
_DB_MODE = None
_SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "aurora_local.sqlite")

def detect_db_connection():
    """Detects if MySQL is reachable; otherwise selects SQLite."""
    global _DB_MODE
    if _DB_MODE is not None:
        return _DB_MODE

    host = os.environ.get("DB_HOST", "localhost")
    port = int(os.environ.get("DB_PORT", 3306))
    user = os.environ.get("DB_USER", "root")
    password = os.environ.get("DB_PASSWORD", "")
    db_name = os.environ.get("DB_NAME", "aurora_db")

    # Attempt MySQL via mysql.connector
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host=host, port=port, user=user, password=password, database=db_name,
            connection_timeout=2
        )
        conn.close()
        _DB_MODE = "mysql_connector"
        print("[AURORA DB] Connected to MySQL Server (mysql.connector).")
        return _DB_MODE
    except Exception:
        pass

    # Attempt MySQL via pymysql
    try:
        import pymysql
        conn = pymysql.connect(
            host=host, port=port, user=user, password=password, database=db_name,
            connect_timeout=2
        )
        conn.close()
        _DB_MODE = "pymysql"
        print("[AURORA DB] Connected to MySQL Server (PyMySQL).")
        return _DB_MODE
    except Exception:
        pass

    # Fallback to SQLite
    _DB_MODE = "sqlite"
    print(f"[AURORA DB] MySQL offline on {host}:{port}. Running in offline SQLite mode ({os.path.basename(_SQLITE_PATH)}).")
    ensure_sqlite_initialized()
    return _DB_MODE

def get_connection():
    mode = detect_db_connection()
    host = os.environ.get("DB_HOST", "localhost")
    port = int(os.environ.get("DB_PORT", 3306))
    user = os.environ.get("DB_USER", "root")
    password = os.environ.get("DB_PASSWORD", "")
    db_name = os.environ.get("DB_NAME", "aurora_db")

    if mode == "mysql_connector":
        import mysql.connector
        return mysql.connector.connect(host=host, port=port, user=user, password=password, database=db_name)
    elif mode == "pymysql":
        import pymysql
        return pymysql.connect(host=host, port=port, user=user, password=password, database=db_name,
                               cursorclass=pymysql.cursors.DictCursor)
    else:
        conn = sqlite3.connect(_SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn

@contextmanager
def get_cursor():
    mode = detect_db_connection()
    conn = get_connection()

    if mode == "mysql_connector":
        cursor = conn.cursor(dictionary=True)
    elif mode == "pymysql":
        cursor = conn.cursor()
    else:
        cursor = conn.cursor()

    try:
        yield cursor, conn, mode
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

def _adapt_query(query, mode):
    """Adapts query parameters and syntax for SQLite if needed."""
    if mode == "sqlite":
        # Replace %s with ?
        q = query.replace("%s", "?")
        # Replace NOW() with datetime('now')
        q = q.replace("NOW()", "datetime('now')")
        # Replace IFNULL / COALESCE functions if needed
        return q
    return query

def fetch_all(query, params=None):
    with get_cursor() as (cursor, conn, mode):
        q = _adapt_query(query, mode)
        cursor.execute(q, params or ())
        rows = cursor.fetchall()
        if mode == "sqlite":
            return [dict(r) for r in rows]
        return rows

def fetch_one(query, params=None):
    with get_cursor() as (cursor, conn, mode):
        q = _adapt_query(query, mode)
        cursor.execute(q, params or ())
        row = cursor.fetchone()
        if mode == "sqlite" and row:
            return dict(row)
        return row

def execute(query, params=None):
    with get_cursor() as (cursor, conn, mode):
        q = _adapt_query(query, mode)
        cursor.execute(q, params or ())
        return cursor.lastrowid

def ensure_sqlite_initialized():
    """Initializes local SQLite database with full AURORA schema and seed data if not present."""
    if os.path.exists(_SQLITE_PATH) and os.path.getsize(_SQLITE_PATH) > 1000:
        # Apply additive corrections to older offline databases. Existing records are
        # retained; seed rows are matched by natural airport/entity keys.
        conn = sqlite3.connect(_SQLITE_PATH)
        try:
            _repair_sqlite_seed_data(conn)
            conn.commit()
        finally:
            conn.close()
        return

    print("[AURORA DB] Initializing local database tables and demo seed records...")
    conn = sqlite3.connect(_SQLITE_PATH)
    cur = conn.cursor()

    # DDL
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS airline (
      airline_id INTEGER PRIMARY KEY AUTOINCREMENT,
      airline_name TEXT NOT NULL,
      iata_code TEXT UNIQUE,
      icao_code TEXT UNIQUE,
      country TEXT NOT NULL,
      callsign TEXT,
      operating_status TEXT NOT NULL DEFAULT 'ACTIVE'
    );

    CREATE TABLE IF NOT EXISTS aircraft_type (
      type_id INTEGER PRIMARY KEY AUTOINCREMENT,
      manufacturer TEXT NOT NULL,
      model TEXT NOT NULL,
      variant TEXT NOT NULL DEFAULT 'Standard',
      aircraft_category TEXT NOT NULL,
      wingspan REAL NOT NULL,
      aircraft_length REAL NOT NULL,
      max_takeoff_weight REAL NOT NULL,
      max_landing_weight REAL NOT NULL,
      passenger_capacity INTEGER NOT NULL DEFAULT 0,
      cargo_capacity REAL NOT NULL DEFAULT 0,
      min_runway_length REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS aircraft (
      aircraft_id INTEGER PRIMARY KEY AUTOINCREMENT,
      registration_number TEXT NOT NULL UNIQUE,
      type_id INTEGER NOT NULL,
      owner_airline_id INTEGER,
      operator_airline_id INTEGER NOT NULL,
      manufacturing_date TEXT,
      aircraft_status TEXT NOT NULL DEFAULT 'ACTIVE',
      notes TEXT
    );

    CREATE TABLE IF NOT EXISTS airport (
      airport_id INTEGER PRIMARY KEY AUTOINCREMENT,
      airport_name TEXT NOT NULL,
      iata_code TEXT UNIQUE,
      icao_code TEXT UNIQUE,
      city TEXT NOT NULL,
      region_state TEXT,
      country TEXT NOT NULL,
      latitude REAL NOT NULL,
      longitude REAL NOT NULL,
      elevation REAL NOT NULL DEFAULT 0,
      timezone TEXT NOT NULL DEFAULT 'UTC',
      operating_status TEXT NOT NULL DEFAULT 'ACTIVE'
    );

    CREATE TABLE IF NOT EXISTS runway (
      runway_id INTEGER PRIMARY KEY AUTOINCREMENT,
      airport_id INTEGER NOT NULL,
      runway_designation TEXT NOT NULL,
      runway_length REAL NOT NULL,
      runway_width REAL NOT NULL,
      surface_type TEXT NOT NULL DEFAULT 'ASPHALT',
      true_heading REAL,
      runway_status TEXT NOT NULL DEFAULT 'OPEN',
      start_x INTEGER NOT NULL DEFAULT 125,
      start_y INTEGER NOT NULL DEFAULT 500,
      end_x INTEGER NOT NULL DEFAULT 600,
      end_y INTEGER NOT NULL DEFAULT 0,
      notes TEXT
    );

    CREATE TABLE IF NOT EXISTS runway_direction (
      direction_id INTEGER PRIMARY KEY AUTOINCREMENT,
      runway_id INTEGER NOT NULL,
      designation TEXT NOT NULL,
      heading REAL NOT NULL,
      landing_permitted INTEGER NOT NULL DEFAULT 1,
      takeoff_permitted INTEGER NOT NULL DEFAULT 1,
      ils_available INTEGER NOT NULL DEFAULT 0,
      approach_category TEXT NOT NULL DEFAULT 'CAT I'
    );

    CREATE TABLE IF NOT EXISTS taxiway (
      taxiway_id INTEGER PRIMARY KEY AUTOINCREMENT,
      airport_id INTEGER NOT NULL,
      taxiway_name TEXT NOT NULL,
      surface_type TEXT NOT NULL DEFAULT 'ASPHALT',
      taxiway_status TEXT NOT NULL DEFAULT 'OPEN',
      start_x INTEGER NOT NULL DEFAULT 125,
      start_y INTEGER NOT NULL DEFAULT 200,
      end_x INTEGER NOT NULL DEFAULT 500,
      end_y INTEGER NOT NULL DEFAULT 200
    );

    CREATE TABLE IF NOT EXISTS terminal (
      terminal_id INTEGER PRIMARY KEY AUTOINCREMENT,
      airport_id INTEGER NOT NULL,
      terminal_name TEXT NOT NULL,
      terminal_type TEXT NOT NULL DEFAULT 'DOMESTIC'
    );

    CREATE TABLE IF NOT EXISTS aircraft_stand (
      stand_id INTEGER PRIMARY KEY AUTOINCREMENT,
      airport_id INTEGER NOT NULL,
      terminal_id INTEGER,
      stand_code TEXT NOT NULL,
      max_aircraft_size TEXT NOT NULL DEFAULT 'HEAVY',
      stand_status TEXT NOT NULL DEFAULT 'AVAILABLE'
    );

    CREATE TABLE IF NOT EXISTS flight (
      flight_id INTEGER PRIMARY KEY AUTOINCREMENT,
      flight_number TEXT NOT NULL,
      airline_id INTEGER NOT NULL,
      aircraft_id INTEGER NOT NULL,
      origin_airport_id INTEGER NOT NULL,
      destination_airport_id INTEGER NOT NULL,
      flight_type TEXT NOT NULL DEFAULT 'PASSENGER',
      flight_status TEXT NOT NULL DEFAULT 'SCHEDULED',
      service_date TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS flight_operation (
      operation_id INTEGER PRIMARY KEY AUTOINCREMENT,
      flight_id INTEGER NOT NULL,
      airport_id INTEGER NOT NULL,
      operation_type TEXT NOT NULL,
      scheduled_datetime TEXT NOT NULL,
      estimated_datetime TEXT,
      actual_datetime TEXT,
      operation_status TEXT NOT NULL DEFAULT 'SCHEDULED',
      notes TEXT
    );

    CREATE TABLE IF NOT EXISTS aircraft_runway_compatibility (
      type_id INTEGER NOT NULL,
      runway_id INTEGER NOT NULL,
      landing_eligible INTEGER NOT NULL DEFAULT 1,
      takeoff_eligible INTEGER NOT NULL DEFAULT 1,
      remarks TEXT,
      PRIMARY KEY (type_id, runway_id)
    );

    CREATE TABLE IF NOT EXISTS runway_restriction (
      restriction_id INTEGER PRIMARY KEY AUTOINCREMENT,
      runway_id INTEGER NOT NULL,
      restriction_type TEXT NOT NULL,
      start_datetime TEXT NOT NULL,
      end_datetime TEXT NOT NULL,
      description TEXT,
      restriction_status TEXT NOT NULL DEFAULT 'SCHEDULED'
    );

    CREATE TABLE IF NOT EXISTS airport_operating_hours (
      hours_id INTEGER PRIMARY KEY AUTOINCREMENT,
      airport_id INTEGER NOT NULL,
      day_of_week TEXT NOT NULL,
      opening_time TEXT NOT NULL,
      closing_time TEXT NOT NULL,
      is_closed INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS runway_assignment (
      assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
      operation_id INTEGER NOT NULL UNIQUE,
      direction_id INTEGER NOT NULL,
      assignment_datetime TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      assignment_status TEXT NOT NULL DEFAULT 'CONFIRMED',
      assigned_by TEXT NOT NULL DEFAULT 'OPERATIONS_DESK',
      remarks TEXT
    );

    CREATE TABLE IF NOT EXISTS airport_map (
      map_id INTEGER PRIMARY KEY AUTOINCREMENT,
      airport_id INTEGER NOT NULL,
      map_name TEXT NOT NULL,
      map_type TEXT NOT NULL,
      map_version TEXT NOT NULL DEFAULT '1.0',
      coordinate_reference_system TEXT NOT NULL DEFAULT 'SCREEN_PIXELS_1000x1000',
      map_status TEXT NOT NULL DEFAULT 'ACTIVE',
      map_asset_url TEXT
    );

    CREATE TABLE IF NOT EXISTS map_feature (
      feature_id INTEGER PRIMARY KEY AUTOINCREMENT,
      map_id INTEGER NOT NULL,
      feature_type TEXT NOT NULL,
      feature_name TEXT NOT NULL,
      pos_x INTEGER NOT NULL DEFAULT 0,
      pos_y INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS assignment_audit (
      audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
      assignment_id INTEGER NOT NULL,
      operation_id INTEGER NOT NULL,
      old_direction_id INTEGER,
      new_direction_id INTEGER,
      old_status TEXT,
      new_status TEXT NOT NULL,
      action_type TEXT NOT NULL,
      changed_by TEXT NOT NULL DEFAULT 'SYSTEM',
      changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    -- Audit triggers
    CREATE TRIGGER IF NOT EXISTS trg_audit_insert AFTER INSERT ON runway_assignment
    BEGIN
      INSERT INTO assignment_audit (assignment_id, operation_id, new_direction_id, new_status, action_type, changed_by)
      VALUES (NEW.assignment_id, NEW.operation_id, NEW.direction_id, NEW.assignment_status, 'INSERT', NEW.assigned_by);
    END;

    CREATE TRIGGER IF NOT EXISTS trg_audit_update AFTER UPDATE ON runway_assignment
    BEGIN
      INSERT INTO assignment_audit (assignment_id, operation_id, old_direction_id, new_direction_id, old_status, new_status, action_type, changed_by)
      VALUES (NEW.assignment_id, NEW.operation_id, OLD.direction_id, NEW.direction_id, OLD.assignment_status, NEW.assignment_status, 'UPDATE', NEW.assigned_by);
    END;

    CREATE TRIGGER IF NOT EXISTS trg_audit_delete AFTER DELETE ON runway_assignment
    BEGIN
      INSERT INTO assignment_audit (assignment_id, operation_id, old_direction_id, old_status, new_status, action_type, changed_by)
      VALUES (OLD.assignment_id, OLD.operation_id, OLD.direction_id, OLD.assignment_status, 'DELETED', 'DELETE', 'SYSTEM');
    END;

    -- Views
    CREATE VIEW IF NOT EXISTS view_airport_infrastructure_summary AS
    SELECT 
      ap.airport_id, ap.iata_code, ap.icao_code, ap.airport_name, ap.city, ap.country,
      COUNT(DISTINCT rw.runway_id) AS runway_count,
      COUNT(DISTINCT rd.direction_id) AS direction_count,
      COUNT(DISTINCT tw.taxiway_id) AS taxiway_count,
      COUNT(DISTINCT tm.terminal_id) AS terminal_count,
      COUNT(DISTINCT st.stand_id) AS stand_count
    FROM airport ap
    LEFT JOIN runway rw ON ap.airport_id = rw.airport_id
    LEFT JOIN runway_direction rd ON rw.runway_id = rd.runway_id
    LEFT JOIN taxiway tw ON ap.airport_id = tw.airport_id
    LEFT JOIN terminal tm ON ap.airport_id = tm.airport_id
    LEFT JOIN aircraft_stand st ON ap.airport_id = st.airport_id
    GROUP BY ap.airport_id;
    """)

    # Seed data
    cur.executescript("""
    INSERT INTO airline (airline_id, airline_name, iata_code, icao_code, country, callsign, operating_status) VALUES
    (1, 'American Airlines', 'AA', 'AAL', 'United States', 'AMERICAN', 'ACTIVE'),
    (2, 'British Airways', 'BA', 'BAW', 'United Kingdom', 'SPEEDBIRD', 'ACTIVE'),
    (3, 'Air India', 'AI', 'AIC', 'India', 'AIRINDIA', 'ACTIVE'),
    (4, 'Nordic Regional Air', 'NR', 'NRA', 'Sweden', 'NORDIC', 'ACTIVE');

    INSERT INTO aircraft_type (type_id, manufacturer, model, variant, aircraft_category, wingspan, aircraft_length, max_takeoff_weight, max_landing_weight, passenger_capacity, cargo_capacity, min_runway_length) VALUES
    (1, 'Airbus', 'A320neo', 'A320-271N', 'MEDIUM', 35.80, 37.57, 79000.00, 67400.00, 180, 3700.00, 2100.00),
    (2, 'Boeing', 'B737-800', 'NG-800', 'MEDIUM', 35.79, 39.47, 79010.00, 66360.00, 189, 4400.00, 2300.00),
    (3, 'Boeing', 'B777-300ER', 'Long-Range', 'HEAVY', 64.80, 73.86, 351530.00, 251290.00, 396, 20100.00, 3200.00),
    (4, 'Airbus', 'A350-900', 'XWB-900', 'HEAVY', 64.75, 66.80, 280000.00, 207000.00, 350, 16500.00, 2800.00),
    (5, 'ATR', 'ATR 72-600', 'Regional Turboprop', 'LIGHT', 27.05, 27.17, 23000.00, 22350.00, 72, 1700.00, 1400.00),
    (6, 'Bombardier', 'CRJ-900', 'NextGen', 'MEDIUM', 24.85, 36.20, 38330.00, 34020.00, 90, 2320.00, 1950.00);

    INSERT INTO aircraft (aircraft_id, registration_number, type_id, owner_airline_id, operator_airline_id, manufacturing_date, aircraft_status, notes) VALUES
    (1, 'N101AA', 1, 1, 1, '2021-03-15', 'ACTIVE', 'Primary mainline A320neo based at DFW hub'),
    (2, 'N102AA', 1, 1, 1, '2022-06-20', 'ACTIVE', 'Mainline A320neo based at DFW'),
    (3, 'N777AA', 3, 1, 1, '2019-11-10', 'ACTIVE', 'Widebody international 777-300ER long-hauler'),
    (4, 'G-XWBA', 4, 2, 2, '2020-01-18', 'ACTIVE', 'British Airways flagship A350-900 based at LHR'),
    (5, 'G-ZBJA', 2, 2, 2, '2021-08-04', 'ACTIVE', 'Skyline European fleet 737-800'),
    (6, 'VT-EXA', 3, 3, 3, '2023-04-12', 'ACTIVE', 'Air India flagship B777-300ER based at BOM'),
    (7, 'VT-EXB', 1, 3, 3, '2018-05-22', 'ACTIVE', 'Air India domestic trunk A320neo based at BOM'),
    (8, 'N802AA', 2, 1, 1, '2019-09-30', 'ACTIVE', 'American domestic trunk carrier B737-800'),
    (9, 'SE-NRA1', 5, 4, 4, '2022-02-14', 'ACTIVE', 'Nordic commuter ATR 72'),
    (10, 'SE-NRA2', 6, 4, 4, '2020-07-19', 'ACTIVE', 'Nordic regional jet CRJ-900'),
    (11, 'N999AA', 1, 1, 1, '2015-04-10', 'MAINTENANCE', 'In routine C-check maintenance at DFW Hangar 5'),
    (12, 'G-RETR', 2, 2, 2, '2012-08-01', 'RETIRED', 'Retired from scheduled revenue service');

    INSERT INTO airport (airport_id, airport_name, iata_code, icao_code, city, region_state, country, latitude, longitude, elevation, timezone, operating_status) VALUES
    (1, 'Dallas/Fort Worth International Airport', 'DFW', 'KDFW', 'Dallas-Fort Worth', 'Texas', 'United States', 32.899800, -97.040300, 185.00, 'America/Chicago', 'ACTIVE'),
    (2, 'London Heathrow Airport', 'LHR', 'EGLL', 'London', 'Greater London', 'United Kingdom', 51.470000, -0.454300, 25.00, 'Europe/London', 'ACTIVE'),
    (3, 'Chhatrapati Shivaji Maharaj International Airport', 'BOM', 'VABB', 'Mumbai', 'Maharashtra', 'India', 19.088600, 72.867900, 11.00, 'Asia/Kolkata', 'ACTIVE');

    INSERT INTO runway (runway_id, airport_id, runway_designation, runway_length, runway_width, surface_type, true_heading, runway_status, start_x, start_y, end_x, end_y, notes) VALUES
    (1, 1, '17L/35R', 2591.00, 45.00, 'CONCRETE', 175.00, 'OPEN', 125, 500, 600, 0, 'East parallel runway (Artos Map 1 Runway 1)'),
    (2, 1, '17C/35C', 4085.00, 45.00, 'CONCRETE', 175.00, 'OPEN', 125, 200, 1000, 300, 'Central primary long runway (Artos Map 1 Runway 2)'),
    (3, 1, '18R/36L', 4084.00, 60.00, 'CONCRETE', 185.00, 'OPEN', 125, 120, 1000, 0, 'West long heavy runway (Artos Map 1 Runway 3)'),
    (4, 2, '09L/27R', 3902.00, 50.00, 'ASPHALT', 90.00, 'OPEN', 200, 350, 900, 350, 'Northern runway at EGLL'),
    (5, 2, '09R/27L', 3660.00, 50.00, 'ASPHALT', 90.00, 'OPEN', 200, 650, 900, 650, 'Southern runway at EGLL'),
    (6, 3, '09/27', 3448.00, 45.00, 'ASPHALT', 92.00, 'OPEN', 800, 600, 100, 200, 'Main primary runway at VABB (Artos Map 2 Runway 9)'),
    (7, 3, '14/32', 2925.00, 45.00, 'ASPHALT', 142.00, 'OPEN', 800, 600, 200, 500, 'Secondary intersecting runway at VABB (Artos Map 2 Runway 10)');

    INSERT INTO runway_direction (direction_id, runway_id, designation, heading, landing_permitted, takeoff_permitted, ils_available, approach_category) VALUES
    (1, 1, '17L', 175.00, 1, 1, 1, 'CAT I'),
    (2, 1, '35R', 355.00, 1, 1, 1, 'CAT I'),
    (3, 2, '17C', 175.00, 1, 1, 1, 'CAT III'),
    (4, 2, '35C', 355.00, 1, 1, 1, 'CAT III'),
    (5, 3, '18R', 185.00, 1, 1, 1, 'CAT III'),
    (6, 3, '36L', 5.00, 1, 1, 1, 'CAT III'),
    (7, 4, '09L', 90.00, 1, 1, 1, 'CAT III'),
    (8, 4, '27R', 270.00, 1, 1, 1, 'CAT III'),
    (9, 5, '09R', 90.00, 1, 1, 1, 'CAT III'),
    (10, 5, '27L', 270.00, 1, 1, 1, 'CAT III'),
    (11, 6, '09', 92.00, 1, 1, 1, 'CAT II'),
    (12, 6, '27', 272.00, 1, 1, 1, 'CAT II'),
    (13, 7, '14', 142.00, 1, 0, 0, 'NON-PRECISION'),
    (14, 7, '32', 322.00, 0, 1, 0, 'VISUAL');

    INSERT INTO taxiway (taxiway_id, airport_id, taxiway_name, surface_type, taxiway_status, start_x, start_y, end_x, end_y) VALUES
    (1, 1, 'Alpha (A)', 'CONCRETE', 'OPEN', 125, 200, 125, 500),
    (2, 1, 'Bravo (B)', 'CONCRETE', 'OPEN', 125, 500, 125, 700),
    (3, 1, 'Kilo (K)', 'CONCRETE', 'OPEN', 300, 200, 412, 480),
    (4, 2, 'Alpha (A)', 'ASPHALT', 'OPEN', 200, 350, 200, 650),
    (5, 2, 'November (N)', 'ASPHALT', 'OPEN', 900, 350, 900, 650),
    (6, 3, 'Echo (E)', 'ASPHALT', 'OPEN', 800, 600, 800, 400),
    (7, 3, 'Sierra (S)', 'ASPHALT', 'OPEN', 800, 400, 170, 400),
    (8, 3, 'Alpha (A)', 'ASPHALT', 'OPEN', 100, 600, 1000, 600),
    (9, 3, 'Bravo (B)', 'ASPHALT', 'OPEN', 800, 200, 800, 600),
    (10, 3, 'Charlie (C)', 'ASPHALT', 'OPEN', 100, 200, 200, 500);

    INSERT INTO flight (flight_id, flight_number, airline_id, aircraft_id, origin_airport_id, destination_airport_id, flight_type, flight_status, service_date) VALUES
    (1, 'AA-101', 1, 1, 1, 3, 'PASSENGER', 'SCHEDULED', '2026-10-15'),
    (2, 'AA-102', 1, 2, 3, 1, 'PASSENGER', 'SCHEDULED', '2026-10-15'),
    (3, 'AA-201', 1, 3, 1, 2, 'PASSENGER', 'SCHEDULED', '2026-10-15'),
    (4, 'AA-202', 1, 3, 2, 1, 'PASSENGER', 'SCHEDULED', '2026-10-16'),
    (5, 'BA-192', 2, 4, 2, 1, 'PASSENGER', 'SCHEDULED', '2026-10-15'),
    (6, 'BA-193', 2, 5, 1, 2, 'PASSENGER', 'SCHEDULED', '2026-10-15'),
    (9, 'AI-102', 3, 8, 1, 3, 'PASSENGER', 'SCHEDULED', '2026-10-15');

    INSERT INTO flight_operation (operation_id, flight_id, airport_id, operation_type, scheduled_datetime, estimated_datetime, actual_datetime, operation_status, notes) VALUES
    (1, 1, 1, 'TAKEOFF', '2026-10-15 06:00:00', '2026-10-15 06:05:00', NULL, 'SCHEDULED', 'Morning departure from DFW to BOM'),
    (2, 1, 3, 'LANDING', '2026-10-15 08:15:00', '2026-10-15 08:20:00', NULL, 'SCHEDULED', 'Arrival at BOM from DFW'),
    (3, 2, 3, 'TAKEOFF', '2026-10-15 09:30:00', NULL, NULL, 'SCHEDULED', 'Morning return departure from BOM'),
    (4, 2, 1, 'LANDING', '2026-10-15 11:45:00', NULL, NULL, 'SCHEDULED', 'Arrival back at DFW base'),
    (5, 3, 1, 'TAKEOFF', '2026-10-15 02:15:00', NULL, NULL, 'SCHEDULED', 'Long-haul red-eye widebody takeoff DFW to LHR'),
    (6, 3, 2, 'LANDING', '2026-10-15 07:10:00', NULL, NULL, 'SCHEDULED', 'LHR early morning arrival'),
    (17, 9, 1, 'TAKEOFF', '2026-10-15 15:00:00', NULL, NULL, 'SCHEDULED', 'Takeoff during maintenance window at DFW');

    INSERT INTO aircraft_runway_compatibility (type_id, runway_id, landing_eligible, takeoff_eligible, remarks) VALUES
    (1, 1, 1, 1, 'Compatible on DFW 17L/35R'),
    (1, 2, 1, 1, 'Compatible on DFW 17C/35C'),
    (1, 3, 1, 1, 'Compatible on DFW 18R/36L'),
    (1, 6, 1, 1, 'Compatible on BOM 09/27'),
    (1, 7, 1, 1, 'Compatible on BOM 14/32'),
    (2, 1, 1, 1, 'Compatible on DFW 17L/35R'),
    (2, 2, 1, 1, 'Compatible on DFW 17C/35C'),
    (2, 3, 1, 1, 'Compatible on DFW 18R/36L'),
    (2, 6, 1, 1, 'Compatible on BOM 09/27'),
    (2, 7, 1, 1, 'Compatible on BOM 14/32'),
    (3, 1, 0, 0, 'INELIGIBLE: Runway length 2591m below B777-300ER MTOW safety envelope 3200m'),
    (3, 2, 1, 1, 'Eligible: DFW 17C/35C length 4085m exceeds requirements'),
    (3, 3, 1, 1, 'Eligible: DFW 18R/36L length 4084m prime widebody runway'),
    (3, 6, 1, 1, 'Eligible on BOM 09/27'),
    (3, 7, 0, 0, 'INELIGIBLE: BOM secondary runway 14/32 too short for B777');

    INSERT INTO runway_restriction (restriction_id, runway_id, restriction_type, start_datetime, end_datetime, description, restriction_status) VALUES
    (1, 3, 'LIGHTING_MAINTENANCE', '2026-10-15 13:00:00', '2026-10-15 17:00:00', 'AGL calibration window on DFW Runway 18R/36L', 'SCHEDULED'),
    (2, 7, 'NOISE_ABATEMENT', '2026-10-15 22:00:00', '2026-10-16 06:00:00', 'Night curfew restriction on BOM 14/32', 'SCHEDULED');

    INSERT INTO airport_map (map_id, airport_id, map_name, map_type, map_version, coordinate_reference_system, map_status) VALUES
    (1, 1, 'DFW Airfield Radar Layout (Map 1)', 'AIRPORT_LAYOUT', '2.0', 'SCREEN_PIXELS_1000x1000', 'ACTIVE'),
    (2, 3, 'BOM Airfield Radar Layout (Map 2)', 'AIRPORT_LAYOUT', '2.0', 'SCREEN_PIXELS_1000x1000', 'ACTIVE');

    INSERT INTO map_feature (feature_id, map_id, feature_type, feature_name, pos_x, pos_y) VALUES
    (1, 1, 'WAYPOINT', 'WP-101 (Apron North)', 125, 120),
    (2, 1, 'WAYPOINT', 'WP-102 (Taxiway Alpha)', 125, 200),
    (3, 1, 'WAYPOINT', 'WP-103 (Taxiway Bravo)', 125, 500),
    (4, 1, 'WAYPOINT', 'WP-104 (Apron South)', 125, 700),
    (5, 1, 'WAYPOINT', 'WP-201 (Mid Kilo)', 300, 200),
    (6, 1, 'WAYPOINT', 'WP-202 (Intersection)', 412, 480),
    (7, 1, 'WAYPOINT', 'WP-301 (Runway 1 Threshold)', 600, 0),
    (8, 1, 'WAYPOINT', 'WP-302 (Runway 2 End)', 1000, 300),
    (9, 1, 'WAYPOINT', 'WP-303 (Runway 3 End)', 1000, 0),
    (10, 2, 'WAYPOINT', 'WP-B1 (Apron East)', 800, 600),
    (11, 2, 'WAYPOINT', 'WP-B2 (Taxiway Echo)', 800, 400),
    (12, 2, 'WAYPOINT', 'WP-B3 (Taxiway Sierra)', 170, 400),
    (13, 2, 'WAYPOINT', 'WP-B4 (Runway 9 Threshold)', 100, 200),
    (14, 2, 'WAYPOINT', 'WP-B5 (Runway 10 Threshold)', 200, 500),
    (15, 2, 'WAYPOINT', 'WP-B6 (Taxiway Bravo Mid)', 800, 200),
    (16, 2, 'WAYPOINT', 'WP-B7 (East Boundary 1)', 995, 500),
    (17, 2, 'WAYPOINT', 'WP-B8 (East Boundary 2)', 995, 200);

    INSERT INTO runway_assignment (assignment_id, operation_id, direction_id, assignment_datetime, assignment_status, assigned_by, remarks) VALUES
    (1, 1, 4, '2026-10-15 05:15:00', 'CONFIRMED', 'OPERATOR_ALPHA', 'Assigned central parallel runway 35C'),
    (2, 2, 12, '2026-10-15 07:45:00', 'CONFIRMED', 'OPERATOR_BETA', 'East-west runway approach BOM 09/27');
    """)

    conn.commit()
    _repair_sqlite_seed_data(conn)
    conn.commit()
    conn.close()
    print("[AURORA DB] Local SQLite relational database ready.")


def _repair_sqlite_seed_data(conn):
    """Backfill published demo infrastructure/certificates without overwriting data."""
    cur = conn.cursor()
    terminals = [
        ("DFW", "Terminal A (American Hub)", "DOMESTIC"),
        ("DFW", "Terminal D (International)", "INTERNATIONAL"),
        ("DFW", "Terminal E (Regional & Cargo)", "CARGO"),
        ("LHR", "Terminal 2 (The Queen's Terminal)", "INTERNATIONAL"),
        ("LHR", "Terminal 5 (British Flagship)", "INTERNATIONAL"),
        ("BOM", "Terminal 2 (Chhatrapati T2)", "INTERNATIONAL"),
        ("BOM", "Terminal 1 (Santa Cruz Domestic)", "DOMESTIC"),
    ]
    for iata, name, terminal_type in terminals:
        cur.execute("""INSERT INTO terminal (airport_id, terminal_name, terminal_type)
            SELECT airport_id, ?, ? FROM airport WHERE iata_code = ?
            AND NOT EXISTS (SELECT 1 FROM terminal t JOIN airport a ON a.airport_id=t.airport_id
                            WHERE a.iata_code=? AND t.terminal_name=?)""",
                    (name, terminal_type, iata, iata, name))

    stands = [
        ("DFW", "Terminal D (International)", "Gate D18", "SUPER"),
        ("DFW", "Terminal A (American Hub)", "Gate A24", "HEAVY"),
        ("DFW", "Terminal E (Regional & Cargo)", "Stand E02", "MEDIUM"),
        ("LHR", "Terminal 2 (The Queen's Terminal)", "Gate A10", "HEAVY"),
        ("LHR", "Terminal 5 (British Flagship)", "Gate 504", "SUPER"),
        ("BOM", "Terminal 2 (Chhatrapati T2)", "Gate 42", "HEAVY"),
        ("BOM", "Terminal 1 (Santa Cruz Domestic)", "Stand D03", "MEDIUM"),
    ]
    for iata, terminal_name, code, size in stands:
        cur.execute("""INSERT INTO aircraft_stand (airport_id, terminal_id, stand_code, max_aircraft_size)
            SELECT a.airport_id, t.terminal_id, ?, ? FROM airport a
            LEFT JOIN terminal t ON t.airport_id=a.airport_id AND t.terminal_name=?
            WHERE a.iata_code=? AND NOT EXISTS (
                SELECT 1 FROM aircraft_stand s JOIN airport ap ON ap.airport_id=s.airport_id
                WHERE ap.iata_code=? AND s.stand_code=?)""",
                    (code, size, terminal_name, iata, iata, code))

    # Match the checked-in MySQL seed matrix by aircraft model, airport, and
    # physical runway designation. INSERT OR IGNORE leaves existing decisions intact.
    runway_ids = list(range(1, 8))
    runway_specs = [("DFW", "17L/35R"), ("DFW", "17C/35C"), ("DFW", "18R/36L"),
                    ("LHR", "09L/27R"), ("LHR", "09R/27L"), ("BOM", "09/27"), ("BOM", "14/32")]
    eligible = {
        "A320neo": {runway: (1, 1) for runway in runway_ids},
        "B737-800": {runway: (1, 1) for runway in runway_ids},
        "B777-300ER": {runway: ((0, 0) if runway in (1, 7) else (1, 1)) for runway in runway_ids},
        "A350-900": {runway: ((0, 0) if runway in (1, 7) else (1, 1)) for runway in runway_ids},
        "ATR 72-600": {runway: (1, 1) for runway in runway_ids},
        "CRJ-900": {runway: (1, 1) for runway in runway_ids},
    }
    remarks = {
        ("B777-300ER", 1): "INELIGIBLE: runway shorter than the seeded 3200m requirement",
        ("B777-300ER", 7): "INELIGIBLE: BOM secondary runway is too short for B777-300ER",
        ("A350-900", 1): "INELIGIBLE: DFW 17L/35R below A350 recommended field length",
        ("A350-900", 7): "INELIGIBLE: BOM 14/32 clearance constraint",
    }
    for type_id, model in enumerate(eligible, start=1):
        for runway_id, (iata, designation) in enumerate(runway_specs, start=1):
            land, takeoff = eligible[model][runway_id]
            note = remarks.get((model, runway_id), f"Seeded compatibility for {iata} {designation}")
            cur.execute("""INSERT OR IGNORE INTO aircraft_runway_compatibility
                (type_id, runway_id, landing_eligible, takeoff_eligible, remarks)
                SELECT act.type_id, rw.runway_id, ?, ?, ? FROM aircraft_type act
                JOIN runway rw ON rw.runway_designation=? JOIN airport ap ON ap.airport_id=rw.airport_id
                WHERE act.model=? AND ap.iata_code=?""",
                        (land, takeoff, note, designation, model, iata))
