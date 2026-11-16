# AURORA — Aircraft & Unified Runway Operations Records Archive
### Artos 2.0 Engine • Relational DBMS Academic Project

AURORA is a database-driven academic aviation management application built with **Python, Pygame, and MySQL 8.0+ / 8.4 LTS**. It builds upon the visual language, radar simulation layouts, and UI heritage of **ARTOS 2.0**, upgrading it into a fully normalized relational database system for managing aircraft, airlines, airports, runway vectors, predefined landing/takeoff schedules, and validated manual runway assignments.

---

## 🛫 Key Architecture & Scope Highlights

- **Desktop Pygame UI (Zero Web / Minimal Dependencies):** Follows the visual aesthetic of the original Artos project—dark cockpit radar theme, green scan grids (`0, 70, 0`), cyan taxiway links (`0, 255, 255`), blue runway vectors (`25, 141, 200`), yellow waypoints (`255, 250, 15`), and tactical flight log feeds.
- **Strict Manual Assignment & Validation (No Automated Allocation):** Landing and takeoff operations have predefined scheduled times. Users manually assign a runway direction vector. The system validates the choice against 5 strict database rules (airport alignment, direction suitability, airframe compatibility, runway open status, and active restriction windows).
- **Relational Integrity & Normalization:** 18 normalized tables (1NF, 2NF, 3NF, BCNF compliant) with InnoDB foreign keys, check constraints, database triggers for automated audit logging, views, and indexes.
- **Credential Safety:** Uses `.env` for database credentials with zero hardcoded passwords.

---

## 🛠️ Prerequisites & Minimal Dependencies

AURORA is intentionally designed with the **least dependencies**:
- **Python 3.10+** (Python 3.12 - 3.14 compatible)
- **MySQL Server 8.0+** (or 8.4 LTS)
- Python packages (only 3 core libraries):
  ```bash
  pip install -r requirements.txt
  ```
  *(Packages: `pygame>=2.5.0`, `mysql-connector-python>=8.0.0` or `pymysql`, `python-dotenv>=1.0.0`)*

---

## 🚀 Quick Setup Guide

### 1. Configure Database Credentials (`.env`)
A default `.env` file is already created. Edit it if your local MySQL settings differ:
```ini
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=aurora_db
```

### 2. Initialize the Database (Schema & Demo Seed)
Run the automated Python database setup script:
```bash
python database/setup_db.py
```
This script connects to your MySQL server, creates `aurora_db`, executes `database/schema.sql` (creating all 18 tables, views, indexes, and triggers), populates `database/seed.sql` with rich demo data (4 airlines, 6 aircraft types, 12 aircraft, 3 airports, 7 runways with 14 bidirectional vectors, 22 flights, 30 operations, and Artos map waypoints), and prints row count verification.

### 3. Launch AURORA
Start the main Pygame multi-view management suite:
```bash
python main.py
```

### 4. (Optional) Run the Modernized Artos Standalone Simulation
To run the original 1000x1000 standalone 2D radar waypoint scope directly against the database:
```bash
# Launch Map 1 (DFW Airport)
python artos_map1.py

# Launch Map 2 (BOM Airport)
python artos_map2.py
```

### 5. Run Automated Integrity Tests
To execute the automated validation rule tests and constraint edge case test suite:
```bash
python tests/test_validation.py
```

---

## 🖥️ Pygame Application Views & Features

The main application features a high-contrast top navigation bar enabling seamless switching across 5 operational views:

### 1. Dashboard (`[1. DASHBOARD]`)
- **Real-Time Database Metrics:** Stat cards showing total aircraft, active aircraft, airports, runways, scheduled operations, and unassigned operations.
- **Flight Schedule Table:** Scrollable upcoming landing and takeoff schedule displaying flight numbers, airlines, station codes, scheduled datetime, assigned runway direction, and operational status.

### 2. Manual Runway Assignment & Validation (`[2. RUNWAY ASSIGNMENT]`)
- **Step 1:** Select a pending/unassigned flight operation from the left table.
- **Step 2:** Select a candidate runway direction vector from the right table.
- **Step 3:** Click **"CHECK VALIDATION RULES"** to test compliance:
  - Validates that the selected direction belongs to the operation's station airport.
  - Validates that landing/takeoff is permitted on that vector.
  - Checks the `AIRCRAFT_RUNWAY_COMPATIBILITY` matrix for airframe MTOW and runway length certification.
  - Verifies the physical runway is currently `OPEN`.
  - Ensures no active `RUNWAY_RESTRICTION` or maintenance window overlaps the scheduled time.
  - Displays a detailed **PASS** or **REJECTION** diagnostic modal with the exact reason!
- **Step 4:** Click **"CONFIRM ASSIGNMENT"** to atomically commit the validated assignment to MySQL. The `assignment_audit` trigger automatically records the operator, timestamp, and vector.
- **Cancel Vector:** Allows clearing an assigned runway vector.

