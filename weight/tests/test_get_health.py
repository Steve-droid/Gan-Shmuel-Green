import pytest
from unittest.mock import patch
from app import app

@pytest.fixture
def client():
    """Fixture to provide a test client for the Flask app."""
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

def test_health_success(client):
    """
    Test /health returns 200 OK when the database connection is successful.
    Mocks test_connection to return True.
    """
    with patch("app.test_connection", return_value=True):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json() == {"status": "OK"}

def test_health_failure(client):
    """
    Test /health returns 500 Failure when the database connection fails.
    Mocks test_connection to return False.
    """
    with patch("app.test_connection", return_value=False):
        resp = client.get("/health")
        assert resp.status_code == 500
        assert resp.get_json() == {"status": "Failure"}