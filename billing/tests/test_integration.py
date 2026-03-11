from unittest.mock import patch, MagicMock
import pandas as pd
from io import BytesIO
import os

def test_health_integration(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.data == b"OK"

def test_post_truck_integration(client, db_connection):
    cursor = db_connection.cursor()
    cursor.execute(
        "INSERT INTO Provider (name) VALUES ('Test Provider')"
    )
    db_connection.commit()
    provider_id = cursor.lastrowid

    response = client.post("/truck", json={"id": "T-001", "provider": provider_id})

    assert response.status_code == 201
    assert response.get_json() == {"id": "T-001"}

    cursor.execute(
        "SELECT * FROM Trucks WHERE id = 'T-001'"
    )
    row = cursor.fetchone()
    assert row is not None

def test_put_truck_integration(client, db_connection):
    cursor = db_connection.cursor()
    cursor.execute(
        "INSERT INTO Provider (name) VALUES ('Provider A')"
    )
    db_connection.commit()
    provider_a_id = cursor.lastrowid

    cursor.execute("INSERT INTO Provider (name) VALUES ('Provider B')")
    db_connection.commit()
    provider_b_id = cursor.lastrowid

    cursor.execute("INSERT INTO Trucks (id, provider_id) VALUES ('T-001', %s)", (provider_a_id,))
    db_connection.commit()

    response = client.put("/truck/T-001", json={"provider": provider_b_id})

    assert response.status_code == 200
    assert response.get_json() == {"id": "T-001"}

    cursor.execute(
        "SELECT provider_id FROM Trucks WHERE id = 'T-001'"
    )
    row = cursor.fetchone()
    assert row[0] == provider_b_id

def test_get_truck_integration(client, db_connection):
    cursor = db_connection.cursor()
    cursor.execute(
        "INSERT INTO Provider (name) VALUES ('Test Provider')"
    )
    db_connection.commit()
    provider_id = cursor.lastrowid

    cursor.execute("INSERT INTO Trucks (id, provider_id) VALUES ('T-001', %s)", (provider_id,))
    db_connection.commit()

    mock_weight_response = MagicMock()
    mock_weight_response.json.return_value = {"tara": 5000, "sessions": [1, 2]}
    
    with patch("app.routes.truck.requests.get", return_value=mock_weight_response):
        response = client.get("/truck/T-001")
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == "T-001"
    assert data["tara"] == 5000
    assert data["sessions"] == [1, 2]


def test_get_bill_integration(client, db_connection):
    cursor = db_connection.cursor()
    cursor.execute("INSERT INTO Provider (name) VALUES ('Test Provider')")
    db_connection.commit()
    provider_id = cursor.lastrowid

    cursor.execute("INSERT INTO Trucks (id, provider_id) VALUES ('T-001', %s)", (provider_id,))
    cursor.execute("INSERT INTO Rates (product_id, rate, scope) VALUES ('orange', 10, 'ALL')")
    db_connection.commit()

    def mock_requests_get(url, **kwargs):
        mock_resp = MagicMock()
        if "/item/" in url:
            mock_resp.json.return_value = {"sessions": [100]}
        else:
            mock_resp.json.return_value = {"produce": "orange", "neto": 500}
        return mock_resp

    with patch("app.routes.bill.requests.get", side_effect=mock_requests_get):
        response = client.get(f"/bill/{provider_id}")

    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == str(provider_id)
    assert data["name"] == "Test Provider"
    assert data["truckCount"] == 1
    assert data["sessionCount"] == 1
    assert data["total"] == 5000
    assert data["products"][0]["product"] == "orange"
    assert data["products"][0]["amount"] == 500


def test_create_provider_integration(client, db_connection):
    response = client.post("/provider", json={"name": "TestProvider"})
    assert response.status_code == 201
    data = response.get_json()
    assert "id" in data

    cursor = db_connection.cursor()
    cursor.execute("SELECT name FROM Provider WHERE id=%s", (data["id"],))
    row = cursor.fetchone()
    assert row[0] == "TestProvider"

def test_update_provider_integration(client, db_connection):
    cursor = db_connection.cursor()
    cursor.execute("INSERT INTO Provider (name) VALUES ('OldName')")
    db_connection.commit()
    provider_id = cursor.lastrowid

    response = client.put(f"/provider/{provider_id}", json={"name": "NewName"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["name"] == "NewName"

    cursor.execute("SELECT name FROM Provider WHERE id=%s", (provider_id,))
    row = cursor.fetchone()
    assert row[0] == "NewName"

def test_list_providers_integration(client, db_connection):
    cursor = db_connection.cursor()
    cursor.execute("DELETE FROM Provider")
    cursor.executemany(
        "INSERT INTO Provider (name) VALUES (%s)", 
        [("Prov1",), ("Prov2",)]
    )
    db_connection.commit()

    response = client.get("/providers")
    assert response.status_code == 200
    data = response.get_json()
    names = [p["name"] for p in data]
    assert "Prov1" in names and "Prov2" in names

def test_upload_and_download_rates(client, db_connection):
    df = pd.DataFrame({
        "Product": [101, 102],
        "Rate": [10, 20],
        "Scope": ["A", "B"]
    })

    os.makedirs("in", exist_ok=True)
    excel_path = "in/rates_test.xlsx"
    df.to_excel(excel_path, index=False)

    try:
        response = client.post("/rates?file=rates_test.xlsx")
        assert response.status_code == 200
        assert response.get_json()["status"] == "all rates replaced"

        cursor = db_connection.cursor()
        cursor.execute("SELECT product_id, rate, scope FROM Rates ORDER BY product_id")
        rows = cursor.fetchall()
        assert rows == [("101", 10, "A"), ("102", 20, "B")]

        response = client.get("/rates")
        assert response.status_code == 200
        assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        downloaded_excel = BytesIO(response.data)
        df_downloaded = pd.read_excel(downloaded_excel)

        df_sorted = df.sort_values("Product").reset_index(drop=True)
        df_downloaded_sorted = df_downloaded.sort_values("Product").reset_index(drop=True)
        pd.testing.assert_frame_equal(df_sorted, df_downloaded_sorted)
    finally:
        os.remove(excel_path)
