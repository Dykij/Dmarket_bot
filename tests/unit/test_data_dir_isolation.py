"""Изоляция каталога данных. ЧИСТЫЕ тесты: БД не создаются, файлы не удаляются."""
import os
import tempfile
from pathlib import Path

from src.utils import data_dir as data_dir_module
from src.utils.data_dir import get_data_dir

PROJECT_DATA = Path(data_dir_module.__file__).resolve().parents[2] / "data"


def test_env_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("DMARKET_DATA_DIR", str(tmp_path))
    assert get_data_dir() == tmp_path


def test_default_is_project_data_dir(monkeypatch):
    monkeypatch.delenv("DMARKET_DATA_DIR", raising=False)
    assert get_data_dir().resolve() == PROJECT_DATA.resolve()


def test_session_data_dir_is_isolated_temp_dir():
    env = os.environ.get("DMARKET_DATA_DIR")
    assert env, "conftest must set DMARKET_DATA_DIR before any src import"
    p = Path(env).resolve()
    assert p != PROJECT_DATA.resolve()
    assert PROJECT_DATA.resolve() not in p.parents
    assert str(p).startswith(str(Path(tempfile.gettempdir()).resolve()))


def test_module_level_paths_follow_env():
    from src.core.event_shield import EVENTS_FILE
    from src.core.shadow_engine import SHADOW_DB

    base = Path(os.environ["DMARKET_DATA_DIR"])
    assert EVENTS_FILE.parent == base
    assert SHADOW_DB.parent == base
