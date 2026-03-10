from unittest.mock import MagicMock, patch


def test_get_bill_provider_not_found(client):
    mock_con = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_con.cursor.return_value = mock_cursor

    with patch("app.routes.bill.get_db_connection", return_value=mock_con):
        response = client.get("/bill/1")
    
    assert response.status_code == 404
    assert response.get_json() == {"error": "Provider not found"}

def test_get_bill_success(client):
    mock_con = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"id" : 1, "name": "Test Provider"}
    mock_cursor.fetchall.side_effect = [
        [{"id": "123-45-678"}],
        [{"product_id": "orange", "rate": 10}]
    ]
    mock_con.cursor.return_value = mock_cursor

    mock_item_resp = MagicMock()
    mock_item_resp.json.return_value = {"sessions" : [100]}

    mock_session_resp = MagicMock()
    mock_session_resp.json.return_value = {"produce": "orange", "neto": 500}

    def mock_request_get(url, **kwargs):
        if "/item/" in url:
            return mock_item_resp
        return mock_session_resp
    
    with patch("app.routes.bill.get_db_connection", return_value=mock_con), \
        patch("app.routes.bill.requests.get", side_effect=mock_request_get):
        response = client.get("/bill/1")
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == "1"
    assert data["name"] == "Test Provider"
    assert data["truckCount"] == 1
    assert data["sessionCount"] == 1
    assert data["total"] == 5000
    assert data["products"][0]["product"] == "orange"
    assert data["products"][0]["count"] == "1"
    assert data["products"][0]["amount"] == 500

def test_get_bill_skips_incomplete_sessions(client):
    mock_con = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"id": 1, "name": "Test Provider"}
    mock_cursor.fetchall.side_effect = [
        [{"id": "123-45-678"}],
        []
    ]
    mock_con.cursor.return_value = mock_cursor

    mock_item_resp = MagicMock()
    mock_item_resp.json.return_value = {"sessions": [100]}

    mock_sessions_resp = MagicMock()
    mock_sessions_resp.json.return_value = {"produce": "orange", "neto": "na"}

    def mock_requests_get(url, **kwargs):
        if "/item/" in url:
            return mock_item_resp
        return mock_sessions_resp
    
    with patch("app.routes.bill.get_db_connection", return_value=mock_con), \
        patch("app.routes.bill.requests.get", side_effect=mock_requests_get):
        response = client.get("/bill/1")

    assert response.status_code == 200
    data = response.get_json()
    assert data["sessionCount"] == 0
    assert data["total"] == 0
    assert data["products"] == []

def test_get_bill_db_failure(client):
    with patch("app.routes.bill.get_db_connection", side_effect=Exception("DB error")):
        response = client.get("/bill/1")
    
    assert response.status_code == 500
    assert "error" in response.get_json()
