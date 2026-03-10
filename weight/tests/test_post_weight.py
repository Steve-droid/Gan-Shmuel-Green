# to run the tests run : python3 -m pytest tests/test_post_weight.py -v



import pytest
from unittest.mock import patch, MagicMock
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ─── Validation ───────────────────────────────────────────────────────────────

def test_missing_direction_returns_400(client):
    resp = client.post("/weight", json={"weight": 1000, "unit": "kg"})
    assert resp.status_code == 400

def test_invalid_direction_returns_400(client):
    resp = client.post("/weight", json={
        "direction": "sideways", "truck": "T1",
        "weight": 1000, "unit": "kg",
        "containers": "", "produce": "orange"
    })
    assert resp.status_code == 400

def test_missing_truck_for_in_returns_400(client):
    resp = client.post("/weight", json={
        "direction": "in",
        "weight": 1000, "unit": "kg",
        "containers": "C1", "produce": "orange"
    })
    assert resp.status_code == 400

def test_invalid_unit_returns_400(client):
    resp = client.post("/weight", json={
        "direction": "in", "truck": "T1",
        "weight": 1000, "unit": "tons",
        "containers": "C1", "produce": "orange"
    })
    assert resp.status_code == 400


# ─── Session Constraints ──────────────────────────────────────────────────────

@patch("app.get_last_open_in_for_truck", return_value=None)
@patch("app.get_last_transaction_for_truck", return_value=None)
def test_out_without_in_returns_400(mock_last_tx, mock_open_in, client):
    resp = client.post("/weight", json={
        "direction": "out", "truck": "T1",
        "weight": 3000, "unit": "kg", "containers": "", "produce": "orange"
    })
    assert resp.status_code == 400
    assert "error" in resp.get_json()


@patch("app.get_last_open_in_for_truck")
@patch("app.get_last_transaction_for_truck")
def test_in_after_in_without_force_returns_400(mock_last_tx, mock_open_in, client):
    # Simulate: truck already has an open "in"
    existing_in = MagicMock()
    existing_in.id = 1001
    existing_in.direction = "in"
    mock_open_in.return_value = existing_in
    mock_last_tx.return_value = existing_in

    resp = client.post("/weight", json={
        "direction": "in", "truck": "T1",
        "weight": 5000, "unit": "kg",
        "containers": "C1", "produce": "orange", "force": False
    })
    assert resp.status_code == 400
    assert "error" in resp.get_json()


@patch("app.get_last_open_in_for_truck")
@patch("app.get_last_transaction_for_truck")
def test_none_after_in_returns_400(mock_last_tx, mock_open_in, client):
    # Simulate: truck has an open "in", then we send "none" -> not allowed
    existing_in = MagicMock()
    existing_in.id = 1001
    existing_in.direction = "in"
    mock_open_in.return_value = existing_in
    mock_last_tx.return_value = existing_in

    resp = client.post("/weight", json={
        "direction": "none", "truck": "T1",
        "weight": 500, "unit": "kg", "containers": "", "produce": "na"
    })
    assert resp.status_code == 400
    assert "error" in resp.get_json()


@patch("app.get_last_open_in_for_truck", return_value=None)
@patch("app.get_last_transaction_for_truck")
def test_out_after_out_without_force_returns_400(mock_last_tx, mock_open_in, client):
    # Simulate: last transaction was an "out" and force is false
    last_out = MagicMock()
    last_out.direction = "out"
    mock_last_tx.return_value = last_out

    resp = client.post("/weight", json={
        "direction": "out", "truck": "T1",
        "weight": 3000, "unit": "kg", "containers": "", "produce": "orange", "force": False
    })
    assert resp.status_code == 400
    assert "error" in resp.get_json()


# ─── Happy Path ───────────────────────────────────────────────────────────────

@patch("app.insert_transaction", return_value=1001)
@patch("app.get_last_open_in_for_truck", return_value=None)
@patch("app.get_last_transaction_for_truck", return_value=None)
def test_normal_in(mock_last_tx, mock_open_in, mock_insert, client):
    resp = client.post("/weight", json={
        "direction": "in", "truck": "T1",
        "weight": 10000, "unit": "kg",
        "containers": "C1", "produce": "orange"
    })
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["id"] == 1001
    assert body["truck"] == "T1"
    assert body["bruto"] == 10000
    assert "truckTara" not in body
    assert "neto" not in body


