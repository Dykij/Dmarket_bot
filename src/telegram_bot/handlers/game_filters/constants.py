"""Константы для фильтров игровых предметов.

Содержит константы для различных игр:
- CS2/CSGO: категории, редкости, внешний вид
- Dota 2: герои, редкости, слоты
- Team Fortress 2: классы, качества, типы
- Rust: категории, типы, редкости
"""

from typing import Any

# CS2/CSGO константы
CS2_CATEGORIES = [
    "Pistol",
    "SMG",
    "Rifle",
    "Sniper Rifle",
    "Shotgun",
    "Machinegun",
    "Knife",
    "Gloves",
    "Sticker",
    "Agent",
    "Case",
]

CS2_RARITIES = [
    "Consumer Grade",
    "Industrial Grade",
    "Mil-Spec Grade",
    "Restricted",
    "Classified",
    "Covert",
    "Contraband",
]

CS2_EXTERIORS = [
    "Factory New",
    "Minimal Wear",
    "Field-Tested",
    "Well-Worn",
    "Battle-Scarred",
]

# Dota 2 константы
DOTA2_HEROES = [
    "Axe",
    "Anti-Mage",
    "Crystal Maiden",
    "Drow Ranger",
    "Juggernaut",
    "Pudge",
    "Lina",
    "Lion",
    "Sven",
    "Tiny",
    "Invoker",
    "Shadow Fiend",
]

DOTA2_RARITIES = [
    "Common",
    "Uncommon",
    "Rare",
    "Mythical",
    "Legendary",
    "Immortal",
    "Arcana",
]

DOTA2_SLOTS = [
    "Weapon",
    "Head",
    "Back",
    "Arms",
    "Shoulder",
    "Belt",
    "Misc",
    "Taunt",
    "Courier",
    "Ward",
]

# TF2 константы
TF2_CLASSES = [
    "Scout",
    "Soldier",
    "Pyro",
    "Demoman",
    "Heavy",
    "Engineer",
    "Medic",
    "Sniper",
    "Spy",
    "All Classes",
]

TF2_QUALITIES = [
    "Normal",
    "Unique",
    "Vintage",
    "Genuine",
    "Strange",
    "Unusual",
    "Haunted",
    "Collectors",
]

TF2_TYPES = [
    "Hat",
    "Weapon",
    "Cosmetic",
    "Action",
    "Tool",
    "Taunt",
    "Crate",
    "Key",
]

# Rust константы
RUST_CATEGORIES = [
    "Weapon",
    "Clothing",
    "Tool",
    "Construction",
    "Misc",
]

RUST_TYPES = [
    "Assault Rifle",
    "Pistol",
    "Shotgun",
    "SMG",
    "Jacket",
    "Pants",
    "Helmet",
    "Boots",
    "Gloves",
    "Door",
    "Box",
]

RUST_RARITIES = [
    "Common",
    "Uncommon",
    "Rare",
    "Epic",
    "Legendary",
]

# Значения по умолчанию для пользовательских фильтров
DEFAULT_FILTERS: dict[str, dict[str, Any]] = {
    "csgo": {
        "min_price": 1.0,
        "max_price": 1000.0,
        "float_min": 0.0,
        "float_max": 1.0,
        "category": None,
        "rarity": None,
        "exterior": None,
        "stattrak": False,
        "souvenir": False,
    },
    "dota2": {
        "min_price": 1.0,
        "max_price": 1000.0,
        "hero": None,
        "rarity": None,
        "slot": None,
        "quality": None,
        "tradable": True,
    },
    "tf2": {
        "min_price": 1.0,
        "max_price": 1000.0,
        "class": None,
        "quality": None,
        "type": None,
        "effect": None,
        "killstreak": None,
        "australium": False,
    },
    "rust": {
        "min_price": 1.0,
        "max_price": 1000.0,
        "category": None,
        "type": None,
        "rarity": None,
    },
}

# Названия игр для отображения
GAME_NAMES = {
    "csgo": "CS2 (CS:GO)",
    "dota2": "Dota 2",
    "tf2": "Team Fortress 2",
    "rust": "Rust",
}

__all__ = [
    "CS2_CATEGORIES",
    "CS2_EXTERIORS",
    "CS2_RARITIES",
    "DEFAULT_FILTERS",
    "DOTA2_HEROES",
    "DOTA2_RARITIES",
    "DOTA2_SLOTS",
    "GAME_NAMES",
    "RUST_CATEGORIES",
    "RUST_RARITIES",
    "RUST_TYPES",
    "TF2_CLASSES",
    "TF2_QUALITIES",
    "TF2_TYPES",
]
