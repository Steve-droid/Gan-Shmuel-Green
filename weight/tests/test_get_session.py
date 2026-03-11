import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime
from app import app 

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# 1. Show Output for a Successful 'OUT' Session
@patch('app.get_db')
def test_print_success_output(mock_get_db, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    # Simulating: Bruto(8000) - Tara(4000) - Container(520) = 3480
    mock_cursor.fetchall.return_value = [
    {
        "sessionId": 10004,
        "truck": "XYZ-789",
        "bruto": 8000,
        "direction": "in",
        "datetime": datetime(2026, 2, 22, 13, 45, 43),
        "produce": "apples",
        "containers": ""
    },
    {
        "sessionId": 10004,
        "truck": "XYZ-789",
        "bruto": 8000,
        "direction": "out",
        "datetime": datetime(2026, 2, 22, 14, 0, 0),
        "truckTara": 4000,
        "neto": 3480,
        "produce": "na",
        "containers": ""
    }
]

    response = client.get('/session/10004')
    data = response.get_json()

    print("\n\n--- USER RECEIVES (SUCCESS CASE) ---")
    print(json.dumps(data, indent=4))
    print("------------------------------------\n")

    assert response.status_code == 200
    assert data["neto"] == 3480

# 2. Show Output for Missing Tara Edge Case
@patch('app.get_db')
def test_print_missing_tara_output(mock_get_db, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    mock_cursor.fetchall.return_value = [
    {
        "sessionId": 10005,
        "truck": "ABC-123",
        "bruto": 12000,
        "direction": "out",
        "datetime": datetime(2026, 2, 25, 10, 0, 0),
        "truckTara": 0,
        "neto": None,
        "produce": "na",
        "containers": "C001"
    }
]

    response = client.get('/session/10005')
    data = response.get_json()

    print("\n--- USER RECEIVES (MISSING TARA CASE) ---")
    print(json.dumps(data, indent=4))
    print("-----------------------------------------\n")

    assert data["neto"] == "na"

# 3. Show Output for Session Not Found
@patch('app.get_db')
def test_print_not_found_output(mock_get_db, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    mock_cursor.fetchone.return_value = None

    response = client.get('/session/999')
    data = response.get_json()

    print("\n--- USER RECEIVES (404 ERROR) ---")
    print(json.dumps(data, indent=4))
    print("---------------------------------\n")

    assert response.status_code == 404