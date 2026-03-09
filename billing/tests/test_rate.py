import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from io import BytesIO


def test_upload_rates_missing_file_param(client):
    response = client.post("/rates")

    assert response.status_code == 400
    assert response.json["error"] == "file parameter required"


def test_upload_rates_file_not_found(client):
    with patch("app.routes.rates.os.path.exists", return_value=False):
        response = client.post("/rates?file=test.xlsx")

    assert response.status_code == 404
    assert response.json["error"] == "file not found"


def test_upload_rates_success(client):
    df = pd.DataFrame([
        {"Product": 1, "Rate": 10, "Scope": "A"},
        {"Product": 2, "Rate": 20, "Scope": "B"},
    ])

    mock_cursor = MagicMock()
    mock_con = MagicMock()
    mock_con.cursor.return_value = mock_cursor

    with patch("app.routes.rates.os.path.exists", return_value=True), \
         patch("app.routes.rates.pd.read_excel", return_value=df), \
         patch("app.routes.rates.get_db_connection", return_value=mock_con):

        response = client.post("/rates?file=test.xlsx")

    assert response.status_code == 200
    assert response.json["status"] == "all rates replaced"

    mock_cursor.execute.assert_any_call("DELETE FROM Rates")

    assert mock_cursor.execute.call_count >= 3
    mock_con.commit.assert_called_once()
    mock_con.close.assert_called_once()


def test_download_rates_success(client):
    df = pd.DataFrame([
        {"Product": 1, "Rate": 10, "Scope": "A"},
        {"Product": 2, "Rate": 20, "Scope": "B"},
    ])

    mock_con = MagicMock()

    with patch("app.routes.rates.get_db_connection", return_value=mock_con), \
         patch("app.routes.rates.pd.read_sql", return_value=df):

        response = client.get("/rates")

    assert response.status_code == 200
    assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"