import pytest
import requests
import os

# Get the URL of the app container from environment variables
# Default to localhost if not set (for local testing)
BILLING_URL = os.getenv("BILLING_URL", "http://localhost:8083")

def test_app_health_endpoint():
    """
    CI Test: Checks if the remote Flask app container 
    returns a 200 OK from its health endpoint.
    """
    endpoint = f"{BILLING_URL}/health"
    
    try:
        response = requests.get(endpoint, timeout=5)
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'OK'
        
    except requests.exceptions.ConnectionError:
        pytest.fail(f"Could not connect to the App at {endpoint}. Is the container running?")

@pytest.fixture(scope="module")
def state():
    """Stores IDs created during testing to pass between functions."""
    return {
        "provider_id": None,
        "truck_id": "T-800-BILL",
        "product_id": "Apples"
    }

# --- Provider Tests ---

def test_post_provider(state):
    payload = {"name": "Test Logistics Ltd"}
    response = requests.post(f"{BILLING_URL}/provider", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    state["provider_id"] = data["id"]

def test_get_providers():
    response = requests.get(f"{BILLING_URL}/providers")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_put_provider(state):
    p_id = state["provider_id"]
    payload = {"name": "Updated Logistics Name"}
    response = requests.put(f"{BILLING_URL}/provider/{p_id}", json=payload)
    assert response.status_code == 200

# --- Truck Tests ---

def test_post_truck(state):
    payload = {
        "id": state["truck_id"],
        "provider_id": state["provider_id"]
    }
    response = requests.post(f"{BILLING_URL}/truck", json=payload)
    assert response.status_code == 201

def test_get_truck_details(state):
    t_id = state["truck_id"]
    response = requests.get(f"{BILLING_URL}/truck/{t_id}")
    assert response.status_code == 200
    assert response.json()["id"] == t_id

# --- Rates Tests ---

def test_post_rates(state):
    response = requests.post(f"{BILLING_URL}/rates", params={"file": "rates.xlsx"})
    assert response.status_code == 200

def test_get_rates():
    response = requests.get(f"{BILLING_URL}/rates")
    assert response.status_code == 200
    # Assuming it returns a list or a CSV-like structure
    assert response.content is not None 

# --- The "Big One": Bill Test ---

def test_get_bill_functional(state):
    """
    Tests the logic in bill.py. 
    Note: This will return total=0 if the Weight Service has 
    no sessions for this truck ID in the default time range.
    """
    p_id = state["provider_id"]
    response = requests.get(f"{BILLING_URL}/bill/{p_id}")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == str(p_id)
    assert "total" in data
    assert "products" in data
    assert isinstance(data["products"], list)