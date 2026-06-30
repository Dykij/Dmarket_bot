"""
charts.py — Trading performance charts (v14.5).

Generates PNG charts from SQLite data for Telegram and local review:
  - Equity curve (daily)
  - Drawdown chart
  - P&L bar chart
  - Win/Loss pie chart

Uses matplotlib (already in requirements.txt).
"""

from __future__ import annotations

import io
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from src.db.price_history import price_db

logger = logging.getLogger("Charts")

try:
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


def generate_equity_chart(days: int = 30) -> Optional[io.BytesIO]:
    """Generate equity curve chart for last N days."""
    if not HAS_MATPLOTLIB:
        return None

    snapshots = price_db.get_equity_snapshots(days=days)
    if len(snapshots) < 2:
        return None

    dates = []
    totals = []
    cashes = []
    assets = []
    for s in snapshots:
        try:
            dates.append(datetime.fromtimestamp(s["ts"]))
        except (KeyError, TypeError):
            continue
        totals.append(float(s.get("total", 0)))
        cashes.append(float(s.get("cash", 0)))
        assets.append(float(s.get("assets", 0)))

    if len(dates) < 2:
        return None

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(dates, totals, "b-", linewidth=2, label="Total Equity")
    ax.fill_between(dates, 0, cashes, alpha=0.3, color="green", label="Cash")
    ax.fill_between(dates, cashes, totals, alpha=0.3, color="orange", label="Assets")
    ax.set_title("Equity Curve", fontsize=14)
    ax.set_ylabel("USD")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    fig.autofmt_xdate()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_pnl_chart(days: int = 30) -> Optional[io.BytesIO]:
    """Generate daily P&L bar chart."""
    if not HAS_MATPLOTLIB:
        return None

    snapshots = price_db.get_equity_snapshots(days=days)
    if len(snapshots) < 2:
        return None

    dates = []
    pnls = []
    prev_total = None
    for s in snapshots:
        try:
            d = datetime.fromtimestamp(s["ts"])
        except (KeyError, TypeError):
            continue
        total = float(s.get("total", 0))
        if prev_total is not None:
            dates.append(d)
            pnls.append(total - prev_total)
        prev_total = total

    if not pnls:
        return None

    colors = ["#2ecc71" if p >= 0 else "#e74c3c" for p in pnls]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(dates, pnls, color=colors, width=0.8)
    ax.axhline(y=0, color="gray", linestyle="-", linewidth=0.5)
    ax.set_title("Daily P&L", fontsize=14)
    ax.set_ylabel("USD")
    ax.grid(True, alpha=0.3, axis="y")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    fig.autofmt_xdate()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_drawdown_chart(days: int = 90) -> Optional[io.BytesIO]:
    """Generate drawdown chart with peak tracking."""
    if not HAS_MATPLOTLIB:
        return None

    snapshots = price_db.get_equity_snapshots(days=days)
    if len(snapshots) < 2:
        return None

    dates = []
    drawdowns = []
    peak = 0.0
    for s in snapshots:
        try:
            d = datetime.fromtimestamp(s["ts"])
        except (KeyError, TypeError):
            continue
        total = float(s.get("total", 0))
        if total > peak:
            peak = total
        dd = ((peak - total) / peak * 100) if peak > 0 else 0.0
        dates.append(d)
        drawdowns.append(dd)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.fill_between(dates, 0, drawdowns, alpha=0.5, color="#e74c3c")
    ax.plot(dates, drawdowns, "r-", linewidth=1)
    ax.set_title("Drawdown %", fontsize=14)
    ax.set_ylabel("%")
    ax.invert_yaxis()
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    fig.autofmt_xdate()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_win_loss_chart() -> Optional[io.BytesIO]:
    """Generate win/loss pie chart from virtual_inventory."""
    if not HAS_MATPLOTLIB:
        return None

    sold = price_db.get_virtual_inventory(status="sold")
    wins = 0
    losses = 0
    for s in sold:
        buy = float(s["buy_price"] or 0)
        sell = float(s["sell_price"] or 0)
        fee = float(s["fee_paid"] or 0)
        pnl = sell - buy - fee
        if pnl > 0:
            wins += 1
        elif pnl < 0:
            losses += 1

    if wins + losses == 0:
        return None

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.pie(
        [wins, losses],
        labels=[f"Wins ({wins})", f"Losses ({losses})"],
        colors=["#2ecc71", "#e74c3c"],
        autopct="%1.1f%%",
        startangle=90,
    )
    ax.set_title("Win/Loss Distribution", fontsize=14)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf
