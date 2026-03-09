import pytest
import requests
import os

# Get the URL of the app container from environment variables
# Default to localhost if not set (for local testing)
APP_URL = os.getenv("APP_URL", "http://localhost:5000")

def test_app_health_endpoint():
    """
    CI Test: Checks if the remote Flask app container 
    returns a 200 OK from its health endpoint.
    """
    endpoint = f"{APP_URL}/health"
    
    try:
        response = requests.get(endpoint, timeout=5)
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'OK'
        
    except requests.exceptions.ConnectionError:
        pytest.fail(f"Could not connect to the App at {endpoint}. Is the container running?")