# Database layer - MySQL connection for weight microservice
import mysql.connector
from mysql.connector import Error

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
        ) ENGINE=MyISAM AUTO_INCREMENT=10001
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

if __name__ == '__main__':
    init_db()
    if test_connection():
        print("✓ Database connection test passed")
