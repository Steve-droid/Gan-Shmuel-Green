from flask import Blueprint, jsonify, request
from app.db import get_db_connection
import requests

truck_bp = Blueprint('truck', __name__)

@truck_bp.route('/truck', methods=['POST'])
def post_truck():
    try:
        provider_id = request.json.get('provider')
        truck_id = request.json.get('id')

        con = get_db_connection()
        cursor = con.cursor()
        cursor.execute(
            "INSERT INTO Trucks (id, provider_id) VALUES (%s, %s)",
            (truck_id, provider_id)
        )
        con.commit()
        con.close()
        return jsonify({"id": truck_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@truck_bp.route('/truck/<id>', methods=['PUT'])
def put_truck(id):
    try:
        provider_id = request.json.get('provider')

        con = get_db_connection()
        cursor = con.cursor()
        cursor.execute(
            "UPDATE Trucks SET provider_id = %s WHERE id = %s",
            (provider_id, id)
        )
        if cursor.rowcount == 0:
            return jsonify({"error": "Truck not found"}), 404
        
        con.commit()
        con.close()
        return jsonify({"id": id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@truck_bp.route('/truck/<id>', methods=['GET'])
def get_truck(id):
    try:
        from_time = request.args.get('from')
        to_time = request.args.get('to')

        con = get_db_connection()
        cursor = con.cursor()
        cursor.execute(
            "SELECT id FROM Trucks WHERE id = %s", (id,)
        )
        truck = cursor.fetchone()
        con.close()

        if not truck:
            return jsonify({"error": "Truck not found"}), 404
        
        weight_url = f"http://weight-service:5000/item/{id}"
        params = {}
        if from_time:
            params['from'] = from_time
        if to_time:
            params['to'] = to_time
        
        weight_response = requests.get(weight_url, params=params)
        weight_data = weight_response.json()

        return jsonify({
            "id": id,
            "tara": weight_data.get("tara", "na"),
            "sessions": weight_data.get("sessions", [])
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500