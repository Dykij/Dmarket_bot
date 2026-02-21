"""Game-Specific Filters and Strategies - расширенные фильтры для каждой игры.

Этот модуль содержит детальные фильтры и стратегии для каждой игры на DMarket:

1. **CS:GO / CS2** - самый большой и ликвидный рынок
   - Float Value фильтры (FN, MW, FT, WW, BS)
   - Pattern фильтры (Blue Gem, Fade, Marble Fade)
   - Sticker премия (Katowice 2014, Titan Holo)
   - Doppler фазы (Ruby, Sapphire, Black Pearl, Emerald)
   - StatTrak предметы
   - Сувенирные предметы

2. **Dota 2** - уникальный рынок с gems и стилями
   - Arcana предметы
   - Immortal предметы
   - Unusual Couriers с эффектами
   - Ethereal Gems (цвет)
   - Prismatic Gems
   - Inscribed Gems
   - Unlocked стили
   - Golden версии

3. **Team Fortress 2** - коллекционный рынок с unusual эффектами
   - Unusual эффекты (Burning Flames, Sunbeams, etc.)
   - Strange предметы со счётчиками
   - Killstreak варианты (Basic, Specialized, Professional)
   - Australium оружие
   - Collectors Quality
   - Festive версии
   - Vintage предметы

4. **Rust** - растущий рынок с уникальными скинами
   - Luminescent скины
   - Tempered скины
   - Garage Doors (высокая цена)
   - Ограниченные/Limited скины
   - Гоночные скины
   - Drops from Twitch

Author: DMarket Telegram Bot
Created: January 2026
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ============================================================================
# CS:GO / CS2 Filters
# ============================================================================


class CSGOWear(StrEnum):
    """Уровни износа для CS:GO."""

    FACTORY_NEW = "fn"  # 0.00-0.07
    MINIMAL_WEAR = "mw"  # 0.07-0.15
    FIELD_TESTED = "ft"  # 0.15-0.38
    WELL_WORN = "ww"  # 0.38-0.45
    BATTLE_SCARRED = "bs"  # 0.45-1.00


class CSGODopplerPhase(StrEnum):
    """Фазы Doppler ножей."""

    PHASE_1 = "phase1"
    PHASE_2 = "phase2"
    PHASE_3 = "phase3"
    PHASE_4 = "phase4"
    RUBY = "ruby"
    SAPPHIRE = "sapphire"
    BLACK_PEARL = "black_pearl"
    EMERALD = "emerald"  # Gamma Doppler


# Float ranges для CS:GO по качеству
CSGO_FLOAT_RANGES = {
    CSGOWear.FACTORY_NEW: (0.00, 0.07),
    CSGOWear.MINIMAL_WEAR: (0.07, 0.15),
    CSGOWear.FIELD_TESTED: (0.15, 0.38),
    CSGOWear.WELL_WORN: (0.38, 0.45),
    CSGOWear.BATTLE_SCARRED: (0.45, 1.00),
}

# Премии за Doppler фазы (множитель к базовой цене)
CSGO_DOPPLER_PREMIUMS = {
    CSGODopplerPhase.PHASE_1: 1.0,
    CSGODopplerPhase.PHASE_2: 1.05,
    CSGODopplerPhase.PHASE_3: 0.95,
    CSGODopplerPhase.PHASE_4: 1.1,
    CSGODopplerPhase.RUBY: 6.0,
    CSGODopplerPhase.SAPPHIRE: 5.5,
    CSGODopplerPhase.BLACK_PEARL: 4.0,
    CSGODopplerPhase.EMERALD: 3.0,
}

# Популярные Blue Gem Pattern ID (Case Hardened)
CSGO_BLUE_GEM_PATTERNS = {
    # AK-47 Case Hardened patterns
    "ak47_best": [661, 670, 321, 387, 955, 868, 179],
    # Karambit Case Hardened patterns
    "karambit_best": [387, 442, 463, 470, 601, 853],
    # Five-Seven Case Hardened patterns
    "five_seven_best": [278, 690, 363, 868],
    # Falchion Case Hardened patterns
    "falchion_best": [321, 494, 512, 597],
}

# Katowice 2014 стикеры с премиями
CSGO_KATOWICE_2014_STICKERS = {
    "iBUYPOWER (Holo)": 50.0,  # x50 премия
    "Titan (Holo)": 30.0,  # x30 премия
    "Reason Gaming (Holo)": 20.0,
    "dignitas (Holo)": 15.0,
    "Natus Vincere (Holo)": 10.0,
    "Team LDLC.com (Holo)": 10.0,
    "Fnatic (Holo)": 8.0,
    "Ninjas in Pyjamas (Holo)": 7.0,
    "compLexity Gaming (Holo)": 6.0,
    "HellRAlgosers (Holo)": 6.0,
    "LGB eSports (Holo)": 6.0,
    "mousesports (Holo)": 5.0,
    "Virtus.Pro (Holo)": 5.0,
}

# Fade проценты
CSGO_FADE_PERCENTAGES = {
    "100%": 1.5,  # Максимальный фейд
    "99%": 1.4,
    "98%": 1.3,
    "97%": 1.2,
    "96%": 1.15,
    "95%": 1.1,
    "90%": 1.05,
    "85%": 1.0,
}


@dataclass
class CSGOFilter:
    """Фильтр для CS:GO предметов."""

    # Основные фильтры
    wear: CSGOWear | None = None
    is_stattrak: bool | None = None
    is_souvenir: bool | None = None

    # Float фильтры
    float_min: float | None = None
    float_max: float | None = None

    # Doppler фильтры
    doppler_phase: CSGODopplerPhase | None = None

    # Pattern фильтры
    pattern_ids: list[int] | None = None

    # Fade фильтр
    min_fade_percent: float | None = None

    # Sticker фильтры
    has_katowice_2014: bool = False
    sticker_names: list[str] | None = None
    min_sticker_premium: float | None = None

    # Типы оружия
    weapon_types: list[str] | None = None
    knife_types: list[str] | None = None
    glove_types: list[str] | None = None

    def matches(self, item: dict[str, Any]) -> bool:
        """Проверить соответствие предмета фильтру."""
        # Проверка износа
        if self.wear and item.get("wear") != self.wear.value:
            return False

        # Проверка float
        item_float = item.get("float_value", 0.5)
        if self.float_min is not None and item_float < self.float_min:
            return False
        if self.float_max is not None and item_float > self.float_max:
            return False

        # Проверка StatTrak
        if self.is_stattrak is not None:
            item_stattrak = "StatTrak" in item.get("title", "")
            if item_stattrak != self.is_stattrak:
                return False

        # Проверка Souvenir
        if self.is_souvenir is not None:
            item_souvenir = "Souvenir" in item.get("title", "")
            if item_souvenir != self.is_souvenir:
                return False

        # Проверка Doppler фазы
        if self.doppler_phase:
            item_phase = item.get("phase", "").lower()
            if self.doppler_phase.value not in item_phase:
                return False

        # Проверка Pattern ID
        if self.pattern_ids:
            item_pattern = item.get("pattern_id")
            if item_pattern not in self.pattern_ids:
                return False

        return True

    def calculate_premium(self, item: dict[str, Any]) -> float:
        """Рассчитать премию для предмета."""
        premium = 1.0

        # Премия за Doppler фазу
        if self.doppler_phase and self.doppler_phase in CSGO_DOPPLER_PREMIUMS:
            premium *= CSGO_DOPPLER_PREMIUMS[self.doppler_phase]

        # Премия за стикеры
        stickers = item.get("stickers", [])
        for sticker in stickers:
            sticker_name = sticker.get("name", "")
            if sticker_name in CSGO_KATOWICE_2014_STICKERS:
                premium += (
                    CSGO_KATOWICE_2014_STICKERS[sticker_name] * 0.1
                )  # 10% от премии стикера

        # Премия за низкий float (FN)
        item_float = item.get("float_value", 0.5)
        if item_float < 0.01:
            premium *= 1.5  # +50% за очень низкий float
        elif item_float < 0.03:
            premium *= 1.2  # +20%

        return premium


# ============================================================================
# Dota 2 Filters
# ============================================================================


class Dota2Quality(StrEnum):
    """Качество предметов Dota 2."""

    STANDARD = "standard"
    GENUINE = "genuine"
    INSCRIBED = "inscribed"
    CORRUPTED = "corrupted"
    FROZEN = "frozen"
    CURSED = "cursed"
    AUTOGRAPHED = "autographed"
    HEROIC = "heroic"
    UNUSUAL = "unusual"
    GOLDEN = "golden"
    IMMORTAL = "immortal"
    ARCANA = "arcana"
    ASCENDANT = "ascendant"
    EXALTED = "exalted"


class Dota2Rarity(StrEnum):
    """Редкость предметов Dota 2."""

    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    MYTHICAL = "mythical"
    LEGENDARY = "legendary"
    IMMORTAL = "immortal"
    ARCANA = "arcana"
    ANCIENT = "ancient"


# Ethereal Gems (цвета курьеров)
DOTA2_ETHEREAL_GEMS = {
    "Ethereal Flame": 3.0,  # x3 множитель
    "Piercing Beams": 2.5,
    "Burning Animus": 2.0,
    "Resonant Energy": 2.0,
    "Felicity's Blessing": 1.8,
    "Luminous Gaze": 1.5,
    "Searing Essence": 1.5,
    "Diretide Corruption": 2.5,
    "Champion's Aura": 3.5,
    "Divine Essence": 4.0,
}

# Prismatic Gems (цвета)
DOTA2_PRISMATIC_GEMS = {
    "Legacy": 10.0,  # Уникальные legacy цвета
    "Creator's Light": 5.0,
    "Rubiline": 3.0,
    "Verdant Green": 2.0,
    "Dungeon Doom": 2.5,
    "Champion's Blue": 2.0,
    "Blossom Red": 1.8,
    "Miasmatic Grey": 1.5,
    "Unhallowed Ground": 1.5,
}

# Популярные Arcana и Immortals с премиями
DOTA2_VALUABLE_ITEMS = {
    # Arcana
    "Manifold Paradox": 30.0,  # Phantom Assassin Arcana
    "Demon Eater": 35.0,  # Shadow Fiend Arcana
    "Bladeform Legacy": 45.0,  # Juggernaut Arcana
    "Fractal Horns of Inner Abysm": 80.0,  # Terrorblade Arcana
    "Fiery Soul of the Slayer": 40.0,  # Lina Arcana
    "Swine of the Sunken Galley": 50.0,  # Techies Arcana
    "Great Sage's Reckoning": 30.0,  # Monkey King Arcana
    "Benevolent Companion": 200.0,  # Io Arcana (limited)
    # Valuable Immortals
    "Golden Basher Blades": 20.0,
    "Golden Gravelmaw": 15.0,
    "Golden Moonfall": 25.0,
}

# Стили для предметов с unlock
DOTA2_UNLOCK_STYLES = {
    "Second Style": 1.5,  # +50%
    "Third Style": 2.0,  # +100%
    "Alternate Style": 1.3,
    "Kinetic Gem": 1.2,
}


@dataclass
class Dota2Filter:
    """Фильтр для Dota 2 предметов."""

    # Качество и редкость
    qualities: list[Dota2Quality] | None = None
    rarities: list[Dota2Rarity] | None = None

    # Hero фильтр
    heroes: list[str] | None = None

    # Gem фильтры
    has_ethereal_gem: bool = False
    has_prismatic_gem: bool = False
    ethereal_gems: list[str] | None = None
    prismatic_gems: list[str] | None = None

    # Inscribed gems (счётчики)
    has_inscribed_gem: bool = False

    # Style unlock
    has_unlocked_style: bool = False
    style_unlocked: int | None = None  # Номер стиля

    # Тип предмета
    item_types: list[str] | None = None  # courier, ward, announcer, etc.

    # Tradeable/Marketable
    is_tradeable: bool = True
    is_marketable: bool = True

    def matches(self, item: dict[str, Any]) -> bool:
        """Проверить соответствие предмета фильтру."""
        # Проверка качества
        if self.qualities:
            item_quality = item.get("quality", "").lower()
            if not any(q.value in item_quality for q in self.qualities):
                return False

        # Проверка редкости
        if self.rarities:
            item_rarity = item.get("rarity", "").lower()
            if not any(r.value in item_rarity for r in self.rarities):
                return False

        # Проверка героя
        if self.heroes:
            item_hero = item.get("hero", "")
            if item_hero not in self.heroes:
                return False

        # Проверка gems
        item_gems = item.get("gems", [])
        if self.has_ethereal_gem:
            if not any("Ethereal" in g.get("type", "") for g in item_gems):
                return False

        if self.has_prismatic_gem:
            if not any("Prismatic" in g.get("type", "") for g in item_gems):
                return False

        # Проверка unlocked стиля
        if self.has_unlocked_style:
            styles = item.get("styles_unlocked", 0)
            if styles < 1:
                return False

        return True

    def calculate_premium(self, item: dict[str, Any]) -> float:
        """Рассчитать премию для предмета."""
        premium = 1.0

        # Проверка gems
        item_gems = item.get("gems", [])
        for gem in item_gems:
            gem_name = gem.get("name", "")

            # Ethereal gem премия
            for eth_name, mult in DOTA2_ETHEREAL_GEMS.items():
                if eth_name in gem_name:
                    premium *= mult
                    break

            # Prismatic gem премия
            for prism_name, mult in DOTA2_PRISMATIC_GEMS.items():
                if prism_name in gem_name:
                    premium *= mult
                    break

        # Премия за unlocked стили
        styles = item.get("styles_unlocked", 0)
        if styles >= 3:
            premium *= 2.0
        elif styles >= 2:
            premium *= 1.5
        elif styles >= 1:
            premium *= 1.2

        # Премия за specific items
        item_title = item.get("title", "")
        for item_name, item_premium in DOTA2_VALUABLE_ITEMS.items():
            if item_name.lower() in item_title.lower():
                premium *= item_premium / 10.0  # Нормализуем
                break

        return premium


# ============================================================================
# TF2 Filters
# ============================================================================


class TF2Quality(StrEnum):
    """Качество предметов TF2."""

    NORMAL = "normal"
    UNIQUE = "unique"
    STRANGE = "strange"
    VINTAGE = "vintage"
    GENUINE = "genuine"
    UNUSUAL = "unusual"
    HAUNTED = "haunted"
    COLLECTORS = "collectors"
    DECORATED = "decorated"
    COMMUNITY = "community"
    SELF_MADE = "self_made"
    VALVE = "valve"


class TF2Class(StrEnum):
    """Классы TF2."""

    SCOUT = "scout"
    SOLDIER = "soldier"
    PYRO = "pyro"
    DEMOMAN = "demoman"
    HEAVY = "heavy"
    ENGINEER = "engineer"
    MEDIC = "medic"
    SNIPER = "sniper"
    SPY = "spy"
    ALL_CLASS = "all_class"


class TF2KillstreakTier(StrEnum):
    """Уровни Killstreak."""

    NONE = "none"
    BASIC = "basic"
    SPECIALIZED = "specialized"
    PROFESSIONAL = "professional"


# Unusual эффекты с премиями
TF2_UNUSUAL_EFFECTS = {
    # God Tier
    "Burning Flames": 10.0,
    "Scorching Flames": 9.0,
    "Sunbeams": 8.0,
    "Hearts": 7.0,
    "Circling Hearts": 7.0,
    "Beams of Light": 7.0,
    # High Tier
    "Energy Orb": 5.0,
    "Cloudy Moon": 5.0,
    "Harvest Moon": 4.5,
    "Stormy Storm": 4.0,
    "Blizzardy Storm": 4.0,
    "Green Energy": 4.0,
    "Purple Energy": 4.0,
    # Mid Tier
    "Smoking": 3.0,
    "Steaming": 2.5,
    "Planets": 2.5,
    "Orbiting Fire": 3.0,
    "Nuts n Bolts": 2.0,
    "Massed Flies": 2.0,
    "Vivid Plasma": 3.5,
    # Newer Effects
    "Nebula": 4.0,
    "Darkblaze": 4.5,
    "Demonflame": 4.5,
    "Miami Nights": 3.5,
    "Disco Beat Down": 3.5,
}

# Killstreak sheens
TF2_KILLSTREAK_SHEENS = {
    "Team Shine": 1.0,
    "Deadly Daffodil": 1.2,
    "Manndarin": 1.3,
    "Mean Green": 1.2,
    "Agonizing Emerald": 1.4,
    "VillAlgonous Violet": 1.5,
    "Hot Rod": 1.6,
}

# Killstreaker effects
TF2_KILLSTREAKERS = {
    "Fire Horns": 1.5,
    "Cerebral Discharge": 1.4,
    "Tornado": 1.3,
    "Flames": 1.2,
    "Singularity": 1.4,
    "Incinerator": 1.3,
    "Hypno-Beam": 1.5,
}

# Australium оружие с премиями
TF2_AUSTRALIUM_WEAPONS = {
    "Australium Scattergun": 50.0,
    "Australium Rocket Launcher": 45.0,
    "Australium Medigun": 55.0,
    "Australium Sniper Rifle": 40.0,
    "Australium Knife": 60.0,
    "Australium Minigun": 50.0,
    "Australium Stickybomb Launcher": 45.0,
    "Australium Grenade Launcher": 45.0,
    "Australium Flamethrower": 40.0,
    "Australium Wrench": 50.0,
    "Australium SMG": 35.0,
    "Australium Frontier Justice": 35.0,
    "Australium Ambassador": 35.0,
    "Australium Force-A-Nature": 35.0,
    "Australium Tomislav": 35.0,
    "Australium Blutsauger": 35.0,
    "Australium Eyelander": 40.0,
    "Australium Axtinguisher": 35.0,
    "Australium Black Box": 40.0,
    "Golden Frying Pan": 2000.0,  # Очень редкий
}


@dataclass
class TF2Filter:
    """Фильтр для TF2 предметов."""

    # Качество
    qualities: list[TF2Quality] | None = None

    # Класс
    classes: list[TF2Class] | None = None

    # Unusual эффекты
    unusual_effects: list[str] | None = None
    min_unusual_tier: str | None = None  # "god", "high", "mid", "low"

    # Strange
    is_strange: bool | None = None
    has_strange_parts: bool = False
    strange_parts: list[str] | None = None

    # Killstreak
    killstreak_tier: TF2KillstreakTier | None = None
    killstreak_sheen: str | None = None
    killstreaker: str | None = None

    # Australium
    is_australium: bool | None = None

    # Festivized
    is_festive: bool | None = None
    is_festivized: bool | None = None

    # Vintage
    is_vintage: bool | None = None

    # Collectors
    is_collectors: bool | None = None

    # PAlgont
    pAlgont_color: str | None = None

    # Spell
    has_spell: bool = False
    spells: list[str] | None = None

    def matches(self, item: dict[str, Any]) -> bool:
        """Проверить соответствие предмета фильтру."""
        item_title = item.get("title", "").lower()

        # Проверка качества
        if self.qualities:
            item_quality = item.get("quality", "").lower()
            if not any(q.value in item_quality for q in self.qualities):
                return False

        # Проверка Australium
        if self.is_australium is not None:
            is_austr = "australium" in item_title
            if is_austr != self.is_australium:
                return False

        # Проверка Strange
        if self.is_strange is not None:
            is_str = "strange" in item_title
            if is_str != self.is_strange:
                return False

        # Проверка Unusual
        if self.unusual_effects:
            item_effect = item.get("unusual_effect", "")
            if item_effect not in self.unusual_effects:
                return False

        # Проверка Killstreak
        if self.killstreak_tier:
            item_ks = item.get("killstreak_tier", "none").lower()
            if self.killstreak_tier.value not in item_ks:
                return False

        # Проверка Festive/Festivized
        if self.is_festive is not None:
            is_fest = "festive" in item_title
            if is_fest != self.is_festive:
                return False

        if self.is_festivized is not None:
            is_festd = "festivized" in item_title
            if is_festd != self.is_festivized:
                return False

        # Проверка Vintage
        if self.is_vintage is not None:
            is_vint = "vintage" in item_title
            if is_vint != self.is_vintage:
                return False

        return True

    def calculate_premium(self, item: dict[str, Any]) -> float:
        """Рассчитать премию для предмета."""
        premium = 1.0
        item_title = item.get("title", "")

        # Премия за Unusual эффект
        item_effect = item.get("unusual_effect", "")
        if item_effect in TF2_UNUSUAL_EFFECTS:
            premium *= TF2_UNUSUAL_EFFECTS[item_effect]

        # Премия за Killstreak
        item_ks_tier = item.get("killstreak_tier", "none")
        if item_ks_tier == "professional":
            premium *= 2.0

            # Дополнительно за sheen и killstreaker
            item_sheen = item.get("killstreak_sheen", "")
            if item_sheen in TF2_KILLSTREAK_SHEENS:
                premium *= TF2_KILLSTREAK_SHEENS[item_sheen]

            item_ks = item.get("killstreaker", "")
            if item_ks in TF2_KILLSTREAKERS:
                premium *= TF2_KILLSTREAKERS[item_ks]

        elif item_ks_tier == "specialized":
            premium *= 1.5
        elif item_ks_tier == "basic":
            premium *= 1.2

        # Премия за Australium
        for austr_name, austr_price in TF2_AUSTRALIUM_WEAPONS.items():
            if austr_name.lower() in item_title.lower():
                premium *= austr_price / 40.0  # Нормализуем
                break

        # Премия за Strange
        if "strange" in item_title.lower():
            premium *= 1.3

        # Премия за Festivized
        if "festivized" in item_title.lower():
            premium *= 1.2

        return premium


# ============================================================================
# Rust Filters
# ============================================================================


class RustItemType(StrEnum):
    """Типы предметов Rust."""

    WEAPON = "weapon"
    DOOR = "door"
    ARMOR = "armor"
    TOOL = "tool"
    DEPLOYABLE = "deployable"
    MISC = "misc"


class RustRarity(StrEnum):
    """Редкость предметов Rust."""

    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    VERY_RARE = "very_rare"
    LIMITED = "limited"


# Rust ценные скины по категориям
RUST_VALUABLE_SKINS = {
    # Garage Doors (самые дорогие)
    "Garage Door": {
        "Neon Garage Door": 150.0,
        "Looter's Garage Door": 100.0,
        "Salvaged Garage Door": 80.0,
        "Apocalypse Garage Door": 70.0,
        "Punishment Garage Door": 60.0,
    },
    # AK-47 skins
    "AK-47": {
        "Glory AK47": 80.0,
        "Tempered AK47": 60.0,
        "AK47 Alien Red": 50.0,
        "Big Grin AK47": 40.0,
        "Digital Camo AK": 30.0,
    },
    # LR-300 skins
    "LR-300": {
        "Forest RAlgoder LR300": 50.0,
        "Tempered LR300": 40.0,
        "Arctic LR300": 35.0,
    },
    # M249 skins
    "M249": {
        "Alien Relic M249": 45.0,
        "Bombing M249": 35.0,
    },
    # Metal Doors
    "Metal Door": {
        "Neon Metal Door": 60.0,
        "Looter's Metal Door": 40.0,
    },
    # Roadsign Armor
    "Roadsign Armor": {
        "Whiteout Armor": 30.0,
        "Neon Armor": 25.0,
    },
}

# Rust twitch drops с премиями
RUST_TWITCH_DROPS = {
    "Twitch Rivals": 2.0,  # x2 премия
    "Charitable Rust": 2.5,
    "Shadowfrax": 1.5,
    "Ser Winter": 1.5,
}

# Luminescent скины (светящиеся)
RUST_LUMINESCENT_PREMIUM = 1.5  # +50% за luminescent

# Tempered скины
RUST_TEMPERED_PREMIUM = 1.8  # +80% за tempered


@dataclass
class RustFilter:
    """Фильтр для Rust предметов."""

    # Тип предмета
    item_types: list[RustItemType] | None = None

    # Редкость
    rarities: list[RustRarity] | None = None

    # Специальные типы
    is_luminescent: bool | None = None
    is_tempered: bool | None = None
    is_limited: bool | None = None

    # Twitch drops
    is_twitch_drop: bool | None = None
    twitch_streamer: str | None = None

    # Категории предметов
    weapon_types: list[str] | None = None  # ["AK-47", "LR-300", "M249"]
    door_types: list[str] | None = None  # ["Garage Door", "Metal Door"]
    armor_types: list[str] | None = None

    # Только торгуемые
    is_tradeable: bool = True

    def matches(self, item: dict[str, Any]) -> bool:
        """Проверить соответствие предмета фильтру."""
        item_title = item.get("title", "").lower()

        # Проверка типа предмета
        if self.item_types:
            item_type = item.get("item_type", "").lower()
            if not any(t.value in item_type for t in self.item_types):
                return False

        # Проверка категорий оружия
        if self.weapon_types:
            if not any(w.lower() in item_title for w in self.weapon_types):
                return False

        # Проверка door types
        if self.door_types:
            if not any(d.lower() in item_title for d in self.door_types):
                return False

        # Проверка luminescent
        if self.is_luminescent is not None:
            is_lum = "luminescent" in item_title
            if is_lum != self.is_luminescent:
                return False

        # Проверка tempered
        if self.is_tempered is not None:
            is_temp = "tempered" in item_title
            if is_temp != self.is_tempered:
                return False

        # Проверка limited
        if self.is_limited is not None:
            is_lim = item.get("is_limited", False) or "limited" in item_title
            if is_lim != self.is_limited:
                return False

        return True

    def calculate_premium(self, item: dict[str, Any]) -> float:
        """Рассчитать премию для предмета."""
        premium = 1.0
        item_title = item.get("title", "")

        # Проверка valuable skins
        for skins in RUST_VALUABLE_SKINS.values():
            for skin_name, skin_premium in skins.items():
                if skin_name.lower() in item_title.lower():
                    premium *= skin_premium / 30.0  # Нормализуем
                    break

        # Премия за luminescent
        if "luminescent" in item_title.lower():
            premium *= RUST_LUMINESCENT_PREMIUM

        # Премия за tempered
        if "tempered" in item_title.lower():
            premium *= RUST_TEMPERED_PREMIUM

        # Премия за twitch drops
        for streamer, twitch_mult in RUST_TWITCH_DROPS.items():
            if streamer.lower() in item_title.lower():
                premium *= twitch_mult
                break

        # Премия за limited
        if item.get("is_limited"):
            premium *= 1.5

        return premium


# ============================================================================
# Unified Game Filter
# ============================================================================


@dataclass
class UnifiedGameFilter:
    """Унифицированный фильтр для всех игр."""

    game: str

    # Общие параметры
    min_price: Decimal = Decimal("1.0")
    max_price: Decimal = Decimal("1000.0")
    min_profit_percent: Decimal = Decimal("5.0")
    min_liquidity: int = 1
    max_trade_lock_days: int = 7

    # Game-specific фильтры
    csgo_filter: CSGOFilter | None = None
    dota2_filter: Dota2Filter | None = None
    tf2_filter: TF2Filter | None = None
    rust_filter: RustFilter | None = None

    # Категории для поиска
    categories: list[str] = field(default_factory=list)

    # Blacklist
    blacklist_keywords: list[str] = field(default_factory=list)

    def get_game_filter(
        self,
    ) -> CSGOFilter | Dota2Filter | TF2Filter | RustFilter | None:
        """Получить фильтр для текущей игры."""
        if self.game == "csgo":
            return self.csgo_filter or CSGOFilter()
        if self.game == "dota2":
            return self.dota2_filter or Dota2Filter()
        if self.game == "tf2":
            return self.tf2_filter or TF2Filter()
        if self.game == "rust":
            return self.rust_filter or RustFilter()
        return None

    def matches(self, item: dict[str, Any]) -> bool:
        """Проверить соответствие предмета фильтру."""
        # Проверка blacklist
        item_title = item.get("title", "").lower()
        for keyword in self.blacklist_keywords:
            if keyword.lower() in item_title:
                return False

        # Проверка категорий
        if self.categories:
            item_category = item.get("category", "")
            if item_category not in self.categories:
                return False

        # Проверка game-specific фильтра
        game_filter = self.get_game_filter()
        if game_filter:
            return game_filter.matches(item)

        return True

    def calculate_premium(self, item: dict[str, Any]) -> float:
        """Рассчитать премию для предмета."""
        game_filter = self.get_game_filter()
        if game_filter:
            return game_filter.calculate_premium(item)
        return 1.0


# ============================================================================
# Factory Functions
# ============================================================================


def create_csgo_float_filter(
    wear: CSGOWear,
    float_min: float | None = None,
    float_max: float | None = None,
    is_stattrak: bool = False,
) -> CSGOFilter:
    """Создать фильтр для CS:GO по float."""
    # Получить диапазон float для wear
    if float_min is None or float_max is None:
        float_range = CSGO_FLOAT_RANGES.get(wear, (0.0, 1.0))
        float_min = float_min or float_range[0]
        float_max = float_max or float_range[1]

    return CSGOFilter(
        wear=wear,
        float_min=float_min,
        float_max=float_max,
        is_stattrak=is_stattrak,
    )


def create_csgo_doppler_filter(
    phase: CSGODopplerPhase,
    is_stattrak: bool = False,
) -> CSGOFilter:
    """Создать фильтр для Doppler."""
    return CSGOFilter(
        wear=CSGOWear.FACTORY_NEW,
        doppler_phase=phase,
        is_stattrak=is_stattrak,
    )


def create_csgo_blue_gem_filter(
    weapon: str = "ak47",
) -> CSGOFilter:
    """Создать фильтр для Blue Gem."""
    patterns = CSGO_BLUE_GEM_PATTERNS.get(f"{weapon}_best", [])
    return CSGOFilter(
        pattern_ids=patterns,
    )


def create_dota2_arcana_filter() -> Dota2Filter:
    """Создать фильтр для Arcana предметов."""
    return Dota2Filter(
        qualities=[Dota2Quality.ARCANA, Dota2Quality.EXALTED],
    )


def create_dota2_unusual_courier_filter() -> Dota2Filter:
    """Создать фильтр для Unusual курьеров."""
    return Dota2Filter(
        qualities=[Dota2Quality.UNUSUAL],
        item_types=["courier"],
        has_ethereal_gem=True,
        has_prismatic_gem=True,
    )


def create_tf2_unusual_filter(
    min_tier: str = "mid",
    classes: list[TF2Class] | None = None,
) -> TF2Filter:
    """Создать фильтр для Unusual предметов TF2."""
    # Определяем эффекты по tier
    tier_effects = {
        "god": [
            "Burning Flames",
            "Scorching Flames",
            "Sunbeams",
            "Hearts",
            "Circling Hearts",
        ],
        "high": [
            "Energy Orb",
            "Cloudy Moon",
            "Harvest Moon",
            "Stormy Storm",
            "Green Energy",
            "Purple Energy",
        ],
        "mid": ["Smoking", "Steaming", "Planets", "Orbiting Fire", "Vivid Plasma"],
        "low": ["Nuts n Bolts", "Massed Flies"],
    }

    effects = []
    tiers = ["god", "high", "mid", "low"]
    start_index = tiers.index(min_tier) if min_tier in tiers else 2
    for tier in tiers[: start_index + 1]:
        effects.extend(tier_effects.get(tier, []))

    return TF2Filter(
        qualities=[TF2Quality.UNUSUAL],
        unusual_effects=effects,
        classes=classes,
    )


def create_tf2_australium_filter() -> TF2Filter:
    """Создать фильтр для Australium оружия."""
    return TF2Filter(
        is_australium=True,
        is_strange=True,  # Strange Australium более ценны
    )


def create_rust_garage_door_filter() -> RustFilter:
    """Создать фильтр для Garage Doors в Rust."""
    return RustFilter(
        door_types=["Garage Door"],
        is_tradeable=True,
    )


def create_rust_valuable_weapons_filter() -> RustFilter:
    """Создать фильтр для ценного оружия в Rust."""
    return RustFilter(
        weapon_types=["AK-47", "LR-300", "M249"],
        is_tradeable=True,
    )


# ============================================================================
# Preset Filters
# ============================================================================


PRESET_FILTERS = {
    "csgo": {
        "low_float_fn": create_csgo_float_filter(CSGOWear.FACTORY_NEW, 0.00, 0.01),
        "premium_ft": create_csgo_float_filter(CSGOWear.FIELD_TESTED, 0.15, 0.18),
        "doppler_ruby": create_csgo_doppler_filter(CSGODopplerPhase.RUBY),
        "doppler_sapphire": create_csgo_doppler_filter(CSGODopplerPhase.SAPPHIRE),
        "blue_gem_ak": create_csgo_blue_gem_filter("ak47"),
        "blue_gem_karambit": create_csgo_blue_gem_filter("karambit"),
    },
    "dota2": {
        "arcana": create_dota2_arcana_filter(),
        "unusual_courier": create_dota2_unusual_courier_filter(),
    },
    "tf2": {
        "unusual_god": create_tf2_unusual_filter("god"),
        "unusual_high": create_tf2_unusual_filter("high"),
        "australium": create_tf2_australium_filter(),
    },
    "rust": {
        "garage_doors": create_rust_garage_door_filter(),
        "valuable_weapons": create_rust_valuable_weapons_filter(),
    },
}


def get_preset_filter(game: str, preset_name: str) -> Any:
    """Получить предустановленный фильтр.

    Args:
        game: Код игры
        preset_name: Название пресета

    Returns:
        Фильтр или None
    """
    game_presets = PRESET_FILTERS.get(game, {})
    return game_presets.get(preset_name)


def list_preset_filters(game: str) -> list[str]:
    """Получить список доступных пресетов для игры.

    Args:
        game: Код игры

    Returns:
        Список названий пресетов
    """
    return list(PRESET_FILTERS.get(game, {}).keys())


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "CSGO_BLUE_GEM_PATTERNS",
    "CSGO_DOPPLER_PREMIUMS",
    "CSGO_FADE_PERCENTAGES",
    "CSGO_FLOAT_RANGES",
    "CSGO_KATOWICE_2014_STICKERS",
    "DOTA2_ETHEREAL_GEMS",
    "DOTA2_PRISMATIC_GEMS",
    "DOTA2_UNLOCK_STYLES",
    "DOTA2_VALUABLE_ITEMS",
    "PRESET_FILTERS",
    "RUST_LUMINESCENT_PREMIUM",
    "RUST_TEMPERED_PREMIUM",
    "RUST_TWITCH_DROPS",
    "RUST_VALUABLE_SKINS",
    "TF2_AUSTRALIUM_WEAPONS",
    "TF2_KILLSTREAKERS",
    "TF2_KILLSTREAK_SHEENS",
    "TF2_UNUSUAL_EFFECTS",
    "CSGODopplerPhase",
    "CSGOFilter",
    # CS:GO
    "CSGOWear",
    "Dota2Filter",
    # Dota 2
    "Dota2Quality",
    "Dota2Rarity",
    "RustFilter",
    # Rust
    "RustItemType",
    "RustRarity",
    "TF2Class",
    "TF2Filter",
    "TF2KillstreakTier",
    # TF2
    "TF2Quality",
    # Unified
    "UnifiedGameFilter",
    "create_csgo_blue_gem_filter",
    "create_csgo_doppler_filter",
    "create_csgo_float_filter",
    "create_dota2_arcana_filter",
    "create_dota2_unusual_courier_filter",
    "create_rust_garage_door_filter",
    "create_rust_valuable_weapons_filter",
    "create_tf2_australium_filter",
    "create_tf2_unusual_filter",
    "get_preset_filter",
    "list_preset_filters",
]
