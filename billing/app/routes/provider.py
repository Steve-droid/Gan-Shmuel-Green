from flask import Blueprint, request, jsonify
from app.db import get_db_connection
import uuid

provider_bp = Blueprint("provider", __name__)

def create_provider(name: str):
    if not name:
        return None
    con=None
    try:
        con = get_db_connection()
        cursor = con.cursor()
        cursor.execute("INSERT INTO Provider (name) VALUES (%s)", ( name,))
        con.commit()
        provider_id = cursor.lastrowid

        con.close()
        return provider_id
    except Exception:
        if con:
            con.close()
        return None

def update_provider(provider_id: str, new_name: str):
    con=None
    try:
        con = get_db_connection()
        cursor = con.cursor()
        cursor.execute("UPDATE Provider SET name = %s WHERE id = %s", (new_name, provider_id))
        updated = cursor.rowcount > 0
        if updated:
            con.commit()
        con.close()
        return updated
    except Exception:
        if con:
            con.close()
        return False

def get_all_providers():
    con=None

    try:
        con = get_db_connection()
        cursor = con.cursor()    
        cursor.execute("SELECT id, name FROM Provider")

        rows = cursor.fetchall()
        con.close()
        return [{"id": r[0], "name": r[1]} for r in rows]
    except Exception as e:
        if con:
            con.close()
        print("Error in get_all_providers:", e, flush=True)
        return []

# --- Routes ---
@provider_bp.post("/provider")
def create_provider_route():
    data = request.get_json()
    name = data.get("name")
    if not name:
        return jsonify({"error": "name is required"}), 400
    new_id = create_provider(name)
    if not new_id:
        return jsonify({"error": "Failed to create provider"}), 500
    return jsonify({"id": new_id}), 201

@provider_bp.put("/provider/<provider_id>")
def update_provider_route(provider_id):
    data = request.get_json()
    name = data.get("name")
    if not update_provider(provider_id, name):
        return jsonify({"error": "provider not found"}), 404
    return jsonify({"id": provider_id, "name": name}), 200

@provider_bp.get("/providers")
def list_providers_route():
    return jsonify(get_all_providers()), 200