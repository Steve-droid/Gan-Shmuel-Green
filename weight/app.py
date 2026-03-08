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
    get_containers_tara,
    upsert_containers,
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

        # out without an in -> error
        if direction == "out" and open_in is None:
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
                'id': open_in.id,
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
            update_transaction(tx_id, {'sessionId': tx_id})
            return jsonify({
                'id': tx_id,
                'truck': truck,
                'bruto': bruto_kg
            }), 201

    elif direction == "out":
        session_id = open_in.session_id
        truck_tara = bruto_kg  # the "out" measurement is the truck's tara (empty weight)

        container_taras = get_containers_tara(open_in.containers or [])
        if None in container_taras.values():
            neto = "na"
        else:
            neto = open_in.bruto - truck_tara - sum(container_taras.values())

        if last_tx and last_tx.direction == "out" and force:
            # Overwrite existing "out" row in place with same id and sessionId, new data
            update_transaction(last_tx.id, {
                'datetime': now,
                'truck': truck,
                'containers': ','.join(containers_list),
                'bruto': bruto_kg,
                'truckTara': truck_tara,
                'neto': neto if isinstance(neto, int) else None,
                'produce': produce,
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
            'id': session_id,
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
            'id': tx_id,
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
            SELECT id, direction, bruto, neto, produce, containers 
            FROM transactions 
            WHERE datetime BETWEEN %s AND %s 
            AND direction IN ({placeholders})
        """
        
        # 4. Flatten all arguments into one tuple: (t1, t2, 'in', 'out'...)
        params = [t1, t2] + f_list
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        if not results:
            return jsonify({
                "message": f"No weighing sessions exist for the requested time range ({t1} to {t2})"
            }), 200

        # --- THE MODIFICATION: FORMATTING EACH OBJECT ---
        formatted_response = []
        for row in results:
            formatted_response.append({
                "id": row["id"],
                "direction": row["direction"],
                "bruto": row["bruto"], # Assumed stored as KG
                # Handle "na" for neto if tara was unknown (NULL in DB)
                "neto": row["neto"] if row["neto"] is not None else "na",
                "produce": row["produce"],
                # Convert "c1,c2" string into list ["c1", "c2"]
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
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Ensure your query explicitly asks for all needed columns
        cursor.execute("SELECT * FROM transactions WHERE id=%s", (id,))
        row = cursor.fetchone()

        if not row:
            return jsonify({
                "status": "error",
                "message": f"Session ID {id} was not found."
            }), 404

        # 1. Build the Base Response safely
        response_data = {
            "id": row.get('id'),
            "truck": row.get('truck') if row.get('truck') else "na",
            "bruto": row.get('bruto'),
            # Safely handle datetime objects
            "datetime": row['datetime'].strftime("%a, %d %b %Y %H:%M:%S GMT") if row.get('datetime') else "na"
        }

        # 2. Logic for 'OUT' Sessions
        if row.get('direction') == "out":
            tara = row.get('truckTara')
            
            # Check for missing/zero Tara
            if not tara or tara == 0:
                response_data.update({"truckTara": "na", "neto": "na"})
                return jsonify(response_data), 200

            # 3. Process Containers safely
            # Using .get('containers') avoids the KeyError if the key is missing
            container_str = str(row.get('containers')) if row.get('containers') else ""
            container_ids = [c.strip() for c in container_str.split(",") if c.strip()]
            
            total_container_weight = 0
            all_weights_known = True

            for c_id in container_ids:
                cursor.execute("SELECT weight FROM containers_registered WHERE container_id=%s", (c_id,))
                c_row = cursor.fetchone()
                
                if c_row and c_row.get('weight') is not None:
                    total_container_weight += c_row['weight']
                else:
                    all_weights_known = False
                    break
            
            if all_weights_known:
                response_data["neto"] = (row.get('bruto') or 0) - tara - total_container_weight
            else:
                response_data["neto"] = "na"
                
            response_data["truckTara"] = tara

        return jsonify(response_data), 200

    finally:
        cursor.close()
        conn.close()


IN_FOLDER = os.environ['IN_FOLDER']


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
    return jsonify({"message": f"Loaded {len(rows)} containers"}), 201


@app.get('/unknown')
def get_unknown():
    """Get containers with unknown weight"""
    
    # TODO: Implement logic
    # - Query `containers_registered` for missing container IDs
    # - Cross-reference with `transactions.containers`
    # - Return array of container ids
    
    return jsonify([]), 200


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
