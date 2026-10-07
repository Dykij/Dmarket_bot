"""Статическая проверка: в этих местах нет жёстких путей data/ (читает исходники, ничего не запускает)."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    "src/core/target_sniping/scheduler.py",
    "src/core/autonomous_scanner.py",
    "src/risk/error_reporter.py",
    "src/analysis/backtest/obi_regression.py",
]
MARKERS = ("WATCHDOG_", "def load_decision_logs")


@pytest.mark.parametrize("rel", FILES)
def test_no_hardcoded_data_default(rel):
    bad = [
        (i, line.strip())
        for i, line in enumerate((ROOT / rel).read_text(encoding="utf-8").splitlines(), 1)
        if any(m in line for m in MARKERS) and '"data/' in line
    ]
    assert not bad, f"hardcoded data/ path in {rel}: {bad}"
