from flask import Flask, request, jsonify
from datetime import datetime
from db import get_db, test_connection
from typing import List, Optional, Literal
import uuid
from datetime import datetime, timezone
from typing import Literal
import os
import csv
import json as json_module
from db import (
    get_db,
    test_connection,
    insert_transaction,
    update_transaction,
    get_last_transaction_for_truck,
    get_last_open_in_for_truck,
    get_in_transaction_for_session,
    get_containers_tara,
    upsert_containers,
    recalculate_pending_netos,
    get_item_type,
    get_container_tara_kg,
    get_truck_last_tara_kg,
    get_sessions_for_truck,
    get_sessions_for_container,
)
from entity_models import Transaction, Container

app = Flask(__name__)

Direction = Literal["in", "out", "none"]
LBS_TO_KG = 0.45359237
IN_FOLDER = os.getenv("IN_FOLDER", "/app/in")

#check if kg / lbs if lbs convert to kg
def to_kg_int(weight: int, unit: str) -> int:
    """Convert input weight to integer KG (rounded)."""
    unit = unit.lower().strip()
    if unit == "kg":
        return int(weight)
    if unit == "lbs":
        return int(round(float(weight) * LBS_TO_KG))
    raise ValueError("unit must be 'kg' or 'lbs'")

#parse containrs to list that we can go over it
def parse_containers(value) -> list[str]:
    """Accept 'c1,c2' or ['c1','c2'] and return clean list."""
    if value is None:
        return []
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value).split(",")
    return [c.strip() for c in raw if str(c).strip()]




@app.post('/weight')
def post_weight():
    """Record a weight measurement"""
    data = request.get_json(silent=True) or {}

    def validate_post_weight_input(data):
        for field in ("direction", "weight", "unit"):
                if field not in data:
                    return jsonify({"error": f"Missing required field: {field}"}), 400

        direction = str(data["direction"]).lower().strip()
        if direction not in ("in", "out", "none"):
            return jsonify({"error": "direction must be one of: in, out, none"}), 400

        if direction != "none":
            if "truck" not in data:
                return jsonify({"error": f"Missing required field: truck"}), 400
            if direction == "in":
                for field in ("produce", "containers"):
                    if field not in data:
                        return jsonify({"error": f"For a truck going in, Missing at least one required field: {field}"}), 400

    err = validate_post_weight_input(data)
    if err:
        return err
    direction = str(data["direction"]).lower().strip()
    weight = data["weight"]
    unit = str(data["unit"]).lower().strip()
    truck = str(data.get("truck", "na")).strip()
    produce = str(data.get("produce", "na")).strip()
    force = bool(data.get("force", False))
    
    try:
        bruto_kg = to_kg_int(int(data["weight"]), str(data["unit"]))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid weight/unit"}), 400
    

    containers_list = parse_containers(data.get("containers"))
    containers_csv = ",".join(containers_list)

    now = datetime.now(timezone.utc)  


    def validate_session_constraints(direction, open_in, last_tx, force):
        #none after in not allowed
        if direction == "none" and open_in is not None:
            return jsonify({"error": "none after in is not allowed"}), 400

        # out without an in -> error, unless force-overwriting a previous out
        if direction == "out" and open_in is None:
            if not (force and last_tx is not None and last_tx.direction == "out"):
                return jsonify({"error": "out without an in is not allowed"}), 400

        # in followed by in -> error or force overwrite
        if direction == "in" and open_in is not None and not force:
            return jsonify({"error": "in followed by in requires force=true"}), 400

        # out followed by out -> error or force overwrite
        if direction == "out" and last_tx is not None and last_tx.direction == "out" and not force:
            return jsonify({"error": "out followed by out requires force=true"}), 400   


    # last_tx = last_tx_for_truck()
    # open_in = last_open_in_for_truck() 
    
    # Fetch truck state directly from DB
    last_tx = get_last_transaction_for_truck(truck) if truck != "na" else None
    open_in = get_last_open_in_for_truck(truck) if truck != "na" else None
    
    err = validate_session_constraints(direction, open_in, last_tx, force)
    if err:
        return err

    if direction == "in":
        if open_in and force:
            # Overwrite existing "in" row in place with same id and sessionId, new data
            update_transaction(open_in.id, {
                'datetime': now,
                'truck': truck,
                'containers': ','.join(containers_list),
                'bruto': bruto_kg,
                'produce': produce,
            })
            return jsonify({
                'sessionId': open_in.session_id,
                'truck': truck,
                'bruto': bruto_kg
            }), 201

        else:
            new_tx = Transaction(
            datetime=now,
            direction=direction,
            truck=truck,
            containers=containers_list,
            bruto=bruto_kg,
            truck_tara=None,
            neto=None,
            produce=produce,
            session_id=None,
            )

            tx_id = insert_transaction(new_tx)
            # sessionId = own transaction id (anchor for the paired "out")
            update_transaction(tx_id, {'sessionId': tx_id})
            return jsonify({
                'sessionId': tx_id,
                'truck': truck,
                'bruto': bruto_kg
            }), 201

    elif direction == "out":
        # When force-overwriting a previous "out", open_in is None — fetch original "in" from DB
        original_in = open_in if open_in is not None else get_in_transaction_for_session(last_tx.session_id)
        session_id = original_in.session_id
        truck_tara = bruto_kg  # the "out" measurement is the truck's tara (empty weight)

        if bruto_kg >= original_in.bruto:
            return jsonify({"error": f"Out weight ({bruto_kg} kg) must be less than in weight ({original_in.bruto} kg) for this session"}), 400

        # Containers and produce are not recorded on exit
        containers_list = []
        produce = "na"

        container_taras = get_containers_tara(original_in.containers or [])
        if None in container_taras.values():
            neto = "na"
        else:
            neto = original_in.bruto - truck_tara - sum(container_taras.values())

        if last_tx and last_tx.direction == "out" and force:
            # Overwrite existing "out" row in place with same id and sessionId, new data
            update_transaction(last_tx.id, {
                'datetime': now,
                'truck': truck,
                'containers': '',
                'bruto': bruto_kg,
                'truckTara': truck_tara,
                'neto': neto if isinstance(neto, int) else None,
                'produce': 'na',
            })
        else:
            new_tx = Transaction(
                datetime=now,
                direction=direction,
                truck=truck,
                containers=containers_list,
                bruto=bruto_kg,
                truck_tara=truck_tara,
                neto=neto if isinstance(neto, int) else None,
                produce=produce,
                session_id=session_id,
            )
            insert_transaction(new_tx)
        return jsonify({
            'sessionId': session_id,
            'truck': truck,
            'bruto': bruto_kg,
            'truckTara': truck_tara,
            'neto': neto
        }), 201

    else:  # direction == "none"
        new_tx = Transaction(
            datetime=now,
            direction=direction,
            truck=truck,
            containers=containers_list,
            bruto=bruto_kg,
            truck_tara=None,
            neto=None,
            produce=produce,
            session_id=None,
        )
        tx_id = insert_transaction(new_tx)
        return jsonify({
            'sessionId': tx_id,
            'truck': truck,
            'bruto': bruto_kg
        }), 201


