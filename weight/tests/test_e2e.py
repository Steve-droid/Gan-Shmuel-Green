import os
import json
import csv
import requests
import time
import uuid

BASE_URL = "http://localhost:5000"
IN_DIR = "in"


def wait_for_server():
    """Wait until server is ready."""
    for _ in range(30):
        try:
            r = requests.get(f"{BASE_URL}/health")
            if r.status_code == 200 and r.json().get("status") == "OK":
                return
        except Exception:
            pass
        time.sleep(1)

    raise Exception("Server did not start")


def setup_module():
    """Run before tests start."""
    os.makedirs(IN_DIR, exist_ok=True)
    wait_for_server()


# ------------------------------------------------
# 1. Health check
# ------------------------------------------------

def test_health():
    r = requests.get(f"{BASE_URL}/health")

    assert r.status_code == 200
    assert r.json()["status"] == "OK"


# ------------------------------------------------
# 2. Create weigh session (IN)
# ------------------------------------------------

def test_create_weight_in():
    truck_id = f"truck-{uuid.uuid4().hex[:6]}"

    payload = {
        "direction": "in",
        "truck": truck_id,
        "containers": "C1,C2",
        "weight": 20000,
        "unit": "kg",
        "produce": "orange"
    }

    r = requests.post(f"{BASE_URL}/weight", json=payload)

    assert r.status_code == 201, f"Expected 201, got {r.status_code}, body={r.text}"

    data = r.json()

    assert "id" in data
    assert data["truck"] == truck_id
    assert data["bruto"] == 20000


# ------------------------------------------------
# 3. Invalid case: OUT without IN
# ------------------------------------------------

def test_out_without_in():
    truck_id = f"truck-{uuid.uuid4().hex[:6]}"

    payload = {
        "direction": "out",
        "truck": truck_id,
        "weight": 10000,
        "unit": "kg"
    }

    r = requests.post(f"{BASE_URL}/weight", json=payload)

    assert r.status_code == 400
    assert "error" in r.json()


# ------------------------------------------------
# 4. Get all weigh records
# ------------------------------------------------

def test_get_weights():
    r = requests.get(f"{BASE_URL}/weight")

    assert r.status_code == 200

    data = r.json()

    assert isinstance(data, list) or "message" in data


# ------------------------------------------------
# 5. Session lookup
# ------------------------------------------------

def test_session_lookup():
    truck_id = f"truck-{uuid.uuid4().hex[:6]}"

    payload = {
        "direction": "in",
        "truck": truck_id,
        "containers": "X1",
        "weight": 15000,
        "unit": "kg",
        "produce": "apple"
    }

    r = requests.post(f"{BASE_URL}/weight", json=payload)

    assert r.status_code == 201, f"Expected 201, got {r.status_code}, body={r.text}"

    session_id = r.json()["id"]

    r = requests.get(f"{BASE_URL}/session/{session_id}")

    assert r.status_code == 200

    data = r.json()

    assert data["id"] == session_id
    assert data["truck"] == truck_id
    assert data["bruto"] == 15000


# ------------------------------------------------
# 6. Item lookup
# ------------------------------------------------

def test_item_lookup():
    truck_id = f"truck-{uuid.uuid4().hex[:6]}"

    payload = {
        "direction": "in",
        "truck": truck_id,
        "containers": "Y1",
        "weight": 16000,
        "unit": "kg",
        "produce": "pear"
    }

    r = requests.post(f"{BASE_URL}/weight", json=payload)

    assert r.status_code == 201, f"Expected 201, got {r.status_code}, body={r.text}"

    r = requests.get(f"{BASE_URL}/item/{truck_id}")

    assert r.status_code == 200

    data = r.json()

    assert data["id"] == truck_id
    assert "sessions" in data


# ------------------------------------------------
# 7. Batch upload JSON (create file during test)
# ------------------------------------------------

def test_batch_weight_json():
    container_id_1 = f"CJ-{uuid.uuid4().hex[:6]}"
    container_id_2 = f"CJ-{uuid.uuid4().hex[:6]}"
    filename = f"containers_{uuid.uuid4().hex[:6]}.json"
    filepath = os.path.join(IN_DIR, filename)

    rows = [
        {"id": container_id_1, "weight": 1000, "unit": "kg"},
        {"id": container_id_2, "weight": 2200, "unit": "lbs"}
    ]

    with open(filepath, "w") as f:
        json.dump(rows, f)

    try:
        r = requests.post(f"{BASE_URL}/batch-weight", json={"file": filename})

        assert r.status_code == 201, f"Expected 201, got {r.status_code}, body={r.text}"

        data = r.json()
        assert "Loaded 2 containers" in data["message"]

        r = requests.get(f"{BASE_URL}/item/{container_id_1}")
        assert r.status_code == 200

        data = r.json()
        assert data["id"] == container_id_1
        assert data["tara"] == 1000

    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


# ------------------------------------------------
# 8. Batch upload CSV (create file during test)
# ------------------------------------------------

def test_batch_weight_csv():
    container_id_1 = f"CC-{uuid.uuid4().hex[:6]}"
    container_id_2 = f"CC-{uuid.uuid4().hex[:6]}"
    filename = f"containers_{uuid.uuid4().hex[:6]}.csv"
    filepath = os.path.join(IN_DIR, filename)

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "kg"])
        writer.writerow([container_id_1, 1200])
        writer.writerow([container_id_2, 1500])

    try:
        r = requests.post(f"{BASE_URL}/batch-weight", json={"file": filename})

        assert r.status_code == 201, f"Expected 201, got {r.status_code}, body={r.text}"

        data = r.json()
        assert "Loaded 2 containers" in data["message"]

        r = requests.get(f"{BASE_URL}/item/{container_id_2}")
        assert r.status_code == 200

        data = r.json()
        assert data["id"] == container_id_2
        assert data["tara"] == 1500

    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


# ------------------------------------------------
# 9. Batch error: file not found
# ------------------------------------------------

def test_batch_file_not_found():
    filename = f"missing_{uuid.uuid4().hex[:6]}.json"

    r = requests.post(
        f"{BASE_URL}/batch-weight",
        json={"file": filename}
    )

    assert r.status_code == 404, f"Expected 404, got {r.status_code}, body={r.text}"
    assert "error" in r.json()


# ------------------------------------------------
# 10. Invalid date format
# ------------------------------------------------

def test_invalid_date_format():
    r = requests.get(f"{BASE_URL}/weight?from=abc")

    assert r.status_code == 400
    assert "error" in r.json()