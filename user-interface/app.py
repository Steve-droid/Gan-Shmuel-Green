import os
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, Response
from dotenv import load_dotenv
import io

DATE_FROM_PLACEHOLDER = "11/03/2026 14:30:00"
DATE_TO_PLACEHOLDER = "12/03/2026 15:30:00"
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")

WEIGHT_URL = os.getenv("WEIGHT_URL", "http://localhost:5001")
BILLING_URL = os.getenv("BILLING_URL", "http://localhost:5002")


def call(method, base, path, **kwargs):
    """Make an HTTP request; return (response_or_None, error_string_or_None)."""
    try:
        r = getattr(requests, method)(f"{base}{path}", timeout=5, **kwargs)
        return r, None
    except requests.exceptions.ConnectionError:
        return None, f"Could not connect to {base}"
    except requests.exceptions.Timeout:
        return None, f"Request to {base} timed out"


# ── Dashboard ──────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    w_resp, w_err = call("get", WEIGHT_URL, "/health")
    b_resp, b_err = call("get", BILLING_URL, "/health")
    weight_ok = w_resp is not None and w_resp.status_code == 200
    billing_ok = b_resp is not None and b_resp.status_code == 200
    return render_template("dashboard.html",
                           weight_ok=weight_ok, weight_err=w_err,
                           billing_ok=billing_ok, billing_err=b_err)


# ── Weight — Record ────────────────────────────────────────────────────────────

@app.route("/weight/record", methods=["GET", "POST"])
def weight_record():
    result = None
    if request.method == "POST":
        payload = {k: v for k, v in request.form.items() if v}
        r, err = call("post", WEIGHT_URL, "/weight", json=payload)
        if err:
            flash(err, "danger")
        elif r.ok:
            result = r.json()
            flash("Weighing recorded successfully.", "success")
        else:
            flash(f"Error {r.status_code}: {r.text}", "danger")
    return render_template("weight/record.html", result=result)


# ── Weight — Query ─────────────────────────────────────────────────────────────

@app.route("/weight/query")
def weight_query():
    rows = None
    params = {k: v for k, v in request.args.items() if v}
    from_dt=request.args.get("w_from", "na")
    to_dt=request.args.get("w_to", "na")
    # Convert datetime-local format to YYYYMMDDHHMMSS if present
    if from_dt and from_dt != "na":
        params["from"] = from_dt.replace("-", "").replace("T", "").replace(":", "")
    if to_dt and to_dt != "na":
        params["to"] = to_dt.replace("-", "").replace("T", "").replace(":", "")
    
    # Checkboxes send filter=in&filter=out as separate keys; merge into one CSV string
    filter_vals = request.args.getlist('filter')
    if filter_vals:
        params['filter'] = ','.join(filter_vals)
    if params or "submitted" in request.args:
        r, err = call("get", WEIGHT_URL, "/weight", params=params)
        if err:
            flash(err, "danger")
        elif r.ok:
            rows = r.json()
        else:
            flash(f"Error {r.status_code}: {r.text}", "danger")
    return render_template("weight/query.html", rows=rows, raw=params,args=request.args)


# ── Weight — Batch Upload ──────────────────────────────────────────────────────

@app.route("/weight/batch", methods=["GET", "POST"])
def weight_batch():
    if request.method == "POST":
        filename = request.form.get("filename", "").strip()
        if not filename:
            flash("Please enter the filename.", "warning")
        else:
            r, err = call("post", WEIGHT_URL, "/batch-weight", json={"file": filename})
            if err:
                flash(err, "danger")
            elif r.ok:
                flash(f"Batch loaded: {r.text}", "success")
            else:
                flash(f"Error {r.status_code}: {r.text}", "danger")
    return render_template("weight/batch.html")


# ── Weight — Unknown ───────────────────────────────────────────────────────────

@app.route("/weight/unknown")
def weight_unknown():
    r, err = call("get", WEIGHT_URL, "/unknown")
    if err:
        flash(err, "danger")
        items = []
    elif r.ok:
        items = r.json()
    else:
        flash(f"Error {r.status_code}: {r.text}", "danger")
        items = []
    return render_template("weight/unknown.html", items=items)


# ── Lookup — Item / Session ────────────────────────────────────────────────────

@app.route("/lookup")
def lookup():
    item_result = session_result = None
    item_id = request.args.get("item_id", "").strip()
    session_id = request.args.get("session_id", "").strip()
    from_dt = request.args.get("from", "")
    to_dt = request.args.get("to", "")

    if item_id:
        params = {}
        if from_dt:
            params["from"] = from_dt
        if to_dt:
            params["to"] = to_dt
        r, err = call("get", WEIGHT_URL, f"/item/{item_id}", params=params)
        if err:
            flash(err, "danger")
        elif r.ok:
            item_result = r.json()
        else:
            flash(f"Error {r.status_code}: {r.text}", "danger")

    if session_id:
        r, err = call("get", WEIGHT_URL, f"/session/{session_id}")
        if err:
            flash(err, "danger")
        elif r.ok:
            session_result = r.json()
        else:
            flash(f"Error {r.status_code}: {r.text}", "danger")

    return render_template("lookup.html",
                           item_result=item_result, session_result=session_result,
                           args=request.args)


