from unittest.mock import MagicMock, patch


def test_health_ok(client):
    mock_con = MagicMock()
    mock_cursor = MagicMock()
    mock_con.cursor.return_value = mock_cursor
    with patch("app.routes.health.get_db_connection", return_value=mock_con):
        response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "OK"
    
def test_health_db_failure(client):
    with patch("app.routes.health.get_db_connection", side_effect=Exception("DB down")):
        response = client.get("/health")
    assert response.status_code == 500
    assert response.data == b"Failure"