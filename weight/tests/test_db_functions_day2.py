# Integration tests for db.py  *require a real MySQL instance*
#
# How to run:
#   docker compose -f docker-compose.test.yml up   # start test DB
#   DB_PORT=3307 DB_NAME=weight_test python3 -m pytest tests/test_db_integration.py -v
#   docker compose -f docker-compose.test.yml down    # tear down

import pytest
import mysql.connector
from datetime import datetime, timezone

import db as db_module
from db import (
    insert_transaction,
    get_last_transaction_for_truck,
    update_transaction,
    upsert_containers,
    get_containers_tara,
    get_last_open_in_for_truck,
)
from entity_models import Transaction, Container

# --- Test DB wiring --------------------------------------------------------

TEST_DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'rootpass',
    'database': 'weight_test',
    'port': 3307,
}


@pytest.fixture(scope='session', autouse=True)
def use_test_db():
    """Point all db.py calls at the test database for this session."""
    db_module.DB_CONFIG.update(TEST_DB_CONFIG)
    yield


@pytest.fixture(scope='session')
def create_tables(use_test_db):
    """Create tables once per test session."""
    conn = mysql.connector.connect(**TEST_DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS `containers_registered` (
            `container_id` VARCHAR(15) NOT NULL,
            `weight`       INT(12)     DEFAULT NULL,
            `unit`         VARCHAR(10) DEFAULT NULL,
            PRIMARY KEY (`container_id`)
        ) ENGINE=InnoDB
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS `transactions` (
            `id`        INT(12)       NOT NULL AUTO_INCREMENT,
            `datetime`  DATETIME      DEFAULT NULL,
            `direction` VARCHAR(10)   DEFAULT NULL,
            `truck`     VARCHAR(50)   DEFAULT NULL,
            `containers` VARCHAR(10000) DEFAULT NULL,
            `bruto`     INT(12)       DEFAULT NULL,
            `truckTara` INT(12)       DEFAULT NULL,
            `neto`      INT(12)       DEFAULT NULL,
            `produce`   VARCHAR(50)   DEFAULT NULL,
            `sessionId` INT(12)       DEFAULT NULL,
            PRIMARY KEY (`id`)
        ) ENGINE=InnoDB AUTO_INCREMENT=1001
    """)
    conn.commit()
    cursor.close()
    conn.close()
    yield


@pytest.fixture(autouse=True)
def clean_tables(create_tables):
    """Wipe both tables before each test so tests are independent."""
    conn = mysql.connector.connect(**TEST_DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions")
    cursor.execute("DELETE FROM containers_registered")
    conn.commit()
    cursor.close()
    conn.close()
    yield


# --- Helpers --------------------------------------------------------

def make_in_tx(truck="T1", bruto=10000, produce="orange", containers=None):
    return Transaction(
        datetime=datetime.now(timezone.utc),
        direction="in",
        truck=truck,
        containers=containers or ["C-001"],
        bruto=bruto,
        truck_tara=None,
        neto=None,
        produce=produce,
        session_id=None,
    )


def make_out_tx(truck="T1", bruto=5000, session_id=None):
    return Transaction(
        datetime=datetime.now(timezone.utc),
        direction="out",
        truck=truck,
        containers=[],
        bruto=bruto,
        truck_tara=bruto,
        neto=5000,
        produce="orange",
        session_id=session_id,
    )


# --- insert_transaction --------------------------------------------------------

def test_insert_returns_integer_id():
    tx_id = insert_transaction(make_in_tx())
    assert isinstance(tx_id, int)
    assert tx_id >= 1001  # AUTO_INCREMENT starts at 1001


def test_insert_persists_fields():
    tx_id = insert_transaction(make_in_tx(truck="T42", bruto=8000, produce="tomato"))
    result = get_last_transaction_for_truck("T42")
    assert result is not None
    assert result.id == tx_id
    assert result.truck == "T42"
    assert result.bruto == 8000
    assert result.produce == "tomato"
    assert result.direction == "in"


def test_insert_two_transactions_get_different_ids():
    id1 = insert_transaction(make_in_tx(truck="T1"))
    id2 = insert_transaction(make_in_tx(truck="T2"))
    assert id1 != id2


# --- get_last_transaction_for_truck ------------------------------------------------------

def test_get_last_tx_unknown_truck_returns_none():
    assert get_last_transaction_for_truck("UNKNOWN") is None


def test_get_last_tx_returns_most_recent():
    insert_transaction(make_in_tx(truck="T1", bruto=5000))
    insert_transaction(make_in_tx(truck="T1", bruto=9000))
    result = get_last_transaction_for_truck("T1")
    assert result.bruto == 9000


def test_get_last_tx_ignores_other_trucks():
    insert_transaction(make_in_tx(truck="T1", bruto=1000))
    insert_transaction(make_in_tx(truck="T2", bruto=2000))
    result = get_last_transaction_for_truck("T1")
    assert result.bruto == 1000


# --- update_transaction --------------------------------------------------------

def test_update_changes_specified_fields():
    tx_id = insert_transaction(make_in_tx(truck="T1", bruto=5000))
    update_transaction(tx_id, {'bruto': 6000, 'produce': 'tomato'})
    result = get_last_transaction_for_truck("T1")
    assert result.bruto == 6000
    assert result.produce == "tomato"


def test_update_does_not_touch_other_fields():
    tx_id = insert_transaction(make_in_tx(truck="T1", bruto=5000, produce="orange"))
    update_transaction(tx_id, {'bruto': 6000})
    result = get_last_transaction_for_truck("T1")
    assert result.produce == "orange"  # unchanged
    assert result.truck == "T1"        # unchanged


# --- upsert_containers --------------------------------------------------------

def test_upsert_inserts_new_containers():
    upsert_containers([
        Container(container_id="C-001", weight=200, unit="kg"),
        Container(container_id="C-002", weight=150, unit="kg"),
    ])
    result = get_containers_tara(["C-001", "C-002"])
    assert result["C-001"] == 200
    assert result["C-002"] == 150


def test_upsert_updates_existing_container():
    upsert_containers([Container(container_id="C-001", weight=200, unit="kg")])
    upsert_containers([Container(container_id="C-001", weight=999, unit="kg")])
    result = get_containers_tara(["C-001"])
    assert result["C-001"] == 999


def test_upsert_empty_list_does_nothing():
    upsert_containers([])  # should not raise


# --- get_containers_tara --------------------------------------------------------

def test_containers_tara_unknown_returns_none():
    result = get_containers_tara(["UNKNOWN"])
    assert result["UNKNOWN"] is None


def test_containers_tara_converts_lbs_to_kg():
    upsert_containers([Container(container_id="C-LBS", weight=440, unit="lbs")])
    result = get_containers_tara(["C-LBS"])
    expected = int(round(440 * 0.45359237))
    assert result["C-LBS"] == expected


def test_containers_tara_keeps_kg_as_is():
    upsert_containers([Container(container_id="C-KG", weight=300, unit="kg")])
    result = get_containers_tara(["C-KG"])
    assert result["C-KG"] == 300


def test_containers_tara_empty_list():
    assert get_containers_tara([]) == {}


def test_containers_tara_mixed_known_unknown():
    upsert_containers([Container(container_id="C-001", weight=100, unit="kg")])
    result = get_containers_tara(["C-001", "C-999"])
    assert result["C-001"] == 100
    assert result["C-999"] is None


# --- get_last_open_in_for_truck --------------------------------------------------------

def test_open_in_unknown_truck_returns_none():
    assert get_last_open_in_for_truck("UNKNOWN") is None


def test_open_in_returns_in_with_no_out():
    tx_id = insert_transaction(make_in_tx(truck="T1"))
    update_transaction(tx_id, {'sessionId': tx_id})

    result = get_last_open_in_for_truck("T1")
    assert result is not None
    assert result.truck == "T1"
    assert result.direction == "in"


def test_open_in_returns_none_after_matching_out():
    in_id = insert_transaction(make_in_tx(truck="T1"))
    update_transaction(in_id, {'sessionId': in_id})

    out_id = insert_transaction(make_out_tx(truck="T1", session_id=in_id))

    result = get_last_open_in_for_truck("T1")
    assert result is None


def test_open_in_returns_none_for_truck_with_no_in():
    insert_transaction(make_out_tx(truck="T1", session_id=9999))
    assert get_last_open_in_for_truck("T1") is None
