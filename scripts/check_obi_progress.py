#!/usr/bin/env python3
"""Check OBI/OFI observation cycle progress.

Usage: python3 scripts/check_obi_progress.py [db_path]

Reports:
- Total scanned entries with OBI/OFI data
- Distribution by title
- Time range
- Comparison with power analysis target
"""

import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "data/dmarket_state.db"
TARGET_MIN = 200
TARGET_MAX = 500

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# Count scanned entries with OBI/OFI data
rows = conn.execute(
    "SELECT hash_name, details, timestamp FROM decision_logs "
    "WHERE decision = 'scanned' AND details IS NOT NULL "
    "ORDER BY timestamp"
).fetchall()

total = len(rows)
titles = Counter()
obi_values = []
ofi_values = []
timestamps = []

for row in rows:
    try:
        d = json.loads(row["details"])
        if "obi_norm" in d and "ofi" in d:
            titles[row["hash_name"]] += 1
            obi_values.append(d["obi_norm"])
            ofi_values.append(d["ofi"])
            timestamps.append(row["timestamp"])
    except (json.JSONDecodeError, TypeError):
        continue

print("=" * 60)
print("OBI/OFI OBSERVATION CYCLE PROGRESS")
print("=" * 60)
print()
print(f"Total scanned entries with OBI/OFI: {total}")
print(f"Target: {TARGET_MIN}-{TARGET_MAX} observations")
print(f"Progress: {total/TARGET_MAX*100:.0f}% (of max target)")
print()

if timestamps:
    first = datetime.fromtimestamp(timestamps[0])
    last = datetime.fromtimestamp(timestamps[-1])
    print(f"Time range: {first} → {last}")
    print(f"Duration: {(timestamps[-1] - timestamps[0]) / 3600:.1f} hours")
    print()

if titles:
    print(f"Unique titles: {len(titles)}")
    print("Top 10 by observation count:")
    for title, count in titles.most_common(10):
        print(f"  {title}: {count}")
    print()

if obi_values:
    import statistics
    print(f"OBI stats: mean={statistics.mean(obi_values):.3f}, "
          f"std={statistics.stdev(obi_values):.3f}, "
          f"min={min(obi_values):.3f}, max={max(obi_values):.3f}")
    print(f"OFI stats: mean={statistics.mean(ofi_values):.3f}, "
          f"std={statistics.stdev(ofi_values):.3f}, "
          f"min={min(ofi_values):.3f}, max={max(ofi_values):.3f}")
    print()

if total >= TARGET_MIN:
    print("STATUS: READY for regression calibration!")
else:
    print(f"STATUS: Need {TARGET_MIN - total} more observations.")

print("=" * 60)
conn.close()
