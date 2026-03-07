# to run: python3 -m pytest tests/test_post_batch_weight.py -v

import json
import pytest
from unittest.mock import patch
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ─── Missing / bad input ──────────────────────────────────────────────────────

def test_missing_file_param_returns_400(client):
    resp = client.post("/batch-weight", json={})
    assert resp.status_code == 400
    assert "file" in resp.get_json()["error"].lower()


def test_file_not_found_returns_404(client):
    with patch("app.os.path.exists", return_value=False):
        resp = client.post("/batch-weight", json={"file": "missing.csv"})
    assert resp.status_code == 404


# ─── CSV (kg) ─────────────────────────────────────────────────────────────────

@patch("app.upsert_containers")
def test_csv_kg_parses_and_upserts(mock_upsert, client, tmp_path):
    f = tmp_path / "containers.csv"
    f.write_text("id,kg\nC-001,200\nC-002,150\n")

    with patch("app.IN_FOLDER", str(tmp_path)):
        resp = client.post("/batch-weight", json={"file": "containers.csv"})

    assert resp.status_code == 201
    assert resp.get_json()["message"] == "Loaded 2 containers"
    mock_upsert.assert_called_once()
    containers = mock_upsert.call_args[0][0]
    assert containers[0].container_id == "C-001"
    assert containers[0].weight == 200
    assert containers[0].unit == "kg"


# ─── CSV (lbs) ────────────────────────────────────────────────────────────────

@patch("app.upsert_containers")
def test_csv_lbs_parses_and_upserts(mock_upsert, client, tmp_path):
    f = tmp_path / "containers.csv"
    f.write_text("id,lbs\nC-003,440\nC-004,880\n")

    with patch("app.IN_FOLDER", str(tmp_path)):
        resp = client.post("/batch-weight", json={"file": "containers.csv"})

    assert resp.status_code == 201
    containers = mock_upsert.call_args[0][0]
    assert containers[0].unit == "lbs"
    assert containers[0].weight == 440


# ─── JSON ─────────────────────────────────────────────────────────────────────

@patch("app.upsert_containers")
def test_json_parses_and_upserts(mock_upsert, client, tmp_path):
    f = tmp_path / "containers.json"
    f.write_text(json.dumps([
        {"id": "C-010", "weight": 300, "unit": "kg"},
        {"id": "C-011", "weight": 500, "unit": "lbs"},
    ]))

    with patch("app.IN_FOLDER", str(tmp_path)):
        resp = client.post("/batch-weight", json={"file": "containers.json"})

    assert resp.status_code == 201
    assert resp.get_json()["message"] == "Loaded 2 containers"
    containers = mock_upsert.call_args[0][0]
    assert containers[0].container_id == "C-010"
    assert containers[1].unit == "lbs"


# ─── Bad file formats ─────────────────────────────────────────────────────────

def test_unsupported_extension_returns_400(client, tmp_path):
    f = tmp_path / "data.txt"
    f.write_text("C-001,200\n")

    with patch("app.IN_FOLDER", str(tmp_path)):
        resp = client.post("/batch-weight", json={"file": "data.txt"})

    assert resp.status_code == 400
    assert "unsupported" in resp.get_json()["error"].lower()


def test_csv_bad_unit_header_returns_400(client, tmp_path):
    f = tmp_path / "bad.csv"
    f.write_text("id,pounds\nC-001,200\n")

    with patch("app.IN_FOLDER", str(tmp_path)):
        resp = client.post("/batch-weight", json={"file": "bad.csv"})

    assert resp.status_code == 400


def test_json_missing_fields_returns_400(client, tmp_path):
    f = tmp_path / "bad.json"
    f.write_text(json.dumps([{"id": "C-001", "weight": 100}]))  # missing "unit"

    with patch("app.IN_FOLDER", str(tmp_path)):
        resp = client.post("/batch-weight", json={"file": "bad.json"})

    assert resp.status_code == 400


def test_json_invalid_unit_returns_400(client, tmp_path):
    f = tmp_path / "bad.json"
    f.write_text(json.dumps([{"id": "C-001", "weight": 100, "unit": "pounds"}]))

    with patch("app.IN_FOLDER", str(tmp_path)):
        resp = client.post("/batch-weight", json={"file": "bad.json"})

    assert resp.status_code == 400


# ─── Empty file ───────────────────────────────────────────────────────────────

@patch("app.upsert_containers")
def test_empty_csv_loads_zero_containers(mock_upsert, client, tmp_path):
    f = tmp_path / "empty.csv"
    f.write_text("id,kg\n")  # header only, no rows

    with patch("app.IN_FOLDER", str(tmp_path)):
        resp = client.post("/batch-weight", json={"file": "empty.csv"})

    assert resp.status_code == 201
    assert resp.get_json()["message"] == "Loaded 0 containers"
