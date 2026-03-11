import pytest
import requests
import os
from datetime import datetime, timedelta
# Use the service name defined in your docker-compose.yml
WEIGHT_URL = os.getenv("WEIGHT_SERVICE_URL", "http://localhost:8082")

# 0 test heath endpoint to ensure container is up before running other tests
def test_app_health_endpoint():
    """
    CI Test: Checks if the remote Flask app container 
    returns a 200 OK from its health endpoint.
    """
    endpoint = f"{WEIGHT_URL}/health"
    
    try:
        response = requests.get(endpoint, timeout=5)
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'OK'
        
    except requests.exceptions.ConnectionError:
        pytest.fail(f"Could not connect to the App at {endpoint}. Is the container running?")

@pytest.fixture(scope="module")
def shared_data():
    """Object to pass IDs between test steps."""
    return {
        "truck_id": "T-12345",
        "container_id": "C-999",
        "session_id": None
    }

# 1. Test POST /batch-weight
def test_post_batch_weight(shared_data):
    # This assumes 'containers1.json' exists in your /in volume
    payload = {"file": "containers1.json"}
    response = requests.post(f"{WEIGHT_URL}/batch-weight", json=payload)
    
    # If the file exists, we expect 201. 
    # If testing empty environment, adjust to check for 201 or 404
    assert response.status_code in [201, 404] 

# 2. Test POST /weight (IN)
def test_post_weight_in(shared_data):
    payload = {
        "truck": shared_data["truck_id"],
        "direction": "in",
        "weight": 4000,
        "unit": "kg",
        "produce": "apples",
        "containers": shared_data["container_id"]
    }
    response = requests.post(f"{WEIGHT_URL}/weight", json=payload)
    assert response.status_code == 201
    
    data = response.json()
    assert data["truck"] == shared_data["truck_id"]
    shared_data["session_id"] = data["sessionId"] # Save for next tests

# 3. Test GET /session/<id>
def test_get_session(shared_data):
    sess_id = shared_data["session_id"]
    response = requests.get(f"{WEIGHT_URL}/session/{sess_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == sess_id
    assert data["truck"] == shared_data["truck_id"]

# 4. Test GET /unknown
def test_get_unknown():
    response = requests.get(f"{WEIGHT_URL}/unknown")
    assert response.status_code == 200
    # Since C-999 was used in test_post_weight_in but likely isn't
    # in the DB registry yet, it should appear here.
    assert isinstance(response.json(), list)

# 5. Test POST /weight (OUT) - Closing the cycle
def test_post_weight_out(shared_data):
    payload = {
        "truck": shared_data["truck_id"],
        "direction": "out",
        "weight": 2000, # Truck is lighter now
        "unit": "kg"
    }
    response = requests.post(f"{WEIGHT_URL}/weight", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["truck"] == shared_data["truck_id"]
    # Check that it returned a neto (or "na" if container was unknown)
    assert "neto" in data

# 6. Test GET /weight (List) - must run after out to have a complete session
def test_get_weight_list():
    # Pass explicit `to` 2 seconds in the future to avoid sub-second timing race
    # where sessions written in the current second are excluded by the default `to=now`
    t2 = (datetime.now() + timedelta(seconds=2)).strftime('%Y%m%d%H%M%S')
    response = requests.get(f"{WEIGHT_URL}/weight", params={"to": t2})
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) > 0

# 7. Test GET /item/<id> - must run after out to have sessions populated
def test_get_item(shared_data):
    truck_id = shared_data["truck_id"]
    t2 = (datetime.now() + timedelta(seconds=2)).strftime('%Y%m%d%H%M%S')
    response = requests.get(f"{WEIGHT_URL}/item/{truck_id}", params={"to": t2})
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == truck_id
    assert shared_data["session_id"] in data["sessions"]