@app.get('/weight')
def get_weights():
    # --- 1. SET DEFAULTS & GET PARAMS ---
    now = datetime.now()
    now_str = now.strftime('%Y%m%d%H%M%S')
    today_midnight = now.strftime('%Y%m%d000000')


    # Extract parameters from the URL ---
    t1 = request.args.get("from", today_midnight)
    t2 = request.args.get("to", now_str)
    f = request.args.get("filter", "in,out,none")

    # --- 2. VALIDATE DATE FORMATS (Edge Case: Invalid Format) ---
    try:
        t1_dt = datetime.strptime(t1, '%Y%m%d%H%M%S')
        t2_dt = datetime.strptime(t2, '%Y%m%d%H%M%S')
    except ValueError:
        return jsonify({"error": "Invalid date format. Please use yyyymmddhhmmss"}), 400

    # --- 3. VALIDATE DATE LOGIC (Edge Case: Reversed Ranges) ---
    if t1_dt > t2_dt:
        return jsonify({"error": "Invalid range: 'from' date cannot be later than 'to' date"}), 400

    # --- 4. VALIDATE FUTURE DATES (Edge Case: Range in the future) ---
    if t1_dt > now:
        return jsonify({"message": "No sessions recorded for this future time range"}), 200
    
    # If t2 is in the future, we cap it at 'now' so the query is efficient
    if t2_dt > now:
        t2 = now_str

    # --- 5. VALIDATE FILTERS (Edge Case: Invalid/Empty Values) ---
    allowed_filters = {"in", "out", "none"}
    
    # Check if empty filter (Edge Case: Empty Filter)
    if not f.strip():
        f_list = list(allowed_filters) # Default back to all types
    else:
        # Convert string to list and clean whitespace/lowercase
        f_list = [x.strip().lower() for x in f.split(',') if x.strip()]
        
        # Validate values (Edge Case: Invalid Filter Values)
        for val in f_list:
            if val not in allowed_filters:
                return jsonify({"error": f"Invalid filter: '{val}'. Use 'in', 'out', or 'none'"}), 400

    # --- 6. DATABASE EXECUTION ---
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # 2. Create the correct number of %s placeholders
        # Example: if f_list is ['in', 'out'], this creates "%s, %s"
        placeholders = ', '.join(['%s'] * len(f_list))

        # 3. Build the query with the dynamic placeholders
        query = f"""
            SELECT id, sessionId, direction, bruto, neto, produce, containers
            FROM transactions
            WHERE datetime BETWEEN %s AND %s
            AND direction IN ({placeholders})
        """
        
        # 4. Flatten all arguments into one tuple: (t1, t2, 'in', 'out'...)
        params = [t1, t2] + f_list
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        if not results:
            return jsonify([]), 200

        # --- THE MODIFICATION: FORMATTING EACH OBJECT ---
        formatted_response = []
        for row in results:
            formatted_response.append({
                "sessionId": row["sessionId"],
                "direction": row["direction"],
                "bruto": row["bruto"],
                "neto": row["neto"] if row["neto"] is not None else "na",
                "produce": row["produce"],
                "containers": row["containers"].split(",") if row["containers"] else []
            })

        cursor.close()
        conn.close()
        return jsonify(formatted_response), 200

    except Exception as e:
        print(f"DEBUG ERROR: {e}")
        return jsonify({"error": "Internal database error"}), 500


