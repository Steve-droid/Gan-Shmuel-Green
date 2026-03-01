from flask import Flask, request, jsonify
from datetime import datetime
from db import get_db, test_connection
from typing import List, Optional, Literal
import uuid
from datetime import datetime, timezone
from typing import Literal
from db import (
    get_db,
    test_connection,
    insert_transaction,
    update_transaction,
    get_last_transaction_for_truck,
    get_last_open_in_for_truck,
    get_containers_tara,
    get_item_type,
    get_container_tara_kg,
    get_truck_last_tara_kg,
    get_sessions_for_truck,
    get_sessions_for_container,
    
)
from entity_models import Transaction

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
        query = f"SELECT id, truck, bruto, truckTara, neto, datetime FROM transactions WHERE datetime BETWEEN %s AND %s AND direction IN ({placeholders})"
        
        # 4. Flatten all arguments into one tuple: (t1, t2, 'in', 'out'...)
        params = [t1, t2] + f_list
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        if not results:
            return jsonify({
                "message": f"No weighing sessions exist for the requested time range ({t1} to {t2})"
            }), 200

        cursor.close()
        conn.close()
        return jsonify(results), 200

    except Exception as e:
        print(f"DEBUG ERROR: {e}")
        return jsonify({"error": "Internal database error"}), 500
    
    # 6. Transform raw database rows into a list of dictionaries 
    results = []
    for row in rows:
        record = {
            "id": row[0],
            "truck": row[1],
            "bruto": row[2],
            "truckTara": row[3] or 0,  # Use 0 if the value is NULL/None
            "neto": row[4] or 0,       # Use 0 if the truck hasn't left yet
            "datetime": row[5]
        }
        results.append(record)

    # 7. Send the final JSON response to the user 📤
    return jsonify(results), 200


@app.get('/session/<session_id>')
def get_session(session_id):
    """Get session details"""
    
    # TODO: Implement logic
    # - Query `transactions` table for session
    # - Return session with bruto/neto/truckTara
    
    return jsonify({'id': session_id}), 200


@app.post('/batch-weight')
def post_batch_weight():
    """Upload batch weights from file"""
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    # TODO: Implement logic
    # - Parse CSV or JSON
    # - Extract container_id, weight, unit
    # - Store in `containers_registered` table
    
    return jsonify({'status': 'uploaded'}), 201


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
