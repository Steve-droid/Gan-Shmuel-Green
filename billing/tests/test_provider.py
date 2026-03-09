import pytest
import _json
from unittest.mock import MagicMock, patch
from app import create_app
from app.routes.provider import create_provider, update_provider

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

def test_create_provider_empty_name():
    with patch("app.routes.provider.get_db_connection") as mock_conn:
        provider_id = create_provider("")
    assert provider_id is None or provider_id == 0  
    mock_conn.assert_not_called()

def test_update_provider_empty_name():
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 0  
    mock_con = MagicMock()
    mock_con.cursor.return_value = mock_cursor

    with patch("app.routes.provider.get_db_connection", return_value=mock_con):
        result = update_provider(1, "")
    assert result is False  
    mock_con.close.assert_called_once()

def test_update_provider_nonexistent_id():
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 0  
    mock_con = MagicMock()
    mock_con.cursor.return_value = mock_cursor

    with patch("app.routes.provider.get_db_connection", return_value=mock_con):
        result = update_provider(999, "Some Name")
    assert result is False
    mock_con.commit.assert_not_called()  
    mock_con.close.assert_called_once()