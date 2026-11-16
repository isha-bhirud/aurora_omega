"""
AURORA - Manual Runway Assignment Validation Engine (Python)
Validates candidate runway direction selections against database integrity rules.
This provides deterministic validation with clear reasons, NEVER automatic allocation.
"""

from db import fetch_one, fetch_all

class ValidationResult:
    def __init__(self, is_valid, reason, details=None):
        self.is_valid = is_valid
        self.reason = reason
        self.details = details or {}

    def __repr__(self):
        status = "PASSED" if self.is_valid else "FAILED"
        return f"<ValidationResult [{status}]: {self.reason}>"

def validate_runway_assignment(operation_id, direction_id):
    """
    Validates whether a flight operation can legally be assigned to a runway direction.
    Enforces academic DBMS constraints:
      A. Airport alignment
      B. Direction operational permissions (Landing vs Takeoff)
      C. Physical runway status (OPEN vs CLOSED/RESTRICTED)
      D. Aircraft Type compatibility matrix
      E. Active restriction & maintenance intervals
    """
    # 1. Fetch operation details
    op_query = """
    SELECT 
       fo.operation_id,
       fo.airport_id AS operation_airport_id,
       fo.operation_type,
       fo.scheduled_datetime,
       fo.operation_status,
       f.flight_number,
       f.aircraft_id,
       ac.registration_number,
       ac.type_id,
       act.model AS aircraft_model,
       act.aircraft_category,
       ap.iata_code AS airport_code,
       ap.airport_name
     FROM flight_operation fo
     JOIN flight f ON fo.flight_id = f.flight_id
     JOIN aircraft ac ON f.aircraft_id = ac.aircraft_id
     JOIN aircraft_type act ON ac.type_id = act.type_id
     JOIN airport ap ON fo.airport_id = ap.airport_id
     WHERE fo.operation_id = %s
    """
    operation = fetch_one(op_query, (operation_id,))
    if not operation:
        return ValidationResult(False, f"Operation ID {operation_id} not found in database.")

    # 2. Fetch direction details
    dir_query = """
    SELECT 
       rd.direction_id,
       rd.designation AS direction_designation,
       rd.heading,
       rd.landing_permitted,
       rd.takeoff_permitted,
       rd.ils_available,
       rw.runway_id,
       rw.airport_id AS runway_airport_id,
       rw.runway_designation,
       rw.runway_status,
       rw.runway_length,
       rw.surface_type,
       ap.iata_code AS runway_airport_code
     FROM runway_direction rd
     JOIN runway rw ON rd.runway_id = rw.runway_id
     JOIN airport ap ON rw.airport_id = ap.airport_id
     WHERE rd.direction_id = %s
    """
    direction = fetch_one(dir_query, (direction_id,))
    if not direction:
        return ValidationResult(False, f"Runway Direction ID {direction_id} not found in database.")

    # RULE A: Airport Mismatch Check
    if operation["operation_airport_id"] != direction["runway_airport_id"]:
        return ValidationResult(
            False,
            f"AIRPORT MISMATCH: Operation {operation['flight_number']} is at {operation['airport_code']}, "
            f"but direction {direction['direction_designation']} belongs to {direction['runway_airport_code']}.",
            {"operation_airport": operation["airport_code"], "runway_airport": direction["runway_airport_code"]}
        )

    # RULE B: Operational Permission Check (Landing vs Takeoff)
    op_type = operation["operation_type"]
    if op_type == "LANDING" and not direction["landing_permitted"]:
        return ValidationResult(
            False,
            f"DIRECTION RESTRICTION: Direction {direction['direction_designation']} does NOT permit LANDING operations.",
            {"operation_type": op_type, "landing_permitted": direction["landing_permitted"]}
        )
    if op_type == "TAKEOFF" and not direction["takeoff_permitted"]:
        return ValidationResult(
            False,
            f"DIRECTION RESTRICTION: Direction {direction['direction_designation']} does NOT permit TAKEOFF operations.",
            {"operation_type": op_type, "takeoff_permitted": direction["takeoff_permitted"]}
        )

    # RULE C: Physical Runway Operational Status Check
    if direction["runway_status"] != "OPEN":
        return ValidationResult(
            False,
            f"RUNWAY CLOSED/RESTRICTED: Runway {direction['runway_designation']} is currently '{direction['runway_status']}'. "
            f"Assignments are rejected until runway is OPEN.",
            {"runway_status": direction["runway_status"]}
        )

    # RULE D: Aircraft Type & Runway Compatibility Matrix
    compat_query = """
    SELECT landing_eligible, takeoff_eligible, remarks
    FROM aircraft_runway_compatibility
    WHERE type_id = %s AND runway_id = %s
    """
    compat = fetch_one(compat_query, (operation["type_id"], direction["runway_id"]))
    if not compat:
        return ValidationResult(
            False,
            f"COMPATIBILITY UNLISTED: No compatibility certificate exists for {operation['aircraft_model']} "
            f"on runway {direction['runway_designation']}.",
            {"aircraft": operation["aircraft_model"], "runway": direction["runway_designation"]}
        )

    if op_type == "LANDING" and not compat["landing_eligible"]:
        return ValidationResult(
            False,
            f"INCOMPATIBLE AIRFRAME: {operation['aircraft_model']} cannot LAND on {direction['runway_designation']}. "
            f"Note: {compat['remarks'] or 'Length or weight threshold violation.'}",
            {"aircraft": operation["aircraft_model"], "remarks": compat["remarks"]}
        )
    if op_type == "TAKEOFF" and not compat["takeoff_eligible"]:
        return ValidationResult(
            False,
            f"INCOMPATIBLE AIRFRAME: {operation['aircraft_model']} cannot TAKEOFF on {direction['runway_designation']}. "
            f"Note: {compat['remarks'] or 'Length or weight threshold violation.'}",
            {"aircraft": operation["aircraft_model"], "remarks": compat["remarks"]}
        )

    # RULE E: Active Runway Restrictions & Scheduled Maintenance Windows
    sched_time = operation["scheduled_datetime"]
    rest_query = """
    SELECT restriction_id, restriction_type, start_datetime, end_datetime, description
    FROM runway_restriction
    WHERE runway_id = %s
      AND restriction_status IN ('SCHEDULED', 'ACTIVE')
      AND %s BETWEEN start_datetime AND end_datetime
    """
    restriction = fetch_one(rest_query, (direction["runway_id"], sched_time))
    if restriction:
        return ValidationResult(
            False,
            f"RUNWAY RESTRICTION CONFLICT: Active {restriction['restriction_type']} on Runway {direction['runway_designation']}. "
            f"Window: {restriction['start_datetime']} to {restriction['end_datetime']}. "
            f"Details: {restriction['description']}",
            {"restriction": restriction}
        )

    # All checks passed
    return ValidationResult(
        True,
        f"VALIDATION PASSED: Direction {direction['direction_designation']} (Runway {direction['runway_designation']}) "
        f"is fully eligible and certified for {op_type} of {operation['aircraft_model']} "
        f"({operation['registration_number']}) at {operation['airport_code']}.",
        {"operation": operation, "direction": direction}
    )

