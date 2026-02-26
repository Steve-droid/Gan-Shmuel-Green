from flask import Flask, request, jsonify
from datetime import datetime
from db import get_db, test_connection

app = Flask(__name__)

@app.post('/weight')
def post_weight():
    """Record a weight measurement"""
    data = request.get_json()
    
    # Validate required fields
    required = ['direction', 'truck', 'containers', 'weight', 'unit', 'force', 'produce']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    
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
    # 1. Prepare default time values 
    # We use these if the user doesn't provide "from" or "to" in the URL
    now_str = datetime.now().strftime('%Y%m%d%H%M%S')
    today_midnight = datetime.now().strftime('%Y%m%d000000')

    # 2. Extract parameters from the URL 
    t1 = request.args.get("from", today_midnight)
    t2 = request.args.get("to", now_str)
    f = request.args.get("filter", "in,out,none")
    
    # 3. Process the filter string into a list 
    # Example: "in,out" becomes ["in", "out"]
    f_list = f.split(',')
    
    # 4. Define the SQL search query 
    # We use %s placeholders to safely pass our Python variables to SQL
    query = "SELECT id, truck, bruto, truckTara, neto, datetime FROM transactions WHERE datetime BETWEEN %s AND %s AND direction IN %s"
    params = (t1, t2, tuple(f_list))

    # 5. Execute the query and handle potential errors 
    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()  # Fetch all matching records
    except Exception as e:
        # If the database fails, return a 500 error instead of crashing
        return jsonify({"error": "Database connection failed"}), 500
    
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
