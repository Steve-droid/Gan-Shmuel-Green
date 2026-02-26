from flask import Blueprint, jsonify
from app.db import get_db_connection

health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health():
    try:
        con = get_db_connection()
        cursor = con.cursor()
        cursor.execute("SELECT 1")
        con.close
        return "OK", 200
    except Exception:
        return "Failure", 500
    