### 3. Artos 2D Radar Scope (`[3. RADAR SCOPE]`)
- Upgraded interactive radar visualization preserving Artos's classic layout:
  - Green radar grid (`0, 70, 0`)
  - Thick blue runway strips (`25, 141, 200`) with runway designation labels
  - Cyan taxiway links (`0, 255, 255`)
  - Red waypoints (`255, 0, 0`) with yellow tags (`255, 250, 15`)
  - Aircraft markers with flight numbers and heading needles
  - Circular Compass HUD with magnetic heading indicator
  - ATC communications message log
  - Clickable aircraft telemetry: displays target MTOW, model, scheduled operation, and assigned vector.
  - Seamless airport scope switching: **Map 1 (DFW Hub)** and **Map 2 (BOM Hub)**.

### 4. Fleet & Infrastructure (`[4. FLEET & AIRPORTS]`)
- Browse registered aircraft, aircraft types (dimensions, passenger capacities, MTOW), airlines, and airport installations.

### 5. DBMS SQL Concepts Demonstrator (`[5. DBMS SQL REPORTS]`)
- Demonstrates core university DBMS syllabus queries with live SQL output:
  - **Outer Anti-Join:** Unassigned flight operations (`LEFT JOIN ... WHERE IS NULL`)
  - **Relational Intersect:** Aircraft-to-Runway certified compatibility matrix
  - **GROUP BY Aggregation:** Airline fleet distribution and active airframe counts
  - **Relational View Integration:** Multi-entity aerodrome infrastructure summaries
  - **Trigger History:** Live audit trail table populated automatically by database triggers

---

## 🗄️ Relational Data Model (18 Tables)

```
AIRLINE ───────────────< AIRCRAFT >───────────── AIRCRAFT_TYPE
   │                         │                         │
   │                         │                         │
   v                         v                         v
FLIGHT ─────────────────< FLIGHT_OPERATION >   AIRCRAFT_RUNWAY_COMPATIBILITY
   │                         │                         │
   v                         v                         v
AIRPORT ───────────────< RUNWAY >──────────────────────┘
   │                         │
   ├─< TAXIWAY               ├─< RUNWAY_DIRECTION ──< RUNWAY_ASSIGNMENT
   ├─< TERMINAL              ├─< RUNWAY_RESTRICTION          │
   ├─< AIRCRAFT_STAND        └─< AIRPORT_OPERATING_HOURS     v
   └─< AIRPORT_MAP ──< MAP_FEATURE                    ASSIGNMENT_AUDIT
```

Full details can be found in:
- [Entity-Relationship Diagram (`docs/ER_DIAGRAM.md`)](file:///c:/Users/ishit/OneDrive/Desktop/Work/AURORA/docs/ER_DIAGRAM.md)
- [Relational Schema & Normalization Proof (`docs/RELATIONAL_SCHEMA.md`)](file:///c:/Users/ishit/OneDrive/Desktop/Work/AURORA/docs/RELATIONAL_SCHEMA.md)
- [Course SQL Query Demonstrations (`database/queries.sql`)](file:///c:/Users/ishit/OneDrive/Desktop/Work/AURORA/database/queries.sql)

---

## 📂 Project Directory Structure

```
AURORA/
├── .env                         # Local MySQL configuration (credentials ignored in git)
├── .env.example                 # Example template for environment setup
├── .gitignore                   # Git exclusion rules
├── requirements.txt             # Lean Python dependencies (pygame, mysql-connector-python, dotenv)
├── README.md                    # This master project documentation
├── main.py                      # Main entry point for the Pygame application
├── app.py                       # Complete Pygame application integrating all 5 views
├── artos_radar.py               # Upgraded Artos 2D radar visualizer module
├── artos_updated.py             # Standalone 1000x1000 Artos simulation reading from MySQL
├── validator.py                 # Manual assignment validation rule engine
├── db.py                        # MySQL connection manager & parameterized query runner
├── ui_components.py             # Reusable Pygame UI widgets (Buttons, Table, Cards, Modal, Compass)
├── database/
│   ├── schema.sql               # MySQL DDL (18 tables, indexes, triggers, views)
│   ├── seed.sql                 # Demonstration seed dataset (airports, flights, waypoints)
│   ├── queries.sql              # DBMS course syllabus SQL demonstration queries
│   └── setup_db.py              # Automated database generator & seed executor
├── docs/
│   ├── ER_DIAGRAM.md            # Mermaid ER diagram and cardinalities
│   └── RELATIONAL_SCHEMA.md     # Relational schema notation, FDs, and normalization
├── tests/
│   └── test_validation.py       # Automated unit & integration tests
└── artos_source/                # Original Artos repository reference
```

---

## 📜 Disclaimer
AURORA is an academic database management project demonstrating relational database concepts, constraints, and manual validation. It is not an operational air traffic control or certified aviation safety application.
