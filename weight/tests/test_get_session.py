import pytest
import json
from unittest.mock import patch, MagicMock
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# 1. Successful session with both IN and OUT
@patch("app.get_db")
def test_print_success_output(mock_get_db, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    mock_cursor.fetchall.return_value = [
        {
            "id": 10001,
            "sessionId": 10004,
            "truck": "XYZ-789",
            "bruto": 8000,
            "direction": "in",
            "produce": "orange"
        },
        {
            "id": 10002,
            "sessionId": 10004,
            "truck": "XYZ-789",
            "bruto": 4000,
            "direction": "out",
            "truckTara": 4000,
            "neto": 3480,
            "produce": "orange"
        }
    ]

    response = client.get("/session/10004")
    data = response.get_json()

    print("\n\n--- USER RECEIVES (SUCCESS CASE) ---")
    print(json.dumps(data, indent=4))
    print("------------------------------------\n")

    assert response.status_code == 200
    assert data["id"] == 10004
    assert data["truck"] == "XYZ-789"
    assert data["bruto"] == 8000
    assert data["produce"] == "orange"
    assert data["truckTara"] == 4000
    assert data["neto"] == 3480


# 2. OUT exists but neto is unknown
@patch("app.get_db")
def test_print_missing_tara_output(mock_get_db, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    mock_cursor.fetchall.return_value = [
        {
            "id": 10003,
            "sessionId": 10005,
            "truck": "ABC-123",
            "bruto": 12000,
            "direction": "in",
            "produce": "orange"
        },
        {
            "id": 10004,
            "sessionId": 10005,
            "truck": "ABC-123",
            "bruto": 5000,
            "direction": "out",
            "truckTara": 0,
            "neto": None,
            "produce": "orange"
        }
    ]

    response = client.get("/session/10005")
    data = response.get_json()

    print("\n--- USER RECEIVES (MISSING TARA / UNKNOWN NETO CASE) ---")
    print(json.dumps(data, indent=4))
    print("--------------------------------------------------------\n")

    assert response.status_code == 200
    assert data["id"] == 10005
    assert data["truck"] == "ABC-123"
    assert data["bruto"] == 12000
    assert data["produce"] == "orange"
    assert data["truckTara"] == 0
    assert data["neto"] == "na"


# 3. Session not found
@patch("app.get_db")
def test_print_not_found_output(mock_get_db, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    mock_cursor.fetchall.return_value = []

    response = client.get("/session/999")
    data = response.get_json()

    print("\n--- USER RECEIVES (404 ERROR) ---")
    print(json.dumps(data, indent=4))
    print("---------------------------------\n")

    assert response.status_code == 404
    assert data["status"] == "error"
    assert "not found" in data["message"].lower()