"""Whitelist configuration for high-liquidity items.

This module contains curated lists of RECOMMENDED highly liquid items for each game.
These are suggestions, not strict requirements - items may or may not be avAlgolable
on DMarket at any given time.

ВАЖНО: Это РЕКОМЕНДАТЕЛЬНЫЙ список, а не обязательный!
- Предметы из списка получают приоритет при сканировании
- Но сканер НЕ ограничивается только этими предметами
- Список используется для определения ликвидности и снижения порога профита

Usage modes:
    1. PRIORITY_MODE (default): Whitelist items get profit boost, but all items scanned
    2. STRICT_MODE: Only whitelist items are considered (not recommended)

Updated: January 2026
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class WhitelistMode:
    """Режимы работы whitelist."""

    # Рекомендательный режим: whitelist предметы получают приоритет,
    # но все предметы сканируются (РЕКОМЕНДУЕТСЯ)
    PRIORITY = "priority"

    # Строгий режим: только whitelist предметы (НЕ рекомендуется)
    STRICT = "strict"

    # Отключен: whitelist не используется
    DISABLED = "disabled"


# Белый список РЕКОМЕНДУЕМЫХ высоколиквидных предметов по играм
# ВАЖНО: Это рекомендации, а не жёсткие требования!
# App ID маппинг: CS2=730, Rust=252490, Dota2=570, TF2=440
# Updated: January 2026
WHITELIST_ITEMS = {
    "730": [  # CS:GO/CS2 - Кейсы и популярные скины
        # ===== КЕЙСЫ 2025-2026 (ВЫСОКАЯ ЛИКВИДНОСТЬ) =====
        "Gallery Case",
        "Kilowatt Case",
        "Revolution Case",
        "Recoil Case",
        "Dreams & Nightmares Case",
        "Fracture Case",
        "Snakebite Case",
        "Operation Riptide Case",
        "Armory Case",  # Новый 2026
        "Elemental Case",  # Новый 2026
        # ===== КЛАССИЧЕСКИЕ КЕЙСЫ (СТАБИЛЬНАЯ ЛИКВИДНОСТЬ) =====
        "Clutch Case",
        "Spectrum 2 Case",
        "Chroma 3 Case",
        "Prisma 2 Case",
        "Prisma Case",
        "Danger Zone Case",
        "Horizon Case",
        "Operation Bravo Case",
        "CS:GO Weapon Case",
        "CS:GO Weapon Case 2",
        "CS:GO Weapon Case 3",
        "Glove Case",
        "Shadow Case",
        "Falchion Case",
        "Chroma Case",
        "Chroma 2 Case",
        "Phoenix Case",
        "Huntsman Weapon Case",
        "Breakout Case",
        "Revolver Case",
        # ===== ЛИКВИДНЫЕ СКИНЫ (БЫСТРАЯ ПРОДАЖА) =====
        # AK-47
        "AK-47 | Slate",
        "AK-47 | Redline",
        "AK-47 | Asiimov",
        "AK-47 | Vulcan",
        "AK-47 | Fuel Injector",
        "AK-47 | Bloodsport",
        "AK-47 | Neon Rider",
        "AK-47 | Phantom Disruptor",
        "AK-47 | Ice Coaled",
        "AK-47 | Nightwish",
        "AK-47 | Inheritance",  # Новый 2026
        # AWP
        "AWP | Asiimov",
        "AWP | Lightning Strike",
        "AWP | Hyper Beast",
        "AWP | Dragon Lore",
        "AWP | Fade",
        "AWP | Wildfire",
        "AWP | Neo-Noir",
        "AWP | Chromatic Aberration",
        "AWP | Phobos",
        "AWP | Electric Hive",
        "AWP | PAW",
        # M4A4 / M4A1-S
        "M4A4 | Desolate Space",
        "M4A4 | Asiimov",
        "M4A4 | Neo-Noir",
        "M4A4 | The Emperor",
        "M4A4 | Howl",
        "M4A4 | Royal Paladin",
        "M4A1-S | Hyper Beast",
        "M4A1-S | Printstream",
        "M4A1-S | Chantico's Fire",
        "M4A1-S | Golden Coil",
        "M4A1-S | Blue Phosphor",
        "M4A1-S | Nightmare",  # Новый 2026
        # Desert Eagle
        "Desert Eagle | Blaze",
        "Desert Eagle | Code Red",
        "Desert Eagle | Mecha Industries",
        "Desert Eagle | Printstream",
        "Desert Eagle | Light RAlgol",
        "Desert Eagle | Fennec Fox",
        "Desert Eagle | Kumicho Dragon",
        # Пистолеты
        "Glock-18 | Fade",
        "Glock-18 | Candy Apple",
        "Glock-18 | Gamma Doppler",
        "Glock-18 | Wasteland Rebel",
        "Glock-18 | Neo-Noir",
        "USP-S | Cyrex",
        "USP-S | Kill Confirmed",
        "USP-S | Neo-Noir",
        "USP-S | Printstream",
        "USP-S | The TrAlgotor",
        # Ножи (общие категории - высокая ликвидность)
        "★ Karambit",
        "★ Butterfly Knife",
        "★ M9 Bayonet",
        "★ Bayonet",
        "★ Flip Knife",
        "★ Gut Knife",
        "★ Falchion Knife",
        "★ Shadow Daggers",
        "★ Bowie Knife",
        "★ Huntsman Knife",
        "★ Navaja Knife",
        "★ Stiletto Knife",
        "★ Talon Knife",
        "★ Ursus Knife",
        "★ Classic Knife",
        "★ Paracord Knife",
        "★ Survival Knife",
        "★ Nomad Knife",
        "★ Skeleton Knife",
        "★ Kukri Knife",  # Новый 2026
        # Перчатки (общие категории - высокая ликвидность)
        "★ Specialist Gloves",
        "★ Sport Gloves",
        "★ Driver Gloves",
        "★ Hand Wraps",
        "★ Moto Gloves",
        "★ Hydra Gloves",
        "★ Bloodhound Gloves",
        "★ Broken Fang Gloves",
    ],
    "252490": [  # Rust - Популярные предметы
        # ===== ДВЕРИ И СТРОИТЕЛЬСТВО (СТАБИЛЬНЫЙ СПРОС) =====
        "Wood Storage Box",
        "Large Wood Box",
        "Sheet Metal Door",
        "Armored Door",
        "Garage Door",
        "Double Door",
        "Metal Door",
        "High External Stone Wall",
        "High External Wood Wall",
        # ===== ИНСТРУМЕНТЫ И РЕСУРСЫ =====
        "Furnace",
        "Large Furnace",
        "Sleeping Bag",
        "Research Table",
        "RepAlgor Bench",
        "Work Bench Level 1",
        "Work Bench Level 2",
        "Work Bench Level 3",
        "Small Oil Refinery",
        "Tool Cupboard",
        # ===== БРОНЯ (ПОПУЛЯРНАЯ) =====
        "Metal Chest Plate",
        "Metal Facemask",
        "Road Sign Kilt",
        "Road Sign Jacket",
        "Coffee Can Helmet",
        "Roadsign Gloves",
        "Hoodie",
        "Pants",
        # ===== ОРУЖИЕ (ВЫСОКАЯ ЛИКВИДНОСТЬ) =====
        "AK47",
        "Tempered AK47",
        "Glory AK47",
        "LR-300 Assault Rifle",
        "M249",
        "MP5A4",
        "Custom SMG",
        "Thompson",
        "Bolt Action Rifle",
        "L96 Rifle",
        "Semi-Automatic Rifle",
        "Assault Rifle",
        "M39 Rifle",
        "Rocket Launcher",
        # ===== ДЕКОРАТИВНЫЕ (ТУРНИРНЫЕ И РЕДКИЕ) =====
        "Twitch Rivals",
        "Dragon",
        "Alien Red",
        "Tempered",
        "Glory",
        "Playrust.com",
    ],
    "570": [  # Dota 2 - Immortals и Arcanas
        # ===== ARCANA (ВЫСШАЯ ЛИКВИДНОСТЬ) =====
        "Manifold Paradox",  # Phantom Assassin Arcana
        "Demon Eater",  # Shadow Fiend Arcana
        "Fractal Horns of Inner Abysm",  # Terrorblade Arcana
        "Bladeform Legacy",  # Juggernaut Arcana
        "Feast of Abscession",  # Pudge Arcana
        "Fiery Soul of the Slayer",  # Lina Arcana
        "Swine of the Sunken Galley",  # Techies Arcana
        "Great Sage's Reckoning",  # Monkey King Arcana
        "Benevolent Companion",  # Io Arcana
        "Planetfall",  # Earthshaker Arcana
        "Compass of the Rising Gale",  # Windranger Arcana
        "Eminence of Ristul",  # Queen of PAlgon Arcana
        "Disciple's Path",  # Anti-Mage Persona Arcana
        "Dread Retribution",  # Spectre Arcana
        "Condemned Souls",  # Phantom Assassin Arcana 2024
        "Mercurial Vanguard",  # Razor Arcana 2025
        "Eternal Harvest",  # Faceless Void Arcana 2026
        # ===== IMMORTAL (ВЫСОКАЯ ЛИКВИДНОСТЬ) =====
        "Immortal Treasure",
        "Immortal Treasure I",
        "Immortal Treasure II",
        "Immortal Treasure III",
        "Inscribed Murder of Crows",
        "Genuine Monarch Bow",
        "Dragonclaw Hook",
        "Golden Immortal",
        "Ultra Rare Immortal",
        # ===== TI ПРЕДМЕТЫ (СЕЗОННАЯ ВЫСОКАЯ ЛИКВИДНОСТЬ) =====
        "Collector's Cache",
        "Collector's Cache II",
        "Battle Pass",
        "The International",
        "Aghanim's Labyrinth",
        "Nemestice",
        "Cavern Crawl",
        "Diretide",
        # ===== SETS (ПОПУЛЯРНЫЕ) =====
        "Genuine",
        "Exalted",
        "Inscribed",
        "Unusual",
        "Corrupted",
        "Infused",
    ],
    "440": [  # TF2 - Ключи и металл (стабильная валюта)
        # ===== КЛЮЧИ (ЛУЧШАЯ ВАЛЮТА TF2) =====
        "Mann Co. Supply Crate Key",
        "Mann Co. Supply Munition Key",
        "Secret Saxton Key",
        "Tour of Duty Ticket",
        "Uncrating Key",
        "Cosmetic Key",
        # ===== МЕТАЛЛ (БАЗОВАЯ ВАЛЮТА) =====
        "Refined Metal",
        "ReclAlgomed Metal",
        "Scrap Metal",
        "Earbuds",
        # ===== TAUNTS (ВЫСОКАЯ ЛИКВИДНОСТЬ) =====
        "Taunt: The Schadenfreude",
        "Taunt: The Conga",
        "Taunt: High Five!",
        "Taunt: The Kazotsky Kick",
        "Taunt: Mannrobics",
        "Taunt: Rock, Paper, Scissors",
        "Taunt: Square Dance",
        "Taunt: The Boston Breakdance",
        "Taunt: Yeti Punch",
        "Taunt: Victory Lap",
        # ===== СТРАННЫЕ ЧАСТИ (СТАБИЛЬНЫЙ СПРОС) =====
        "Strange Part: Kills",
        "Strange Part: Headshot Kills",
        "Strange Part: Critical Kills",
        "Strange Part: Domination Kills",
        "Strange Part: Revenge Kills",
        "Strange Part: Kills While Explosive-Jumping",
        "Strange Part: Algorborne Enemy Kills",
        "Strange Part",
        # ===== UNUSUAL ЭФФЕКТЫ (ВЫСОКАЯ СТОИМОСТЬ) =====
        "Unusual",
        "Unusual Haunted Metal Scrap",
        # ===== ПОПУЛЯРНЫЕ ПРЕДМЕТЫ =====
        "Bill's Hat",
        "Max's Severed Head",
        "Team CaptAlgon",
        "Tyrant's Helm",
        "The Essential Accessories",
        "Stout Shako",
    ],
}

# Маппинг коротких имен игр в App ID
GAME_APP_ID_MAP = {
    "csgo": "730",
    "cs2": "730",
    "rust": "252490",
    "dota2": "570",
    "tf2": "440",
}

# НастSwarmки whitelist (могут быть переопределены из JSON)
# ВАЖНО: По умолчанию работает в режиме PRIORITY (рекомендательный)
WHITELIST_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "mode": WhitelistMode.PRIORITY,  # PRIORITY = рекомендательный, STRICT = только whitelist
    "priority_only": False,  # Deprecated: use mode instead
    "max_same_items_in_inventory": 5,
    "buy_max_overpay_percent": 2.0,
    "max_stack_value_percent": 15,
    "min_liquidity_score": 70,
    # НастSwarmки приоритета для whitelist предметов
    "profit_boost_percent": 2.0,  # Снижение порога профита для whitelist
    "liquidity_boost": True,  # Считать whitelist предметы ликвидными
}

# Веса игр для диверсификации (в процентах внимания)
GAME_WEIGHTS: dict[str, int] = {
    "tf2": 30,  # Ключи стабильны, быстро продаются
    "csgo": 40,  # Кейсы и скины, высокая волатильность
    "rust": 20,  # Двери и ящики, стабильный спрос
    "dota2": 10,  # Только Inscribed/Immortal предметы
}


def load_whitelist_from_json(file_path: str = "data/whitelist.json") -> bool:
    """Загружает whitelist из JSON файла.

    Args:
        file_path: Путь к JSON файлу с whitelist

    Returns:
        True если загрузка успешна, False иначе
    """
    global WHITELIST_ITEMS, WHITELIST_SETTINGS, GAME_WEIGHTS

    path = Path(file_path)
    if not path.exists():
        logger.warning(f"Whitelist file not found: {file_path}")
        return False

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        # Загружаем настSwarmки
        if "settings" in data:
            WHITELIST_SETTINGS.update(data["settings"])
            logger.info(f"Loaded whitelist settings: {WHITELIST_SETTINGS}")

        # Загружаем enabled/priority_only
        if "enabled" in data:
            WHITELIST_SETTINGS["enabled"] = data["enabled"]
        if "priority_only" in data:
            WHITELIST_SETTINGS["priority_only"] = data["priority_only"]

        # Загружаем веса игр для диверсификации
        if "game_weights" in data:
            GAME_WEIGHTS.update(data["game_weights"])
            logger.info(f"Loaded game weights: {GAME_WEIGHTS}")

        # Загружаем предметы по играм
        if "items" in data:
            items_data = data["items"]
            total_items = 0

            # Маппинг имен игр из JSON в App ID
            game_to_appid = {
                "csgo": "730",
                "cs2": "730",
                "dota2": "570",
                "rust": "252490",
                "tf2": "440",
            }

            for game_name, items in items_data.items():
                app_id = game_to_appid.get(game_name.lower())
                if app_id and items:
                    # Добавляем к существующему списку, избегая дубликатов
                    existing = set(WHITELIST_ITEMS.get(app_id, []))
                    new_items = [item for item in items if item not in existing]
                    WHITELIST_ITEMS[app_id] = list(existing) + new_items
                    total_items += len(new_items)
                    logger.debug(f"Loaded {len(new_items)} items for {game_name}")

            logger.info(f"✅ Loaded {total_items} whitelist items from {file_path}")

        return True

    except json.JSONDecodeError as e:
        logger.exception(f"Failed to parse whitelist JSON: {e}")
        return False
    except Exception as e:
        logger.exception(f"Error loading whitelist: {e}")
        return False


def get_game_weight(game: str) -> int:
    """Получает вес игры для стратегии диверсификации.

    Args:
        game: Код игры (csgo, rust, dota2, tf2)

    Returns:
        Вес игры в процентах (0-100)
    """
    return GAME_WEIGHTS.get(game.lower(), 10)


class WhitelistChecker:
    """Класс для проверки предметов по белому списку."""

    def __init__(
        self, enable_priority_boost: bool = True, profit_boost_percent: float = 2.0
    ):
        """Инициализирует проверку белого списка.

        Args:
            enable_priority_boost: Включить приоритетную обработку whitelist предметов
            profit_boost_percent: На сколько процентов снизить порог профита для whitelist
        """
        self.enable_priority_boost = enable_priority_boost
        self.profit_boost_percent = profit_boost_percent

    def is_whitelisted(self, item: dict[str, Any], game: str) -> bool:
        """Проверяет, находится ли предмет в белом списке.

        Args:
            item: Словарь с данными предмета
            game: Код игры (csgo, rust, dota2, tf2)

        Returns:
            True если предмет в белом списке, False иначе
        """
        # Получаем App ID игры
        app_id = GAME_APP_ID_MAP.get(game.lower())
        if not app_id:
            return False

        # Получаем whitelist для этой игры
        whitelist = WHITELIST_ITEMS.get(app_id, [])
        if not whitelist:
            return False

        # Проверяем title предмета
        title = item.get("title", "")
        return any(target in title for target in whitelist)

    def get_adjusted_profit_margin(
        self, base_margin: float, is_whitelist: bool
    ) -> float:
        """Получает скорректированный порог профита.

        Args:
            base_margin: Базовый порог профита
            is_whitelist: Предмет из белого списка

        Returns:
            Скорректированный порог профита
        """
        if is_whitelist and self.enable_priority_boost:
            # Снижаем порог профита для whitelist предметов
            adjusted = base_margin - self.profit_boost_percent
            logger.debug(
                f"🎯 Whitelist priority: profit margin adjusted "
                f"{base_margin:.1f}% -> {adjusted:.1f}%"
            )
            return max(adjusted, 3.0)  # Минимум 3% чистого профита

        return base_margin


def get_whitelist_for_game(game: str) -> list[str]:
    """Получает белый список для конкретной игры.

    Args:
        game: Код игры (csgo, rust, dota2, tf2)

    Returns:
        Список названий предметов в белом списке
    """
    app_id = GAME_APP_ID_MAP.get(game.lower())
    if not app_id:
        return []

    return WHITELIST_ITEMS.get(app_id, [])


def add_to_whitelist(game: str, item_name: str) -> bool:
    """Добавляет предмет в белый список.

    Args:
        game: Код игры (csgo, rust, dota2, tf2)
        item_name: Название предмета

    Returns:
        True если добавлено успешно, False иначе
    """
    app_id = GAME_APP_ID_MAP.get(game.lower())
    if not app_id:
        logger.warning(f"Unknown game: {game}")
        return False

    if app_id not in WHITELIST_ITEMS:
        WHITELIST_ITEMS[app_id] = []

    if item_name not in WHITELIST_ITEMS[app_id]:
        WHITELIST_ITEMS[app_id].append(item_name)
        logger.info(f"✅ Added to whitelist ({game}): {item_name}")
        return True

    logger.warning(f"Item already in whitelist: {item_name}")
    return False


def remove_from_whitelist(game: str, item_name: str) -> bool:
    """Удаляет предмет из белого списка.

    Args:
        game: Код игры (csgo, rust, dota2, tf2)
        item_name: Название предмета

    Returns:
        True если удалено успешно, False иначе
    """
    app_id = GAME_APP_ID_MAP.get(game.lower())
    if not app_id or app_id not in WHITELIST_ITEMS:
        return False

    if item_name in WHITELIST_ITEMS[app_id]:
        WHITELIST_ITEMS[app_id].remove(item_name)
        logger.info(f"🗑️ Removed from whitelist ({game}): {item_name}")
        return True

    return False
