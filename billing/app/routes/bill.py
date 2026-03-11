from flask import Blueprint, jsonify, request
from app.db import get_db_connection
import requests
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bill_bp = Blueprint('bill', __name__)

@bill_bp.route('/bill/<int:id>', methods=['GET'])
def get_bill(id):
    logger.debug(f"=== get_bill called === id={id}, args={dict(request.args)}")
    try:
        from_time = request.args.get('from', datetime.now().replace(day=1).strftime('%Y%m%d000000'))
        to_time = request.args.get('to', datetime.now().strftime('%Y%m%d%H%M%S'))
        logger.debug(f"Time range: from={from_time}, to={to_time}")

        con = get_db_connection()
        cursor = con.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM Provider WHERE id = %s", (id,)
        )
        provider = cursor.fetchone()
        logger.debug(f"Provider lookup result: {provider}")
        if not provider:
            logger.warning(f"Provider id={id} not found")
            con.close()
            return jsonify({"error": "Provider not found"}), 404

        cursor.execute(
            "SELECT id FROM Trucks WHERE provider_id = %s", (id,))
        trucks = cursor.fetchall()
        logger.debug(f"Trucks for provider {id}: {trucks}")

        cursor.execute(
            "SELECT product_id, rate, scope FROM Rates WHERE scope = %s OR scope = 'ALL'",
            (str(id),)
        )
        rows = cursor.fetchall()
        logger.debug(f"Raw rates rows: {rows}")
        rates = {row['product_id'].lower(): row['rate'] for row in rows if row['scope'].upper() == 'ALL'}
        rates.update({row['product_id'].lower(): row['rate'] for row in rows if row['scope'].upper() != 'ALL'})
        logger.debug(f"Resolved rates map: {rates}")

        con.close()

        total = 0
        session_count = 0
        truck_list = []
        products_map = {}
        weight_url = os.environ.get("WEIGHT_SERVICE_URL", "http://weight-service:5000")
        logger.debug(f"Weight service URL: {weight_url}")

        for truck in trucks:
            truck_id = truck['id']
            logger.debug(f"Fetching sessions for truck_id={truck_id}")
            resp = requests.get(f"{weight_url}/item/{truck_id}", params={'from': from_time, 'to': to_time})
            logger.debug(f"  /item/{truck_id} status={resp.status_code}, body={resp.text[:300]}")
            weight_data = resp.json()

            sessions = weight_data.get('sessions', [])
            logger.debug(f"  Sessions for truck {truck_id}: {sessions}")
            truck_list.append(truck_id)

            for session_id in sessions:
                session_resp = requests.get(f"{weight_url}/session/{session_id}")
                logger.debug(f"  /session/{session_id} status={session_resp.status_code}, body={session_resp.text[:300]}")
                session_data = session_resp.json()

                product = session_data.get('produce', 'unknown').lower()
                neto = session_data.get('neto', 'na')
                logger.debug(f"    session {session_id}: product={product}, neto={neto}")

                if neto == 'na' or neto is None:
                    logger.debug(f"    Skipping session {session_id} — neto is na/None")
                    continue

                session_count += 1
                rate = rates.get(product, 0)
                pay = neto * rate
                total += pay
                logger.debug(f"    rate={rate}, pay={pay}, running total={total}")

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

        response_body = {
            "id": str(id),
            "name": provider['name'],
            "from": from_time,
            "to": to_time,
            "truckCount": len(truck_list),
            "sessionCount": session_count,
            "products": products,
            "total": total
        }
        logger.debug(f"=== get_bill response === {response_body}")
        return jsonify(response_body), 200

    except Exception as e:
        logger.exception(f"get_bill error for id={id}: {e}")
        return jsonify({"error": str(e)}), 500
