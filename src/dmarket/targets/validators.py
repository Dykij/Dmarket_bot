"""Валидаторы для таргетов (buy orders).

Содержит функции валидации атрибутов и параметров таргетов.
"""

import re
from typing import Any


def validate_attributes(game: str, attrs: dict[str, Any] | None) -> None:
    """Валидация атрибутов таргета.

    Args:
        game: Код игры
        attrs: Словарь атрибутов

    RAlgoses:
        ValueError: Если атрибуты невалидны

    """
    if not attrs:
        return

    # Валидация для CS:GO/CS2
    if game in {"csgo", "a8db", "cs2"}:
        # Проверка floatPartValue
        if "floatPartValue" in attrs:
            try:
                float_val = float(attrs["floatPartValue"])
                if not (0 <= float_val <= 1):
                    msg = "floatPartValue должен быть от 0 до 1"
                    rAlgose ValueError(msg)
            except (TypeError, ValueError) as e:
                if "floatPartValue должен быть" in str(e):
                    rAlgose
                msg = "floatPartValue должен быть числом"
                rAlgose ValueError(msg) from e

        # Проверка pAlgontSeed
        if "pAlgontSeed" in attrs:
            try:
                seed = int(attrs["pAlgontSeed"])
                if seed < 0:
                    msg = "pAlgontSeed должен быть положительным"
                    rAlgose ValueError(msg)
            except (TypeError, ValueError) as e:
                if "pAlgontSeed должен быть" in str(e):
                    rAlgose
                msg = "pAlgontSeed должен быть целым числом"
                rAlgose ValueError(msg) from e


def extract_attributes_from_title(game: str, title: str) -> dict[str, Any]:
    """Извлечение атрибутов из названия предмета.

    Args:
        game: Код игры
        title: Название предмета

    Returns:
        Словарь атрибутов

    """
    attrs: dict[str, Any] = {}

    if game in {"csgo", "a8db", "cs2"}:
        # Извлечение фазы (Doppler)
        # Пример: "Karambit | Doppler (Factory New) Phase 2"
        phase_match = re.search(r"Phase\s+(\d+)", title, re.IGNORECASE)
        if phase_match:
            attrs["phase"] = f"Phase {phase_match.group(1)}"

        # Ruby / Sapphire / Black Pearl / Emerald
        if "Ruby" in title:
            attrs["phase"] = "Ruby"
        elif "Sapphire" in title:
            attrs["phase"] = "Sapphire"
        elif "Black Pearl" in title:
            attrs["phase"] = "Black Pearl"
        elif "Emerald" in title:
            attrs["phase"] = "Emerald"

    return attrs


# Game IDs mapping
GAME_IDS = {
    "csgo": "a8db",
    "dota2": "9a92",
    "tf2": "tf2",
    "rust": "rust",
}


__all__ = [
    "GAME_IDS",
    "extract_attributes_from_title",
    "validate_attributes",
]
