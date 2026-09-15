import sqlite3

def apply_sqlite_pragmas(conn: sqlite3.Connection) -> None:
    """Apply standard performance and concurrency PRAGMAs for SQLite."""
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")  # Balance speed/reliability
    conn.execute("PRAGMA cache_size=-64000")   # 64MB cache
    conn.execute("PRAGMA temp_store=MEMORY")   # Temp tables in memory
    conn.execute("PRAGMA mmap_size=268435456") # 256MB memory-mapped I/O
