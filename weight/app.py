from flask import Flask, request, jsonify

app = Flask(__name__)


# POST endpoint
@app.post('/weight')
def post_data():
    """Handle POST requests"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    return jsonify({
        'message': 'Data received successfully',
        'received_data': data,
        'status': 'success'
    }), 201

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
