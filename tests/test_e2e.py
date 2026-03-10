import requests

WEIGHT_URL = "http://host.docker.internal:8082"
BILLING_URL = "http://host.docker.internal:8083"

TRUCK_ID = "TST-001"  # must be <= 10 chars (billingdb varchar(10))

def test_full_weighing_and_billing_flow():
    
    # Create provider
    r = requests.post(f"{BILLING_URL}/provider", json={"name": "Test Provider"})
    assert r.status_code == 201
    provider_id = r.json()["id"]

    # Register truck under provider
    r = requests.post(f"{BILLING_URL}/truck", json={"id": TRUCK_ID, "provider": provider_id})
    assert r.status_code == 201

    # Upload rates — file= is a query parameter, not a body field
    r = requests.post(f"{BILLING_URL}/rates?file=rates.xlsx")
    assert r.status_code == 200

    # Truck arrives
    r = requests.post(f"{WEIGHT_URL}/weight", json={
        "direction": "in", "truck": TRUCK_ID, "weight": 10000,
        "unit": "kg", "force": False, "produce": "orange", "containers": ""
    })
    assert r.status_code == 201

    # Truck leaves
    r = requests.post(f"{WEIGHT_URL}/weight", json={
        "direction": "out", "truck": TRUCK_ID, "weight": 3000,
        "unit": "kg", "force": False, "produce": "na", "containers": ""
    })
    assert r.status_code == 201
    assert r.json()["neto"] == 7000

    # Get invoice
    r = requests.get(f"{BILLING_URL}/bill/{provider_id}")
    assert r.status_code == 200
    bill = r.json()
    assert bill["sessionCount"] >= 1
    assert bill["total"] > 0
