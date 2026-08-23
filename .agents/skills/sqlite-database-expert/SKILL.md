---
name: sqlite-database-expert
description: 'Use when working with SQLite databases - queries, migrations, WAL mode, security, performance optimization. Trigger keywords: "SQLite", "database", "SQL query", "migration", "WAL mode", "parameterized query", "index", "schema". Essential for DMarket bot price history database.'
---

# SQLite Database Expert

Expert patterns for SQLite embedded database development with focus on security, performance, and migrations.

## When to Use

- Writing or reviewing SQL queries
- Designing database schema
- Optimizing query performance
- Implementing migrations
- Debugging SQLite issues

## Core Patterns

### 1. Connection Management

```python
import sqlite3
from contextlib import contextmanager
from typing import Generator

@contextmanager
def get_connection(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")  # Concurrent reads during writes
    conn.execute("PRAGMA busy_timeout=5000")  # Wait 5s on lock
    conn.execute("PRAGMA synchronous=NORMAL")  # Faster, still safe with WAL
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# Usage
with get_connection("data/dmarket_trading.db") as conn:
    conn.execute("INSERT INTO prices (item_id, price, timestamp) VALUES (?, ?, ?)",
                 (item_id, price, timestamp))
```

### 2. Parameterized Queries (SQL Injection Prevention)

```python
# WRONG - SQL injection vulnerability
def get_item_bad(item_id: str):
    query = f"SELECT * FROM items WHERE id = '{item_id}'"  # DANGEROUS!
    return conn.execute(query).fetchall()

# RIGHT - Parameterized query
def get_item_good(item_id: str):
    query = "SELECT * FROM items WHERE id = ?"
    return conn.execute(query, (item_id,)).fetchall()

# WRONG - f-string in SQL
def search_items_bad(search: str):
    query = f"SELECT * FROM items WHERE title LIKE '%{search}%'"  # DANGEROUS!

# RIGHT - Parameterized
def search_items_good(search: str):
    query = "SELECT * FROM items WHERE title LIKE ?"
    return conn.execute(query, (f"%{search}%",)).fetchall()
```

### 3. Batch Operations

```python
def insert_prices_batch(conn: sqlite3.Connection, prices: list[tuple]):
    """Batch insert for better performance."""
    conn.executemany(
        "INSERT INTO prices (item_id, price, timestamp) VALUES (?, ?, ?)",
        prices
    )
    conn.commit()

# For large batches, use transactions
def insert_large_batch(conn: sqlite3.Connection, prices: list[tuple]):
    """Insert in chunks to avoid memory issues."""
    chunk_size = 1000
    for i in range(0, len(prices), chunk_size):
        chunk = prices[i:i + chunk_size]
        conn.executemany(
            "INSERT INTO prices (item_id, price, timestamp) VALUES (?, ?, ?)",
            chunk
        )
    conn.commit()
```

### 4. Schema Migrations

```python
def migrate(conn: sqlite3.Connection):
    """Run database migrations."""
    # Create migrations table if not exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS migrations (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Get applied migrations
    applied = {row[0] for row in conn.execute("SELECT name FROM migrations").fetchall()}

    # Define migrations
    migrations = [
        ("001_create_prices_table", """
            CREATE TABLE IF NOT EXISTS prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id TEXT NOT NULL,
                price REAL NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                UNIQUE(item_id, timestamp)
            )
        """),
        ("002_add_index_prices_item", """
            CREATE INDEX IF NOT EXISTS idx_prices_item_id ON prices(item_id)
        """),
        ("003_add_trades_table", """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id TEXT NOT NULL,
                buy_price REAL NOT NULL,
                sell_price REAL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """),
    ]

    # Apply pending migrations
    for name, sql in migrations:
        if name not in applied:
            conn.execute(sql)
            conn.execute("INSERT INTO migrations (name) VALUES (?)", (name,))
            print(f"Applied migration: {name}")

    conn.commit()
```

### 5. Performance Optimization

```python
def optimize_database(conn: sqlite3.Connection):
    """Optimize SQLite performance."""
    # Enable WAL mode for concurrent access
    conn.execute("PRAGMA journal_mode=WAL")

    # Set cache size (negative = KB, positive = pages)
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache

    # Optimize for speed over safety (WAL makes this safe)
    conn.execute("PRAGMA synchronous=NORMAL")

    # Enable memory-mapped I/O
    conn.execute("PRAGMA mmap_size=268435456")  # 256MB

    # Analyze for query optimizer
    conn.execute("ANALYZE")
```

### 6. Full-Text Search

```python
def setup_fts(conn: sqlite3.Connection):
    """Setup Full-Text Search for item titles."""
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
            title,
            content='items',
            content_rowid='id'
        )
    """)

    # Populate FTS index
    conn.execute("""
        INSERT INTO items_fts (rowid, title)
        SELECT id, title FROM items
    """)

def search_items_fts(conn: sqlite3.Connection, query: str):
    """Search items using FTS."""
    return conn.execute("""
        SELECT items.* FROM items
        JOIN items_fts ON items.id = items_fts.rowid
        WHERE items_fts MATCH ?
        ORDER BY rank
    """, (query,)).fetchall()
```

## Anti-patterns

### String concatenation in SQL
**Symptom:** SQL injection vulnerability
**Fix:** Always use parameterized queries (`?` placeholders)

### No WAL mode
**Symptom:** "database is locked" errors
**Fix:** `PRAGMA journal_mode=WAL`

### No indexes on frequent queries
**Symptom:** Slow queries on large tables
**Fix:** Add indexes on columns used in WHERE, JOIN, ORDER BY

### Committing after every insert
**Symptom:** Slow insert performance
**Fix:** Batch inserts, commit once per batch

### No busy timeout
**Symptom:** Immediate failure on lock contention
**Fix:** `PRAGMA busy_timeout=5000`
