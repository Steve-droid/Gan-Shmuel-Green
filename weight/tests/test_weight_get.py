import pytest
from unittest.mock import patch, MagicMock
from app import app
from datetime import datetime

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# 1. Test Success Case (Data found)
@patch('app.get_db')
def test_get_weights_success(mock_get_db, client):
    # Mock the database cursor and connection
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    # Define dummy data that looks like your DB rows
    mock_cursor.fetchall.return_value = [
        {
            "sessionId": 1001,
            "direction": "in",
            "bruto": 5000,
            "neto": 2000,
            "produce": "orange",
            "containers": "C1,C2",
            "datetime": "2024-01-01 10:00:00"
        }
    ]

    response = client.get('/weight?from=20240101000000&to=20240102000000&filter=in')
    
    data = response.get_json()
    assert response.status_code == 200
    assert len(data) == 1
    assert data[0]["sessionId"] == 1001
    assert data[0]["containers"] == ["C1", "C2"]  # Check it split correctly

# 2. Test Edge Case: No Results Found
@patch('app.get_db')
def test_get_weights_empty(mock_get_db, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Return empty list from DB
    mock_cursor.fetchall.return_value = []

    response = client.get('/weight?from=20200101000000&to=20200101000001')
    
    data = response.get_json()
    assert response.status_code == 200
    assert data == []

# 3. Test Edge Case: Invalid Date Format (400)
def test_get_weights_invalid_date(client):
    response = client.get('/weight?from=2024-01-01') # Wrong format
    assert response.status_code == 400
    assert "Invalid date format" in response.get_json()["error"]

# 4. Test Edge Case: Invalid Filter (400)
def test_get_weights_invalid_filter(client):
    response = client.get('/weight?filter=truck') # 'truck' is not allowed
    assert response.status_code == 400
    assert "Invalid filter" in response.get_json()["error"]

# 5. Test Edge Case: Future Date
def test_get_weights_future_date(client):
    # Set 'from' in 2099 AND 'to' in 2100 so the range is NOT reversed
    response = client.get('/weight?from=20990101000000&to=21000101000000')
    
    data = response.get_json()
    assert response.status_code == 200
    assert "future time range" in data["message"]