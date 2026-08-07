#!/usr/bin/env python3
"""Check OBI/OFI observation cycle progress with diversity metrics.

Usage: python3 scripts/check_obi_progress.py [db_path] [--json]

Reports:
- Total scanned entries with OBI/OFI data
- Distribution by title (top 10 + unique count)
- Distribution by hour-of-day (UTC)
- Duration and rate (entries/hour)
- Stopping criteria status (quantity, time, hour coverage, title diversity)
"""

import json
import sqlite3
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone

DB_PATH = "data/dmarket_state.db"
JSON_MODE = False
for arg in sys.argv[1:]:
    if arg == "--json":
        JSON_MODE = True
    elif not arg.startswith("-"):
        DB_PATH = arg

# Stopping criteria
MIN_ENTRIES = 500
MIN_DURATION_HOURS = 48
MIN_HOUR_BLOCKS = 4  # out of 6 possible blocks
MIN_UNIQUE_TITLES = 50
HOUR_BLOCKS = {
    "night (00-04 UTC)": range(0, 4),
    "early_morning (04-08 UTC)": range(4, 8),
    "morning (08-12 UTC)": range(8, 12),
    "afternoon (12-16 UTC)": range(12, 16),
    "evening (16-20 UTC)": range(16, 20),
    "night_late (20-24 UTC)": range(20, 24),
}

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

rows = conn.execute(
    "SELECT hash_name, details, timestamp FROM decision_logs "
    "WHERE decision = 'scanned' AND details IS NOT NULL "
    "ORDER BY timestamp"
).fetchall()

total = 0
titles = Counter()
hour_dist = Counter()
obi_values = []
ofi_values = []
timestamps = []

for row in rows:
    try:
        d = json.loads(row["details"])
        if "obi_norm" in d and "ofi" in d:
            total += 1
            titles[row["hash_name"]] += 1
            obi_values.append(d["obi_norm"])
            ofi_values.append(d["ofi"])
            ts = row["timestamp"]
            timestamps.append(ts)
            hour = datetime.fromtimestamp(ts, tz=timezone.utc).hour
            hour_dist[hour] += 1
    except (json.JSONDecodeError, TypeError):
        continue

# Calculate duration
duration_hours = 0.0
rate_per_hour = 0.0
if len(timestamps) >= 2:
    duration_hours = (timestamps[-1] - timestamps[0]) / 3600.0
    rate_per_hour = total / max(duration_hours, 0.01)

# Count covered hour blocks
covered_blocks = 0
block_details = {}
for block_name, hour_range in HOUR_BLOCKS.items():
    count = sum(hour_dist.get(h, 0) for h in hour_range)
    block_details[block_name] = count
    if count > 0:
        covered_blocks += 1

# Stopping criteria
criteria = {
    "quantity": total >= MIN_ENTRIES,
    "duration": duration_hours >= MIN_DURATION_HOURS,
    "hour_coverage": covered_blocks >= MIN_HOUR_BLOCKS,
    "title_diversity": len(titles) >= MIN_UNIQUE_TITLES,
}
all_met = all(criteria.values())

if JSON_MODE:
    result = {
        "total": total,
        "duration_hours": round(duration_hours, 1),
        "rate_per_hour": round(rate_per_hour, 0),
        "unique_titles": len(titles),
        "covered_hour_blocks": covered_blocks,
        "criteria": criteria,
        "all_criteria_met": all_met,
        "obi_mean": round(statistics.mean(obi_values), 4) if obi_values else 0,
        "ofi_mean": round(statistics.mean(ofi_values), 4) if ofi_values else 0,
    }
    print(json.dumps(result, indent=2))
else:
    print("=" * 60)
    print("OBI/OFI OBSERVATION CYCLE PROGRESS")
    print("=" * 60)
    print()
    print(f"Total scanned entries: {total}")
    print(f"Duration: {duration_hours:.1f} hours")
    print(f"Rate: {rate_per_hour:.0f} entries/hour")
    print(f"Unique titles: {len(titles)}")
    print()

    # Stopping criteria
    print("STOPPING CRITERIA:")
    status = lambda met: "✅" if met else "❌"
    print(f"  {status(criteria['quantity'])} Quantity: {total}/{MIN_ENTRIES}")
    print(f"  {status(criteria['duration'])} Duration: {duration_hours:.1f}h/{MIN_DURATION_HOURS}h")
    print(f"  {status(criteria['hour_coverage'])} Hour coverage: {covered_blocks}/{MIN_HOUR_BLOCKS} blocks")
    print(f"  {status(criteria['title_diversity'])} Title diversity: {len(titles)}/{MIN_UNIQUE_TITLES}")
    print()

    # Hour distribution
    if hour_dist:
        print("HOUR DISTRIBUTION (UTC):")
        for block_name, count in block_details.items():
            bar = "█" * min(count // 50, 40)
            print(f"  {block_name:30s} {count:6d} {bar}")
        print()

    # Top titles
    if titles:
        print(f"TOP 10 TITLES (of {len(titles)} unique):")
        for title, count in titles.most_common(10):
            print(f"  {title[:45]:45s} {count:6d}")
        print()

    # OBI/OFI stats
    if obi_values:
        print("OBI/OFI STATISTICS:")
        print(f"  OBI: mean={statistics.mean(obi_values):.4f}, std={statistics.stdev(obi_values):.4f}, "
              f"min={min(obi_values):.4f}, max={max(obi_values):.4f}")
        print(f"  OFI: mean={statistics.mean(ofi_values):.4f}, std={statistics.stdev(ofi_values):.4f}, "
              f"min={min(ofi_values):.4f}, max={max(ofi_values):.4f}")
        print()

    # Time range
    if timestamps:
        first = datetime.fromtimestamp(timestamps[0], tz=timezone.utc)
        last = datetime.fromtimestamp(timestamps[-1], tz=timezone.utc)
        print(f"TIME RANGE: {first.strftime('%Y-%m-%d %H:%M UTC')} → {last.strftime('%Y-%m-%d %H:%M UTC')}")
        print()

    if all_met:
        print("STATUS: ✅ ALL CRITERIA MET — ready for regression calibration!")
    else:
        remaining = [k for k, v in criteria.items() if not v]
        print(f"STATUS: ❌ Not ready — waiting for: {', '.join(remaining)}")

    print("=" * 60)

conn.close()
