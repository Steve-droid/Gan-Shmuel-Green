# to run the tests run : python3 -m pytest tests/test_get_item.py -v

import pytest # type: ignore
from unittest.mock import patch
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ─── Validation ───────────────────────────────────────────────────────────────

@patch("app.get_item_type", return_value=None)
def test_item_not_exists_returns_404(mock_type, client):
    resp = client.get("/item/NO_SUCH_ID?from=20260101000000&to=20260131235959")
    assert resp.status_code == 404


@patch("app.get_item_type", return_value="truck")
def test_invalid_from_format_returns_400(mock_type, client):
    resp = client.get("/item/T1?from=abc&to=20260131235959")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


@patch("app.get_item_type", return_value="truck")
def test_invalid_to_format_returns_400(mock_type, client):
    resp = client.get("/item/T1?from=20260101000000&to=bad")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


# ─── Happy Path: Truck ────────────────────────────────────────────────────────

@patch("app.get_sessions_for_truck", return_value=[1001, 1002])
@patch("app.get_truck_last_tara_kg", return_value=3500)
@patch("app.get_item_type", return_value="truck")
def test_get_item_truck_success(mock_type, mock_tara, mock_sessions, client):
    resp = client.get("/item/T1?from=20260101000000&to=20260131235959")
    assert resp.status_code == 200
    body = resp.get_json()

    assert body["id"] == "T1"
    assert body["tara"] == 3500
    assert body["sessions"] == [1001, 1002]


@patch("app.get_sessions_for_truck", return_value=[])
@patch("app.get_truck_last_tara_kg", return_value=None)
@patch("app.get_item_type", return_value="truck")
def test_get_item_truck_unknown_tara_returns_na(mock_type, mock_tara, mock_sessions, client):
    resp = client.get("/item/T1?from=20260101000000&to=20260131235959")
    assert resp.status_code == 200
    body = resp.get_json()

    assert body["id"] == "T1"
    assert body["tara"] == "na"
    assert body["sessions"] == []


# ─── Happy Path: Container ────────────────────────────────────────────────────

@patch("app.get_sessions_for_container", return_value=[2001])
@patch("app.get_container_tara_kg", return_value=220)
@patch("app.get_item_type", return_value="container")
def test_get_item_container_success(mock_type, mock_tara, mock_sessions, client):
    resp = client.get("/item/C1?from=20260101000000&to=20260131235959")
    assert resp.status_code == 200
    body = resp.get_json()

    assert body["id"] == "C1"
    assert body["tara"] == 220
    assert body["sessions"] == [2001]


@patch("app.get_sessions_for_container", return_value=[2001, 2002])
@patch("app.get_container_tara_kg", return_value=None)
@patch("app.get_item_type", return_value="container")
def test_get_item_container_unknown_tara_returns_na(mock_type, mock_tara, mock_sessions, client):
    resp = client.get("/item/C1?from=20260101000000&to=20260131235959")
    assert resp.status_code == 200
    body = resp.get_json()

    assert body["id"] == "C1"
    assert body["tara"] == "na"
    assert body["sessions"] == [2001, 2002]


# ─── Defaults (optional) ──────────────────────────────────────────────────────
# אם אצלכם ב-get_item יש ברירות מחדל ל-from/to,
# הטסט הזה בודק רק שמחזירים 200 עם פורמט נכון בלי פרמטרים.

@patch("app.get_sessions_for_truck", return_value=[1001])
@patch("app.get_truck_last_tara_kg", return_value=1111)
@patch("app.get_item_type", return_value="truck")
def test_get_item_defaults_no_from_to(mock_type, mock_tara, mock_sessions, client):
    resp = client.get("/item/T1")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["id"] == "T1"
    assert body["tara"] == 1111
    assert body["sessions"] == [1001]