def validate_manual_input(airport_id, aircraft_name, time_str, weight_tons, runway_vector):
    """
    Validates a manual flight entry and runway selection from the Artos input screen.
    Validates against stored runway direction, compatibility envelope, and active restrictions.
    """
    if not runway_vector:
        return ValidationResult(False, "Please select or enter a runway direction (e.g. 17C, 35R, 09, 27).")

    # Clean input
    clean_vec = str(runway_vector).strip().upper()
    if clean_vec.startswith("RUNWAY "):
        clean_vec = clean_vec.replace("RUNWAY ", "").strip()

    # Look up direction for the airport
    q_dir = """
    SELECT rd.direction_id, rd.designation, rd.takeoff_permitted, rd.landing_permitted,
           rw.runway_id, rw.runway_designation, rw.runway_status, rw.runway_length, rw.airport_id,
           ap.iata_code AS airport_code
    FROM runway_direction rd
    JOIN runway rw ON rd.runway_id = rw.runway_id
    JOIN airport ap ON rw.airport_id = ap.airport_id
    WHERE UPPER(rd.designation) = %s AND rw.airport_id = %s
    """
    direction = fetch_one(q_dir, (clean_vec, airport_id))

    if not direction:
        # Check if user entered physical runway designation like 17L/35R or 09/27
        q_rw = """
        SELECT rd.direction_id, rd.designation, rd.takeoff_permitted, rd.landing_permitted,
               rw.runway_id, rw.runway_designation, rw.runway_status, rw.runway_length, rw.airport_id,
               ap.iata_code AS airport_code
        FROM runway_direction rd
        JOIN runway rw ON rd.runway_id = rw.runway_id
        JOIN airport ap ON rw.airport_id = ap.airport_id
        WHERE UPPER(rw.runway_designation) = %s AND rw.airport_id = %s
        LIMIT 1
        """
        direction = fetch_one(q_rw, (clean_vec, airport_id))

    if not direction:
        # Check if direction exists at another airport
        q_other = """
        SELECT ap.iata_code FROM runway_direction rd
        JOIN runway rw ON rd.runway_id = rw.runway_id
        JOIN airport ap ON rw.airport_id = ap.airport_id
        WHERE UPPER(rd.designation) = %s LIMIT 1
        """
        other = fetch_one(q_other, (clean_vec,))
        if other:
            return ValidationResult(
                False,
                f"AIRPORT MISMATCH: Direction '{clean_vec}' belongs to {other['airport_code']}, not this airport."
            )
        return ValidationResult(
            False,
            f"INVALID VECTOR: Runway vector '{clean_vec}' is not recognized for this airport."
        )

    # Check runway status
    if direction["runway_status"] != "OPEN":
        return ValidationResult(
            False,
            f"RUNWAY {direction['runway_status']}: Runway {direction['runway_designation']} is currently closed/under maintenance."
        )

    # Check takeoff permission (default operation from input screen is departure/takeoff)
    if not direction["takeoff_permitted"]:
        return ValidationResult(
            False,
            f"DIRECTION RESTRICTION: Direction {direction['designation']} has takeoff_permitted = 0 (Landing Only)."
        )

    # Check weight compatibility
    try:
        wt = float(weight_tons)
        # Heavy widebody envelope (e.g. B777 > 220 tons) on short runways (< 3200m)
        if wt > 220 and direction["runway_length"] < 3200:
            return ValidationResult(
                False,
                f"INCOMPATIBLE AIRFRAME: Heavy weight ({wt:.0f}t) exceeds safety threshold for Runway {direction['runway_designation']} (length {direction['runway_length']:.0f}m < 3200m required)."
            )
    except (ValueError, TypeError):
        pass

    # Check maintenance window / restrictions
    # Match time against restrictions (comparing HH:MM:SS with time portion)
    q_rest = """
    SELECT restriction_type, description, start_datetime, end_datetime
    FROM runway_restriction
    WHERE runway_id = %s AND restriction_status IN ('SCHEDULED', 'ACTIVE')
    """
    restrictions = fetch_all(q_rest, (direction["runway_id"],))
    for r in restrictions:
        start_t = str(r["start_datetime"]).split()[-1]
        end_t = str(r["end_datetime"]).split()[-1]
        if start_t <= time_str <= end_t:
            return ValidationResult(
                False,
                f"RUNWAY RESTRICTION CONFLICT: Active {r['restriction_type']} on Runway {direction['runway_designation']} during {time_str} ({start_t} to {end_t})."
            )

    return ValidationResult(
        True,
        f"VALIDATION PASSED: Runway {direction['designation']} ({direction['runway_designation']}) confirmed for {aircraft_name}.",
        {"direction_id": direction["direction_id"], "direction_designation": direction["designation"], "runway_id": direction["runway_id"]}
    )

