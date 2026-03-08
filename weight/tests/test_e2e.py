import requests
import time
import uuid

BASE_URL = "http://localhost:5000"


def wait_for_server():
    """Wait until Flask server is ready."""
    for _ in range(30):
        try:
            r = requests.get(f"{BASE_URL}/health")
            if r.status_code == 200 and r.json().get("status") == "OK":
                return
        except Exception:
            pass
        time.sleep(1)
    raise Exception("Server did not start in time")


def setup_module():
    wait_for_server()


def test_health():
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "OK"


def test_create_in_weight():
    truck_id = f"truck-{uuid.uuid4().hex[:8]}"

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


def test_get_weights():
    r = requests.get(f"{BASE_URL}/weight")
    assert r.status_code == 200

    data = r.json()
    assert isinstance(data, list) or "message" in data


def test_out_without_in_should_fail():
    truck_id = f"truck-{uuid.uuid4().hex[:8]}"

    payload = {
        "direction": "out",
        "truck": truck_id,
        "weight": 10000,
        "unit": "kg"
    }

    r = requests.post(f"{BASE_URL}/weight", json=payload)
    assert r.status_code == 400
    assert "error" in r.json()


def test_session_lookup():
    truck_id = f"truck-{uuid.uuid4().hex[:8]}"

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


def test_item_endpoint():
    truck_id = f"truck-{uuid.uuid4().hex[:8]}"

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


def test_invalid_date_format_should_fail():
    r = requests.get(f"{BASE_URL}/weight?from=abc")
    assert r.status_code == 400
    assert "error" in r.json()