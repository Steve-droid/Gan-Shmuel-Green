import pytest
from unittest.mock import MagicMock, patch
from app.routes.provider import create_provider, update_provider, get_all_providers

def test_create_provider_success():
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = 123
    mock_con = MagicMock()
    mock_con.cursor.return_value = mock_cursor

    with patch("app.routes.provider.get_db_connection", return_value=mock_con):
        provider_id = create_provider("Test Provider")
    
    assert provider_id == 123
    mock_cursor.execute.assert_called_with("INSERT INTO Provider (name) VALUES (%s)", ("Test Provider",))
    mock_con.commit.assert_called_once()
    mock_con.close.assert_called_once()

def test_update_provider_success():
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 1
    mock_con = MagicMock()
    mock_con.cursor.return_value = mock_cursor

    with patch("app.routes.provider.get_db_connection", return_value=mock_con):
        result = update_provider(1, "New Name")

    assert result is True
    mock_cursor.execute.assert_called_with("UPDATE Provider SET name = %s WHERE id = %s", ("New Name", 1))
    mock_con.commit.assert_called_once()
    mock_con.close.assert_called_once()

