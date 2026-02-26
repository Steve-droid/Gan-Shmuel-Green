from flask import Flask, request, jsonify
from datetime import datetime
from db import get_db, test_connection
from typing import List, Optional, Literal
import uuid
from datetime import datetime, timezone
from db import transactions

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

    required = ["direction", "truck", "containers", "weight", "unit", "force", "produce"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields"}), 400

    direction = str(data["direction"]).lower().strip()
    if direction not in ("in", "out", "none"):
        return jsonify({"error": "direction must be one of: in, out, none"}), 400

    truck = str(data["truck"]).strip()
    produce = str(data["produce"]).strip()
    force = bool(data["force"])
    
    try:
        bruto_kg = to_kg_int(int(data["weight"]), str(data["unit"]))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid weight/unit"}), 400
    

    containers_list = parse_containers(data["containers"])
    containers_csv = ",".join(containers_list)

    now = datetime.now(timezone.utc)  
    #return the most recent version of the truck
    def last_tx_for_truck():
        if truck == "na":
            return None
        return (
            transactions.query
            .filter_by(truck=truck)
            .order_by(transactions.datetime.desc(), transactions.id.desc())
            .first()
        )
    
    #Returns the truck's last IN, only if it is still "open".
    def last_open_in_for_truck():
        if truck == "na":
            return None

        last_in = (
            transactions.query
            .filter_by(truck=truck, direction="in")
            .order_by(transactions.datetime.desc(), transactions.id.desc())
            .first()
        )
        if not last_in:
            return None

        out_exists = (
            transactions.query
            .filter_by(truck=truck, direction="out", session_id=last_in.session_id)
            .first()
        )
        if out_exists:
            return None
        return last_in
    
    last_tx = last_tx_for_truck()
    open_in = last_open_in_for_truck()

    #none after in not allow
    if direction == "none" and open_in is not None:
        return jsonify({"error": "none after in is not allowed"}), 400

    # out בלי in -> error
    if direction == "out" and open_in is None:
        return jsonify({"error": "out without an in is not allowed"}), 400

    # in אחרי in (כלומר יש open_in) -> error או force overwrite
    if direction == "in" and open_in is not None and not force:
        return jsonify({"error": "in followed by in requires force=true"}), 400

    # out אחרי out -> error או force overwrite
    if direction == "out" and last_tx is not None and last_tx.direction == "out" and not force:
        return jsonify({"error": "out followed by out requires force=true"}), 400


    
    # TODO: Implement logic
    # - Validate direction (in/out/none) 
    # - Check session constraints (in/in, out/out, out without in)
    # - Generate/return session id
    # - Store in `transactions` table
    
    return jsonify({
        'id': 'session_001',
        'truck': data['truck'],
        'bruto': data['weight']
        #, 'truckTara': None,   
        # 'neto': None
    }), 201


@app.get('/weight')
def get_weights():
    """Query weights with filters"""
    from_dt = request.args.get('from')  # yyyymmddhhmmss
    to_dt = request.args.get('to')      # yyyymmddhhmmss
    filter_dir = request.args.get('filter', 'in,out,none')
    
    # TODO: Implement logic
    # - Query `transactions` table for weights in date range
    # - Filter by direction
    # - Return array of weight records
    
    return jsonify([]), 200


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
    """Get item (truck or container) details"""
    from_dt = request.args.get('from')
    to_dt = request.args.get('to')
    
    # TODO: Implement logic
    # - Query `transactions` and `containers_registered` tables
    # - Return tara and sessions
    
    return jsonify({'id': item_id, 'tara': None, 'sessions': []}), 200


@app.get('/health')
def health_check():
    """Health check - verify DB connection"""
    
    if test_connection():
        return jsonify({'status': 'OK'}), 200
    else:
        return jsonify({'status': 'Failure'}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