# ── Billing — Providers ────────────────────────────────────────────────────────

@app.route("/billing/providers", methods=["GET", "POST"])
def billing_providers():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            name = request.form.get("name", "").strip()
            r, err = call("post", BILLING_URL, "/provider", json={"name": name})
            if err:
                flash(err, "danger")
            elif r.ok:
                data = r.json()
                flash(f"Provider created with ID {data.get('id')}.", "success")
            else:
                flash(f"Error {r.status_code}: {r.text}", "danger")
        elif action == "update":
            pid = request.form.get("provider_id", "").strip()
            name = request.form.get("new_name", "").strip()
            r, err = call("put", BILLING_URL, f"/provider/{pid}", json={"name": name})
            if err:
                flash(err, "danger")
            elif r.ok:
                flash("Provider updated.", "success")
            else:
                flash(f"Error {r.status_code}: {r.text}", "danger")
        return redirect(url_for("billing_providers"))
    return render_template("billing/providers.html")


# ── Billing — Trucks ───────────────────────────────────────────────────────────

@app.route("/billing/trucks", methods=["GET", "POST"])
def billing_trucks():
    truck_result = None
    if request.method == "POST":
        action = request.form.get("action")
        if action == "register":
            payload = {"id": request.form.get("truck_id", "").strip(),
                       "provider": request.form.get("provider_id", "").strip()}
            r, err = call("post", BILLING_URL, "/truck", json=payload)
            if err:
                flash(err, "danger")
            elif r.ok:
                flash("Truck registered.", "success")
            else:
                flash(f"Error {r.status_code}: {r.text}", "danger")
        elif action == "update":
            tid = request.form.get("truck_id", "").strip()
            provider = request.form.get("provider_id", "").strip()
            r, err = call("put", BILLING_URL, f"/truck/{tid}", json={"provider": provider})
            if err:
                flash(err, "danger")
            elif r.ok:
                flash("Truck updated.", "success")
            else:
                flash(f"Error {r.status_code}: {r.text}", "danger")
        return redirect(url_for("billing_trucks"))

    lookup_id = request.args.get("truck_id", "").strip()
    if lookup_id:
        params = {k: v for k, v in request.args.items() if k in ("from", "to") and v}
        r, err = call("get", BILLING_URL, f"/truck/{lookup_id}", params=params)
        if err:
            flash(err, "danger")
        elif r.ok:
            truck_result = r.json()
        else:
            flash(f"Error {r.status_code}: {r.text}", "danger")

    return render_template("billing/trucks.html", truck_result=truck_result, args=request.args)


# ── Billing — Rates ────────────────────────────────────────────────────────────

@app.route("/billing/rates", methods=["GET", "POST"])
def billing_rates():
    if request.method == "POST":
        filename = request.form.get("filename", "").strip()
        if not filename:
            flash("Please enter the filename.", "warning")
        else:
            r, err = call("post", BILLING_URL, "/rates", params={"file": filename})
            if err:
                flash(err, "danger")
            elif r.ok:
                flash(f"Rates uploaded: {r.text}", "success")
            else:
                flash(f"Error {r.status_code}: {r.text}", "danger")
        return redirect(url_for("billing_rates"))
    return render_template("billing/rates.html")


@app.route("/billing/rates/download")
def billing_rates_download():
    r, err = call("get", BILLING_URL, "/rates")
    if err:
        flash(err, "danger")
        return redirect(url_for("billing_rates"))
    return Response(
        r.content,
        mimetype=r.headers.get("Content-Type", "application/octet-stream"),
        headers={"Content-Disposition": "attachment; filename=rates.xlsx"}
    )


# ── Billing — Invoice ──────────────────────────────────────────────────────────

@app.route("/billing/bill", methods=["GET"])
def billing_bill():
    bill = None
    provider_id = request.args.get("provider_id", "").strip()
    if provider_id:
        params = {k: v for k, v in request.args.items() if k in ("from", "to") and v}
        r, err = call("get", BILLING_URL, f"/bill/{provider_id}", params=params)
        if err:
            flash(err, "danger")
        elif r.ok:
            bill = r.json()
        else:
            flash(f"Error {r.status_code}: {r.text}", "danger")
    return render_template("billing/bill.html", bill=bill, args=request.args)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
