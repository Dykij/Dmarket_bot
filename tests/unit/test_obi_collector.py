"""Сборщик obi_collector: логика сетки, сбоев и остановки; замороженный список названий."""

import re
from pathlib import Path

from src.collector import obi_collector as oc

TITLES = Path(oc.__file__).with_name("titles_v1.txt")
TITLES_SHA256 = "980c94fead67eaf9ce8059b061afad6399ea55d602181d326003f05e87a2f523"
WEAR = re.compile(r"\((Factory New|Minimal Wear|Field-Tested|Well-Worn|Battle-Scarred)\)$")


def test_selftest_passes():
    oc.selftest()


def test_frozen_titles_list():
    titles, sha = oc.read_titles(TITLES)
    assert sha == TITLES_SHA256, "список названий заморожен на время 6-недельного теста"
    assert len(titles) == 300 and len(set(titles)) == 300
    assert all(WEAR.search(t) for t in titles)
    assert not any(re.match(r"^[a-z][a-z0-9_]*:", t) for t in titles)


def test_repo_root_is_derived_from_file_location():
    assert (oc.REPO / "src" / "collector" / "obi_collector.py").is_file()
