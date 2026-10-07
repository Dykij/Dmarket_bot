"""Каталог данных времени выполнения (SQLite-базы, файлы состояния)."""
import os
from pathlib import Path


def get_data_dir() -> Path:
    """Вернуть DMARKET_DATA_DIR, если задана, иначе <корень проекта>/data."""
    env_dir = os.environ.get("DMARKET_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    return Path(__file__).parent.parent.parent / "data"
