from flask import Blueprint, request, jsonify, send_file
import pandas as pd
from app.db import get_db_connection
import os
from io import BytesIO


rates_bp = Blueprint("rates", __name__)

@rates_bp.post("/rates")
def upload_rates():

    filename = request.args.get("file")
    if not filename:
        return jsonify({"error": "file parameter required"}), 400

    path = f"in/{filename}"
    if not os.path.exists(path):
        return jsonify({"error": "file not found"}), 404

    df = pd.read_excel(path)

    con = get_db_connection()
    cursor = con.cursor()

    cursor.execute("DELETE FROM Rates")

    for _, row in df.iterrows():
        product = row["Product"]
        rate = int(row["Rate"])
        scope = str(row["Scope"])

        cursor.execute("""
            INSERT INTO Rates (product_id, rate, scope)
            VALUES (%s, %s, %s)
        """, (product, rate, scope))

    con.commit()
    con.close()

    return jsonify({"status": "all rates replaced"}), 200


@rates_bp.get("/rates")
def download_rates():
    con = get_db_connection()
    df = pd.read_sql("SELECT product_id AS Product, rate AS Rate, scope AS Scope FROM Rates", con)
    con.close()

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Rates")
    output.seek(0)

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="rates.xlsx"
    )