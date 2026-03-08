from unittest.mock import MagicMock, patch
from app import app
import pytest

@patch('app.get_db') # 1. Replace the real DB connection with a stunt double
def test_get_unknown_success(mock_get_db):
    # 2. Setup the "Stunt Double"
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    # 3. Tell the stunt double exactly what to say when asked for data
    # (Row 1: Transactions, Row 2: Registered)
    mock_cursor.fetchall.side_effect = [
        [("C-1,C-2",)], # Seen at scale
        [("C-1",)]      # Known in registry
    ]

    # 4. Trigger the real function using the Flask test client
    client = app.test_client()
    response = client.get('/unknown')

    # 5. The Verification (Assertion)
    assert response.status_code == 200
    assert response.get_json() == ["C-2"] # C-2 was seen but not known!