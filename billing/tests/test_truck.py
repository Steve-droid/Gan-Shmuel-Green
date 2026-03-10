from unittest.mock import MagicMock, patch


def test_post_truck_success(client):
    mock_con = MagicMock()
    mock_cursor = MagicMock()
    mock_con.cursor.return_value = mock_cursor

    with patch("app.routes.truck.get_db_connection", return_value=mock_con):
        response = client.post("/truck", json={"id": "123-45-678", "provider": 1})

    assert response.status_code == 201
    assert response.get_json() == {"id": "123-45-678"}
    mock_cursor.execute.assert_called_once_with(
        "INSERT INTO Trucks (id, provider_id) VALUES (%s, %s)",
        ("123-45-678", 1)
    )
    mock_con.commit.assert_called_once()
    mock_con.close.assert_called_once()

def test_post_truck_db_failure(client):
    with patch("app.routes.truck.get_db_connection", side_effect=Exception("DB error")):
        response = client.post("/truck", json={"id": "123-45-678", "provider": 1})
    
    assert response.status_code == 500
    assert "error" in response.get_json()

def test_post_truck_missing_fields(client):
    mock_con = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = Exception("Column cannot be null")
    mock_con.cursor.return_value= mock_cursor

    with patch("app.routes.truck.get_db_connection", return_value=mock_con):
        response = client.post("/truck", json={})
    
    assert response.status_code == 500
    assert "error" in response.get_json()

def test_put_truck_success(client):
    mock_con = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 1
    mock_con.cursor.return_value = mock_cursor

    with patch("app.routes.truck.get_db_connection", return_value=mock_con):
        response = client.put("/truck/123-45-678", json={"provider": 2})
    
    assert response.status_code == 200
    assert response.get_json() == {"id": "123-45-678"}
    mock_con.commit.assert_called_once()

def test_put_truck_not_found(client):
    mock_con = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 0
    mock_con.cursor.return_value = mock_cursor

    with patch("app.routes.truck.get_db_connection", return_value=mock_con):
        response = client.put("/truck/999-99-999", json={"provider": 2})

    assert response.status_code == 404
    assert response.get_json() == {"error": "Truck not found"}
    mock_con.close.assert_called_once()

def test_get_truck_success(client):
    mock_con = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = ("123-45-678",)
    mock_con.cursor.return_value = mock_cursor

    mock_weight_response = MagicMock()
    mock_weight_response.json.return_value = {"tara": 5000, "sessions": [1, 2]}

    with patch("app.routes.truck.get_db_connection", return_value=mock_con), \
        patch("app.routes.truck.requests.get", return_value=mock_weight_response):
        response = client.get("/truck/123-45-678")

    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == "123-45-678"
    assert data["tara"] == 5000
    assert data["sessions"] == [1, 2]

def test_get_truck_not_found(client):
    mock_con = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_con.cursor.return_value = mock_cursor

    with patch("app.routes.truck.get_db_connection", return_value=mock_con):
        response = client.get("/truck/999-99-999")
    
    assert response.status_code == 404
    assert response.get_json() == {"error": "Truck not found"}