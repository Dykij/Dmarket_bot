import os
import sqlite3
import pytest

DB_PATH = "tests_temp.db"

@pytest.fixture
def temp_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mock_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skin_name TEXT,
            price REAL,
            status TEXT
        )
    ''')
    conn.commit()
    yield conn
    conn.close()
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_db_insert_lock(temp_db):
    """Verifies that SQLite handles standard mock insertions smoothly without structural locking."""
    cursor = temp_db.cursor()
    cursor.execute("INSERT INTO mock_orders (skin_name, price, status) VALUES (?, ?, ?)", 
                   ("AK-47 Slate", 5.50, "SIMULATED_BUY"))
    temp_db.commit()
    
    cursor.execute("SELECT * FROM mock_orders")
    rows = cursor.fetchall()
    
    assert len(rows) == 1
    assert rows[0][1] == "AK-47 Slate"
    assert rows[0][2] == 5.50
