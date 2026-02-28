# Database layer for weight microservice
import mysql.connector
from mysql.connector import Error
from entity_models import Container, Transaction
from datetime import datetime
from typing import List, Optional

# MySQL connection configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'rootpass',
    'database': 'weight',
    'port': 3306
}


def get_db():
    """Get database connection"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        raise

def init_db():
    """Initialize database tables according to weightdb.sql schema"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Create database if not exists
    cursor.execute("CREATE DATABASE IF NOT EXISTS `weight`")
    cursor.execute("USE weight")
    
    # Table: containers_registered (for tara weights)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS `containers_registered` (
            `container_id` VARCHAR(15) NOT NULL,
            `weight` INT(12) DEFAULT NULL,
            `unit` VARCHAR(10) DEFAULT NULL,
            PRIMARY KEY (`container_id`)
        ) ENGINE=MyISAM
    ''')
    
    # Table: transactions (for weight sessions)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS `transactions` (
            `id` INT(12) NOT NULL AUTO_INCREMENT,
            `datetime` DATETIME DEFAULT NULL,
            `direction` VARCHAR(10) DEFAULT NULL,
            `truck` VARCHAR(50) DEFAULT NULL,
            `containers` VARCHAR(10000) DEFAULT NULL,
            `bruto` INT(12) DEFAULT NULL,
            `truckTara` INT(12) DEFAULT NULL,
            `neto` INT(12) DEFAULT NULL,
            `produce` VARCHAR(50) DEFAULT NULL,
            `sessionId` INT(12) DEFAULT NULL,
            PRIMARY KEY (`id`)
        ) ENGINE=MyISAM AUTO_INCREMENT=1001
    ''')
    
    conn.commit()
    cursor.close()
    conn.close()
    print("Database initialized successfully")

def test_connection():
    """Test database connection (for health check)"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Database connection test failed: {e}")
        return False


# ============================================================================
# Transaction CRUD operations
# ============================================================================

def insert_transaction(tx: Transaction) -> int:
    """Insert a transaction and return its ID"""
    conn = get_db()
    cursor = conn.cursor()
    
    db_dict = tx.to_db_dict()
    
    query = """
        INSERT INTO transactions 
        (datetime, direction, truck, containers, bruto, truckTara, neto, produce, sessionId)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    values = (
        db_dict['datetime'],
        db_dict['direction'],
        db_dict['truck'],
        db_dict['containers'],
        db_dict['bruto'],
        db_dict['truckTara'],
        db_dict['neto'],
        db_dict['produce'],
        db_dict['sessionId']
    )
    
    cursor.execute(query, values)
    conn.commit()
    tx_id = cursor.lastrowid
    cursor.close()
    conn.close()
    
    return tx_id



def get_last_transaction_for_truck(truck: str) -> Optional[Transaction]:
    """Get the most recent transaction for a truck"""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute(
        "SELECT * FROM transactions WHERE truck = %s ORDER BY datetime DESC, id DESC LIMIT 1",
        (truck,)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if row:
        return Transaction.from_db_row(row)
    return None


def update_transaction(tx_id: int, fields: dict) -> None:
    """Update specific fields of an existing transaction row (used for force overwrite)"""
    conn = get_db()
    cursor = conn.cursor()
    set_clause = ', '.join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [tx_id]
    cursor.execute(f"UPDATE transactions SET {set_clause} WHERE id = %s", values)
    conn.commit()
    cursor.close()
    conn.close()



def get_containers_tara(container_ids: List[str]) -> dict:
    """Get tara weights in KG for a list of container IDs.
    Returns {container_id: weight_kg} with None for containers not in the registry."""
    if not container_ids:
        return {}
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    placeholders = ','.join(['%s'] * len(container_ids))
    cursor.execute(
        f"SELECT container_id, weight, unit FROM containers_registered WHERE container_id IN ({placeholders})",
        container_ids
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    result = {cid: None for cid in container_ids}
    for row in rows:
        if row['weight'] is not None:
            weight = int(row['weight'])
            if row.get('unit', '').lower() == 'lbs':
                weight = int(round(weight * 0.45359237))
            result[row['container_id']] = weight
    return result


def get_last_open_in_for_truck(truck: str) -> Optional[Transaction]:
    """Get the truck's last 'in' transaction if it's still open (no matching 'out')"""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # Get last 'in' for truck
    cursor.execute(
        """SELECT * FROM transactions 
           WHERE truck = %s AND direction = 'in' 
           ORDER BY datetime DESC, id DESC LIMIT 1""",
        (truck,)
    )
    last_in = cursor.fetchone()
    
    if not last_in:
        cursor.close()
        conn.close()
        return None
    
    # Check if there's a matching 'out' with same sessionId
    cursor.execute(
        """SELECT COUNT(*) as cnt FROM transactions 
           WHERE truck = %s AND direction = 'out' AND sessionId = %s""",
        (truck, last_in['sessionId'])
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    
    # If no 'out' exists, the 'in' is still open
    if result and result['cnt'] == 0:
        return Transaction.from_db_row(last_in)
    return None

if __name__ == '__main__':
    init_db()
    if test_connection():
        print("✓ Database connection test passed")
