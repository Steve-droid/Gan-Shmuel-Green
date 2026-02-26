# Seed data script - populate database with mock data
from db import get_db
from datetime import datetime, timedelta

def seed_containers():
    """Add sample container tara weights"""
    conn = get_db()
    cursor = conn.cursor()
    
    containers = [
        ('C001', 500, 'kg'),
        ('C002', 450, 'kg'),
        ('C003', 520, 'kg'),
        ('C004', 480, 'kg'),
        ('C005', 510, 'kg'),
    ]
    
    query = "INSERT IGNORE INTO containers_registered (container_id, weight, unit) VALUES (%s, %s, %s)"
    cursor.executemany(query, containers)
    
    conn.commit()
    cursor.close()
    conn.close()
    print(f"✓ Inserted {len(containers)} containers")


def seed_transactions():
    """Add sample weight transactions"""
    conn = get_db()
    cursor = conn.cursor()
    
    base_time = datetime.now() - timedelta(days=7)
    
    transactions = [
        # (datetime, direction, truck, containers, bruto, truckTara, neto, produce, sessionId)
        (base_time, 'in', 'ABC-123', 'C001,C002', 15000, None, None, 'orange', 1001),
        (base_time + timedelta(hours=2), 'out', 'ABC-123', 'C001,C002', 10000, 5000, 4050, 'orange', 1001),
        
        (base_time + timedelta(days=1), 'in', 'XYZ-789', 'C003', 12000, None, None, 'tomato', 1002),
        (base_time + timedelta(days=1, hours=3), 'out', 'XYZ-789', 'C003', 8000, 4000, 3480, 'tomato', 1002),
        
        (base_time + timedelta(days=2), 'none', 'na', 'C004', 480, None, None, 'na', 1003),
        
        (base_time + timedelta(days=3), 'in', 'DEF-456', 'C005', 14000, None, None, 'orange', 1004),
    ]
    
    query = """
        INSERT INTO transactions 
        (datetime, direction, truck, containers, bruto, truckTara, neto, produce, sessionId)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.executemany(query, transactions)
    
    conn.commit()
    cursor.close()
    conn.close()
    print(f"✓ Inserted {len(transactions)} transactions")


def clear_all_data():
    """Clear all data from tables"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM transactions")
    cursor.execute("DELETE FROM containers_registered")
    
    conn.commit()
    cursor.close()
    conn.close()
    print("✓ Cleared all data")


if __name__ == '__main__':
    print("Seeding database with mock data...")
    clear_all_data()
    seed_containers()
    seed_transactions()
    print("\n✓ Database seeding complete!")
