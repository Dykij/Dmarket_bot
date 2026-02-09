"""
JSON utilities с использованием orjson для ускорения сериализации.

Модуль предоставляет обертки для orjson с fallback на стандартный json.
orjson в 2-3 раза быстрее стандартного json и поддерживает datetime, UUID, и другие типы.
"""

import json as stdlib_json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Попытка импорта orjson
try:
    import orjson

    ORJSON_AVAILABLE = True
    logger.info("Using orjson for JSON serialization (faster)")
except ImportError:
    orjson = None  # type: ignore[assignment,unused-ignore]

    ORJSON_AVAILABLE = False
    logger.warning(
        "orjson not available, using standard json (slower). "
        "Install orjson for better performance: pip install orjson"
    )


def dumps(obj: Any, **kwargs: Any) -> str:
    """
    Сериализовать объект в JSON строку.

    Использует orjson если доступен, иначе стандартный json.

    Args:
        obj: Объект для сериализации
        **kwargs: Дополнительные параметры (для совместимости)

    Returns:
        JSON строка

    Example:
        >>> data = {"name": "AK-47", "price": 12.50, "created": datetime.now()}
        >>> json_str = dumps(data)
    """
    if ORJSON_AVAILABLE:
        # orjson возвращает bytes, конвертируем в str
        # orjson автоматически поддерживает datetime, UUID, dataclasses
        return orjson.dumps(obj).decode("utf-8")
    # Fallback на стандартный json
    # Удаляем ensure_ascii из kwargs если есть
    kwargs.pop("ensure_ascii", None)
    return stdlib_json.dumps(obj, ensure_ascii=False, **kwargs)


def loads(s: str | bytes, **kwargs: Any) -> Any:
    """
    Десериализовать JSON строку в объект.

    Использует orjson если доступен, иначе стандартный json.

    Args:
        s: JSON строка или bytes
        **kwargs: Дополнительные параметры (для совместимости)

    Returns:
        Десериализованный объект

    Example:
        >>> json_str = '{"name": "AK-47", "price": 12.50}'
        >>> data = loads(json_str)
        >>> print(data["name"])
        AK-47
    """
    if ORJSON_AVAILABLE:
        # orjson.loads принимает str или bytes
        return orjson.loads(s)
    # Fallback на стандартный json
    if isinstance(s, bytes):
        s = s.decode("utf-8")
    return stdlib_json.loads(s, **kwargs)


def dump(obj: Any, fp: Any, **kwargs: Any) -> None:
    """
    Сериализовать объект в JSON файл.

    Args:
        obj: Объект для сериализации
        fp: File-like объект
        **kwargs: Дополнительные параметры
    """
    if ORJSON_AVAILABLE:
        # orjson не имеет dump(), используем dumps + write
        fp.write(orjson.dumps(obj))
    else:
        kwargs.pop("ensure_ascii", None)
        stdlib_json.dump(obj, fp, ensure_ascii=False, **kwargs)


def load(fp: Any, **kwargs: Any) -> Any:
    """
    Десериализовать JSON из файла.

    Args:
        fp: File-like объект
        **kwargs: Дополнительные параметры

    Returns:
        Десериализованный объект
    """
    if ORJSON_AVAILABLE:
        # orjson не имеет load(), используем read + loads
        return orjson.loads(fp.read())
    return stdlib_json.load(fp, **kwargs)


# Алиасы для совместимости
JSONDecodeError = orjson.JSONDecodeError if ORJSON_AVAILABLE else stdlib_json.JSONDecodeError