@app.get('/session/<id>')
def get_session(id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    try:
        # מביאים את כל הרשומות של אותו session
        cursor.execute("""
            SELECT *
            FROM transactions
            WHERE sessionId = %s
            ORDER BY datetime ASC, id ASC
        """, (id,))
        rows = cursor.fetchall()

        if not rows:
            return jsonify({
                "status": "error",
                "message": f"Session ID {id} was not found."
            }), 404

        in_row = None
        out_row = None

        for row in rows:
            if row.get("direction") == "in" and in_row is None:
                in_row = row
            elif row.get("direction") == "out" and out_row is None:
                out_row = row

        # אם אין in ניקח את הרשומה הראשונה כבסיס
        base_row = in_row if in_row else rows[0]

        response_data = {
            "id": base_row.get("sessionId"),
            "truck": base_row.get("truck") or "na",
            "bruto": base_row.get("bruto"),
            "produce": base_row.get("produce") or "na"
        }

        # אם יש OUT, נוסיף גם את המידע שלו
        if out_row:
            response_data["truckTara"] = out_row.get("truckTara")

            if out_row.get("neto") is None:
                response_data["neto"] = "na"
            else:
                response_data["neto"] = out_row.get("neto")


        return jsonify(response_data), 200

    finally:
        cursor.close()
        conn.close()


def _parse_batch_file(filepath: str) -> list[Container]:
    """Parse a batch file and return a list of Container objects."""
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".json":
        with open(filepath, "r") as f:
            rows = json_module.load(f)
        if not isinstance(rows, list):
            raise ValueError("JSON file must contain a top-level array")
        result = []
        for row in rows:
            if "id" not in row or "weight" not in row or "unit" not in row:
                raise ValueError(f"JSON row missing fields: {row}")
            unit = str(row["unit"]).lower().strip()
            if unit not in ("kg", "lbs"):
                raise ValueError(f"Invalid unit '{unit}' in row: {row}")
            result.append(Container(container_id=str(row["id"]), weight=int(row["weight"]), unit=unit))
        return result

    elif ext == ".csv":
        result = []
        with open(filepath, "r", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header is None:
                return []
            if len(header) < 2:
                raise ValueError("CSV must have at least 2 columns: id and unit (kg/lbs)")
            unit = header[1].strip().lower()
            if unit not in ("kg", "lbs"):
                raise ValueError(f"CSV second column header must be 'kg' or 'lbs', got '{header[1]}'")
            for row in reader:
                if len(row) < 2 or not row[0].strip():
                    continue
                result.append(Container(container_id=row[0].strip(), weight=int(row[1].strip()), unit=unit))
        return result

    else:
        raise ValueError(f"Unsupported file format '{ext}'. Use .csv or .json")


@app.post('/batch-weight')
def post_batch_weight():
    """Upload batch container tara weights from a file in /in folder"""
    data = request.get_json(silent=True) or {}
    filename = data.get("file") or request.form.get("file")

    if not filename:
        return jsonify({"error": "Missing 'file' parameter"}), 400

    filepath = os.path.join(IN_FOLDER, filename) #might need to change when we change to volume?
    if not os.path.exists(filepath):
        return jsonify({"error": f"File '{filename}' not found in /in folder"}), 404

    try:
        rows = _parse_batch_file(filepath)
    except (ValueError, KeyError) as e:
        return jsonify({"error": f"Failed to parse file: {e}"}), 400

    upsert_containers(rows)
    resolved = recalculate_pending_netos()
    msg = f"Loaded {len(rows)} containers"
    if resolved:
        msg += f", resolved neto for {resolved} session(s)"
    return jsonify({"message": msg}), 201


@app.get('/unknown')
def get_unknown():
    """
    Returns a list of container IDs that have appeared in transactions 
    but do not have a registered weight in the system.
    """
    conn = get_db()
    try:
        cursor = conn.cursor()
        
        # 1. Fetch all 'seen' containers from transactions
        # We only need the 'containers' column
        cursor.execute("SELECT containers FROM transactions")
        transaction_rows = cursor.fetchall()
        
        # 2. Fetch all 'known' container IDs from registration
        # In your DB, the table name is 'containers_registered'
        cursor.execute("SELECT container_id FROM containers_registered")
        registered_rows = cursor.fetchall()

        # 3. Create a set of Known IDs (the 'Registry')
        # We strip and uppercase to handle any messy manual entries
        registered_ids = {row[0].strip().upper() for row in registered_rows if row[0]}
        
        # 4. Create a set of Seen IDs (from the scale)
        seen_ids = set()
        for row in transaction_rows:
            # Skip empty rows (Edge Case: Scale record with no containers)
            if row[0]:
                # Split the string (e.g., "C-1,C-2") and clean each ID
                parts = row[0].split(',')
                for p in parts:
                    clean_id = p.strip().upper()
                    if clean_id: # Avoid adding empty strings if someone typed "C-1, ,C-2"
                        seen_ids.add(clean_id)
        
        # 5. Logic: Find IDs in 'Seen' that are NOT in 'Registered'
        unknown_diff = seen_ids - registered_ids
        
        # 6. Return as a clean JSON list
        # We convert the set back to a sorted list for consistent output
        return jsonify(sorted(list(unknown_diff))), 200

    except Exception as e:
        # DevOps/Backend safety: Always log or return the error so we aren't flying blind
        return jsonify({"error": f"Database error: {str(e)}"}), 500
        
    finally:
        # Closing the 'tap' to prevent memory leaks and database hanging
        cursor.close()
        conn.close()


@app.get('/item/<item_id>')
def get_item(item_id):
    now = datetime.now()
    default_t2 = now.strftime('%Y%m%d%H%M%S')
    default_t1 = now.strftime('%Y%m') + '01000000'  # 1st of month 00:00:00

    t1 = request.args.get('from', default_t1)
    t2 = request.args.get('to', default_t2)

    # validate format
    try:
        t1_dt = datetime.strptime(t1, '%Y%m%d%H%M%S')
        t2_dt = datetime.strptime(t2, '%Y%m%d%H%M%S')
    except ValueError:
        return jsonify({"error": "Invalid date format. Please use yyyymmddhhmmss"}), 400

    if t1_dt > t2_dt:
        return jsonify({"error": "Invalid range: 'from' date cannot be later than 'to' date"}), 400

    # decide item type (truck/container) or 404
    item_type = get_item_type(item_id)
    if item_type is None:
        return jsonify({"error": "Item not found"}), 404

    if item_type == "container":
        tara = get_container_tara_kg(item_id)
        sessions = get_sessions_for_container(item_id, t1, t2)
    else:  # truck
        tara = get_truck_last_tara_kg(item_id)
        sessions = get_sessions_for_truck(item_id, t1, t2)

    return jsonify({
        "id": item_id,
        "tara": tara if tara is not None else "na",
        "sessions": sessions
    }), 200


@app.get('/health')
def health_check():
    """Health check - verify DB connection"""
    
    if test_connection():
        return jsonify({'status': 'OK'}), 200
    else:
        return jsonify({'status': 'Failure'}), 500
    




if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
