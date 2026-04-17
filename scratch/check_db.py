import sqlite3
import os

db_path = "data/dmarket_trading.db"
if not os.path.exists(db_path):
    print("DB not found")
else:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM virtual_inventory ORDER BY id DESC LIMIT 5")
    rows = cursor.fetchall()
    for row in rows:
        print(dict(row))
    conn.close()
