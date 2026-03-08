from flask import Blueprint, jsonify, request
from app.db import get_db_connection

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