import pytest
from unittest.mock import patch, MagicMock
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def make_mock_db():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


# 1. Success case: data found
@patch("app.get_db")
def test_get_weights_success(mock_get_db, client):
    mock_conn, mock_cursor = make_mock_db()
    mock_get_db.return_value = mock_conn

    mock_cursor.fetchall.return_value = [
        {
            "id": 1001,
            "sessionId": 1001,
            "direction": "in",
            "bruto": 5000,
            "neto": 2000,
            "produce": "orange",
            "containers": "C1,C2"
        }
    ]

    response = client.get("/weight?from=20240101000000&to=20240102000000&filter=in")

    assert response.status_code == 200
    data = response.get_json()

    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["sessionId"] == 1001
    assert data[0]["direction"] == "in"
    assert data[0]["bruto"] == 5000
    assert data[0]["neto"] == 2000
    assert data[0]["produce"] == "orange"
    assert data[0]["containers"] == ["C1", "C2"]


# 2. Success case: neto is NULL in DB -> should become "na"
@patch("app.get_db")
def test_get_weights_neto_none_becomes_na(mock_get_db, client):
    mock_conn, mock_cursor = make_mock_db()
    mock_get_db.return_value = mock_conn

    mock_cursor.fetchall.return_value = [
        {
            "id": 1002,
            "sessionId": 1002,
            "direction": "out",
            "bruto": 7000,
            "neto": None,
            "produce": "apple",
            "containers": "C3"
        }
    ]

    response = client.get("/weight?from=20240101000000&to=20240102000000&filter=out")

    assert response.status_code == 200
    data = response.get_json()

    assert len(data) == 1
    assert data[0]["sessionId"] == 1002
    assert data[0]["neto"] == "na"
    assert data[0]["containers"] == ["C3"]


# 3. Success case: empty containers string -> empty list
@patch("app.get_db")
def test_get_weights_empty_containers_becomes_empty_list(mock_get_db, client):
    mock_conn, mock_cursor = make_mock_db()
    mock_get_db.return_value = mock_conn

    mock_cursor.fetchall.return_value = [
        {
            "id": 1003,
            "sessionId": 1003,
            "direction": "none",
            "bruto": 500,
            "neto": None,
            "produce": "na",
            "containers": ""
        }
    ]

    response = client.get("/weight?from=20240101000000&to=20240102000000&filter=none")

    assert response.status_code == 200
    data = response.get_json()

    assert len(data) == 1
    assert data[0]["sessionId"] == 1003
    assert data[0]["containers"] == []


# 4. Edge case: no results found
@patch("app.get_db")
def test_get_weights_empty(mock_get_db, client):
    mock_conn, mock_cursor = make_mock_db()
    mock_get_db.return_value = mock_conn

    mock_cursor.fetchall.return_value = []

    response = client.get("/weight?from=20200101000000&to=20200101000001")

    assert response.status_code == 200
    data = response.get_json()
    assert "message" in data
    assert "No weighing sessions exist" in data["message"]

    mock_cursor.execute.assert_called_once()
    mock_cursor.fetchall.assert_called_once()


# 5. Edge case: invalid date format
def test_get_weights_invalid_date(client):
    response = client.get("/weight?from=2024-01-01")
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "Invalid date format" in data["error"]


# 6. Edge case: invalid filter
def test_get_weights_invalid_filter(client):
    response = client.get("/weight?filter=truck")
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "Invalid filter" in data["error"]


# 7. Edge case: future date range
def test_get_weights_future_date(client):
    response = client.get("/weight?from=20990101000000&to=21000101000000")

    assert response.status_code == 200
    data = response.get_json()
    assert "message" in data
    assert "future time range" in data["message"]


# 8. Edge case: reversed range
def test_get_weights_reversed_range(client):
    response = client.get("/weight?from=20240102000000&to=20240101000000")

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "from" in data["error"] or "Invalid range" in data["error"]


# 9. Edge case: invalid DB exception returns 500
@patch("app.get_db")
def test_get_weights_db_error_returns_500(mock_get_db, client):
    mock_get_db.side_effect = Exception("DB crashed")

    response = client.get("/weight?from=20240101000000&to=20240102000000")

    assert response.status_code == 500
    data = response.get_json()
    assert "error" in data
    assert data["error"] == "Internal database error"