@patch("app.get_containers_tara", return_value={"C1": 200})
@patch("app.insert_transaction", return_value=1002)
@patch("app.get_last_open_in_for_truck")
@patch("app.get_last_transaction_for_truck")
def test_normal_out(mock_last_tx, mock_open_in, mock_insert, mock_tara, client):
    # Simulate: truck came in with bruto=10000, container C1 tara=200
    open_in = MagicMock()
    open_in.id = 1001
    open_in.session_id = 1001
    open_in.bruto = 10000
    open_in.containers = ["C1"]
    open_in.direction = "in"
    mock_open_in.return_value = open_in
    mock_last_tx.return_value = open_in  # last tx was "in"

    resp = client.post("/weight", json={
        "direction": "out", "truck": "T1",
        "weight": 3000, "unit": "kg", "containers": "", "produce": "orange"
    })
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["id"] == 1001           # session id of the matching "in"
    assert body["truckTara"] == 3000    # "out" weight = truck tara
    assert body["neto"] == 10000 - 3000 - 200  # 6800


@patch("app.get_containers_tara", return_value={"C1": None})  # C1 weight unknown
@patch("app.insert_transaction", return_value=1002)
@patch("app.get_last_open_in_for_truck")
@patch("app.get_last_transaction_for_truck")
def test_out_unknown_container_neto_is_na(mock_last_tx, mock_open_in, mock_insert, mock_tara, client):
    open_in = MagicMock()
    open_in.id = 1001
    open_in.session_id = 1001
    open_in.bruto = 10000
    open_in.containers = ["C1"]
    open_in.direction = "in"
    mock_open_in.return_value = open_in
    mock_last_tx.return_value = open_in

    resp = client.post("/weight", json={
        "direction": "out", "truck": "T1",
        "weight": 3000, "unit": "kg", "containers": "", "produce": "orange"
    })
    assert resp.status_code == 201
    assert resp.get_json()["neto"] == "na"


@patch("app.insert_transaction", return_value=3001)
@patch("app.get_last_open_in_for_truck", return_value=None)
@patch("app.get_last_transaction_for_truck", return_value=None)
def test_none_direction(mock_last_tx, mock_open_in, mock_insert, client):
    resp = client.post("/weight", json={
        "direction": "none", "truck": "na",
        "weight": 500, "unit": "kg", "containers": "", "produce": "na"
    })
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["id"] == 3001
    assert body["bruto"] == 500


# ─── Force ────────────────────────────────────────────────────────────────────

@patch("app.update_transaction")
@patch("app.get_last_open_in_for_truck")
@patch("app.get_last_transaction_for_truck")
def test_force_in_updates_existing_row(mock_last_tx, mock_open_in, mock_update, client):
    existing_in = MagicMock()
    existing_in.id = 1001
    existing_in.direction = "in"
    mock_open_in.return_value = existing_in
    mock_last_tx.return_value = existing_in

    resp = client.post("/weight", json={
        "direction": "in", "truck": "T1",
        "weight": 9000, "unit": "kg",
        "containers": "C1", "produce": "orange", "force": True
    })
    assert resp.status_code == 201
    assert resp.get_json()["id"] == 1001   # same row, not a new one
    mock_update.assert_called_once()       # UPDATE was called, not INSERT


@patch("app.update_transaction")
@patch("app.get_containers_tara", return_value={})
@patch("app.get_last_open_in_for_truck")
@patch("app.get_last_transaction_for_truck")
def test_force_out_updates_existing_row(mock_last_tx, mock_open_in, mock_tara, mock_update, client):
    open_in = MagicMock()
    open_in.id = 1001
    open_in.session_id = 1001
    open_in.bruto = 10000
    open_in.containers = []
    open_in.direction = "in"

    last_out = MagicMock()
    last_out.id = 1002
    last_out.direction = "out"

    mock_open_in.return_value = open_in
    mock_last_tx.return_value = last_out

    resp = client.post("/weight", json={
        "direction": "out", "truck": "T1",
        "weight": 3000, "unit": "kg", "containers": "", "produce": "orange", "force": True
    })
    assert resp.status_code == 201
    mock_update.assert_called_once()       # UPDATE was called on the existing "out" row
