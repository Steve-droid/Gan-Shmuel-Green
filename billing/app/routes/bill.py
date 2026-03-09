from flask import Blueprint, jsonify, request
from app.db import get_db_connection
import requests
import os
from datetime import datetime

bill_bp = Blueprint('bill', __name__)

@bill_bp.route('/bill/<int:id>', methods=['GET'])
def get_bill(id):
    try:
        from_time = request.args.get('from', datetime.now().replace(day=1).strftime('%Y%m%d000000'))
        to_time = request.args.get('to', datetime.now().strftime('%Y%m%d%H%M%S'))

        con = get_db_connection()
        cursor = con.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM Provider WHERE id = %s", (id,)
        )
        provider = cursor.fetchone()
        if not provider:
            con.close()
            return jsonify({"error": "Provider not found"}), 404

        cursor.execute(
            "SELECT id FROM Trucks WHERE provider_id = %s", (id,))
        trucks = cursor.fetchall()

        cursor.execute("SELECT product_id, rate FROM Rates WHERE scope = %s OR scope = 'ALL'", (id,))
        rates = {row['product_id']: row['rate'] for row in cursor.fetchall()}

        con.close()

        total = 0
        session_count = 0
        truck_list = []
        products_map = {}
        weight_url = os.environ.get("WEIGHT_SERVICE_URL", "http://weight-service:5000")

        for truck in trucks:
            truck_id = truck['id']
            resp = requests.get(f"{weight_url}/item/{truck_id}", params={'from': from_time, 'to': to_time})
            weight_data = resp.json()

            sessions = weight_data.get('sessions', [])
            truck_list.append(truck_id)

            for session_id in sessions:
                session_resp = requests.get(f"{weight_url}/session/{session_id}")
                session_data = session_resp.json()
                product = session_data.get('produce', 'unknown')
                neto = session_data.get('neto', 'na')

                if neto == 'na' or neto is None:
                    continue

                session_count += 1
                rate = rates.get(product, 0)
                pay = neto * rate
                total += pay

                if product not in products_map:
                    products_map[product] = {'count': 0, 'amount': 0, 'rate': rate}
                products_map[product]['count'] += 1
                products_map[product]['amount'] += neto

        products = [
            {
                "product": product,
                "count": str(data['count']),
                "amount": data['amount'],
                "rate": data['rate'],
                "pay": data['amount'] * data['rate']
            }
            for product, data in products_map.items()
        ]

        return jsonify({
            "id": str(id),
            "name": provider['name'],
            "from": from_time,
            "to": to_time,
            "truckCount": len(truck_list),
            "sessionCount": session_count,
            "products": products,
            "total": total
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
