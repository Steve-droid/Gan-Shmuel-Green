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
