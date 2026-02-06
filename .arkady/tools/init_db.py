import sqlite3
import os

db_path = r"D:\DMarket-Telegram-Bot-main\.arkady\memory\arkady_brain.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Создаем таблицу для хранения опыта фиксов
cursor.execute('''
CREATE TABLE IF NOT EXISTS fix_experience (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    problem_summary TEXT,
    solution_details TEXT,
    affected_files TEXT,
    status TEXT
)
''')

conn.commit()
conn.close()
print(f"[+] Arkady Brain initialized at {db_path}")
