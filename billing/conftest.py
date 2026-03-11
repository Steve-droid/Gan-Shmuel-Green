import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import pytest
import mysql.connector
import os

# Set test DB env vars before the app is imported so get_db_connection() picks them up
os.environ.setdefault("DB_HOST", "127.0.0.1")
os.environ.setdefault("DB_PORT", "3308")
os.environ.setdefault("DB_USER", "root")
os.environ.setdefault("DB_PASSWORD", "testpass")
os.environ.setdefault("DB_NAME", "billdb")

from app import create_app
@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def db_connection():
    con = mysql.connector.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"]
    )
    yield con
    cursor = con.cursor()
    cursor.execute("DELETE FROM Rates")
    cursor.execute("DELETE FROM Trucks")
    cursor.execute("DELETE FROM Provider")
    con.commit()
    con.close()
