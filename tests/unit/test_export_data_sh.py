"""export_data.sh: ветка data создаётся с нуля, данные сжимаются и пушатся, повтор безвреден."""

import gzip
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "src" / "collector" / "export_data.sh"

pytestmark = pytest.mark.skipif(
    not (shutil.which("bash") and shutil.which("git") and shutil.which("gzip")),
    reason="нужны bash, git и gzip",
)


@pytest.fixture(autouse=True)
def _isolate_git(tmp_path, monkeypatch):
    real_git = "/usr/bin/git" if os.access("/usr/bin/git", os.X_OK) else shutil.which("git")
    shim = tmp_path / "_git_shim"
    shim.mkdir()
    git_bin = shim / "git"
    git_bin.write_text(f'#!/bin/sh\nexec {real_git} "$@"\n')
    git_bin.chmod(0o755)
    monkeypatch.setenv("PATH", f"{shim}:{os.environ.get('PATH', '')}")
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file")


def sh(*args, cwd=None):
    return subprocess.run(
        ["bash", str(SCRIPT), *map(str, args)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
    )


def git(*args, cwd=None):
    return subprocess.run(
        ["git", *map(str, args)], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def make_raw(d: Path, tag: str = "T1"):
    d.mkdir(parents=True, exist_ok=True)
    (d / f"snap_{tag}.csv").write_text("tick_ts,name\n1,a\n2,b\n")
    (d / f"ticks_{tag}.csv").write_text("tick_ts,status\n1,ok\n")
    (d / f"run_{tag}.json").write_text('{"tag": "%s"}\n' % tag)


def test_prepare_export_roundtrip(tmp_path):
    bare = tmp_path / "remote.git"
    git("init", "--bare", "--quiet", bare)
    url = bare.as_uri()
    assert url.startswith("file://")

    work = tmp_path / "w1"
    r = sh("prepare", url, work)
    assert r.returncode == 0, r.stderr
    assert (work / "README.md").is_file()

    raw = tmp_path / "raw"
    make_raw(raw)
    r = sh("export", raw, work, "run1")
    assert r.returncode == 0, r.stderr
    assert "push ok" in r.stdout

    check = tmp_path / "check"
    git("clone", "--quiet", "--branch", "data", url, check)
    snaps = list(check.glob("snapshots/*/*/*/snap_T1.csv.gz"))
    assert len(snaps) == 1
    assert gzip.decompress(snaps[0].read_bytes()).decode().startswith("tick_ts,name")
    assert list(check.glob("snapshots/*/*/*/ticks_T1.csv.gz"))
    assert list(check.glob("snapshots/*/*/*/run_T1.json"))

    # повторный экспорт тех же данных: изменений нет, код 0
    r = sh("export", raw, work, "run1-again")
    assert r.returncode == 0 and "изменений нет" in r.stdout

    # вторая «сессия» клонирует уже существующую ветку и добавляет свои файлы
    work2 = tmp_path / "w2"
    r = sh("prepare", url, work2)
    assert r.returncode == 0 and "найдена" in r.stdout
    raw2 = tmp_path / "raw2"
    make_raw(raw2, "T2")
    assert sh("export", raw2, work2, "run2").returncode == 0
    fresh = tmp_path / "fresh"
    git("clone", "--quiet", "--branch", "data", url, fresh)
    assert len(list(fresh.glob("snapshots/*/*/*/snap_T*.csv.gz"))) == 2


def test_export_empty_raw_fails(tmp_path):
    bare = tmp_path / "remote.git"
    git("init", "--bare", "--quiet", bare)
    work = tmp_path / "w"
    assert sh("prepare", bare.as_uri(), work).returncode == 0
    empty = tmp_path / "empty"
    empty.mkdir()
    r = sh("export", empty, work, "x")
    assert r.returncode == 1


def test_unknown_command(tmp_path):
    assert sh("bogus").returncode == 2


def test_git_shim_refuses_remote_protocols():
    for proto_url in ["https://example.invalid/x.git", "ssh://git@example.invalid/x.git"]:
        r = subprocess.run(
            ["git", "ls-remote", proto_url],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        assert r.returncode != 0
        assert "not allowed" in r.stderr
