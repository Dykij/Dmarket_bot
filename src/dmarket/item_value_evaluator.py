"""Item Value Evaluator - оценка редкости и внутренней ценности предметов.

Этот модуль анализирует атрибуты предметов для всех игр:
- CS2: Float value, Stickers (Katowice 2014, Holo), Patterns (Case Hardened Blue, Doppler)
- Dota 2: Prismatic/Ethereal Gems, Inscribed gems, Unlocked Styles
- TF2: Strange Parts, Halloween Spells, Unusual Effects
- Rust: Glow items, Limited edition, Twitch Drops

Бот может "переплатить" 2-5% за редкий атрибут, если он позволит продать на 20-30% дороже.

Использование:
    ```python
    from src.dmarket.item_value_evaluator import ItemValueEvaluator

    evaluator = ItemValueEvaluator()
    result = evaluator.evaluate(item_data)

    if result.requires_manual_review:
        # Отправить уведомление в Telegram - это джекпот!
        await notify_admin(result)
    elif result.value_multiplier > 1.0:
        # Готовы переплатить за редкость
        adjusted_max_price = base_price * result.value_multiplier
    ```
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class GameType(StrEnum):
    """Поддерживаемые игры."""

    CS2 = "csgo"  # CS:GO / CS2
    DOTA2 = "dota2"
    TF2 = "tf2"
    RUST = "rust"


class RarityTier(StrEnum):
    """Уровни редкости предмета."""

    COMMON = "common"  # Обычный
    UNCOMMON = "uncommon"  # Необычный
    RARE = "rare"  # Редкий
    EPIC = "epic"  # Эпический
    LEGENDARY = "legendary"  # Легендарный
    JACKPOT = "jackpot"  # Джекпот (требует ручной проверки)


@dataclass
class EvaluationResult:
    """Результат оценки ценности предмета."""

    # Основные данные
    item_id: str
    game: GameType
    title: str

    # Оценка редкости
    rarity_tier: RarityTier = RarityTier.COMMON
    value_multiplier: float = 1.0  # Множитель цены (1.0 = без бонуса)

    # Найденные атрибуты
    detected_attributes: list[str] = field(default_factory=list)
    bonus_reasons: list[str] = field(default_factory=list)

    # Флаги
    requires_manual_review: bool = False  # Нужна ручная проверка (джекпот)
    is_profitable_rare: bool = False  # Можно заработать на редкости

    # Детали для CS2
    float_value: float | None = None
    stickers: list[dict[str, Any]] = field(default_factory=list)
    pattern_id: int | None = None
    phase: str | None = None

    # Детали для Dota 2
    gems: list[dict[str, Any]] = field(default_factory=list)
    unlocked_styles: int = 0

    # Детали для TF2
    strange_parts: list[str] = field(default_factory=list)
    spells: list[str] = field(default_factory=list)
    unusual_effect: str | None = None

    # Детали для Rust
    is_glow: bool = False
    is_limited_edition: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Преобразовать в словарь."""
        return {
            "item_id": self.item_id,
            "game": self.game,
            "title": self.title,
            "rarity_tier": self.rarity_tier,
            "value_multiplier": self.value_multiplier,
            "detected_attributes": self.detected_attributes,
            "bonus_reasons": self.bonus_reasons,
            "requires_manual_review": self.requires_manual_review,
            "is_profitable_rare": self.is_profitable_rare,
        }


class ItemValueEvaluator:
    """Оценщик ценности предметов на основе редких атрибутов.

    Этот класс анализирует мета-данные предметов и определяет,
    стоит ли платить больше за редкие атрибуты.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Инициализация оценщика.

        Args:
            config: Конфигурация оценки (опционально)
        """
        self.config = config or {}

        # Загружаем конфигурацию редких атрибутов
        self._load_rare_attributes_config()

        logger.info("ItemValueEvaluator initialized")

    def _load_rare_attributes_config(self) -> None:
        """Загрузить конфигурацию редких атрибутов."""
        # CS2: Float пороги
        self.cs2_float_thresholds = {
            "double_zero": 0.01,  # < 0.01 = Double Zero (+15-30%)
            "triple_zero": 0.001,  # < 0.001 = Triple Zero (+30-50%)
            "quad_zero": 0.0001,  # < 0.0001 = Quad Zero (JACKPOT)
        }

        # CS2: Ценные наклейки (Katowice 2014/2015, iBUYPOWER и т.д.)
        self.cs2_valuable_stickers = {
            # Катовице 2014 (самые ценные)
            "katowice_2014_holo": [
                "iBUYPOWER (Holo) | Katowice 2014",
                "Titan (Holo) | Katowice 2014",
                "Reason Gaming (Holo) | Katowice 2014",
                "VOX Eminor (Holo) | Katowice 2014",
                "Team LDLC.com (Holo) | Katowice 2014",
                "Natus Vincere (Holo) | Katowice 2014",
                "compLexity Gaming (Holo) | Katowice 2014",
                "HellRaisers (Holo) | Katowice 2014",
                "Fnatic (Holo) | Katowice 2014",
                "Ninjas in Pyjamas (Holo) | Katowice 2014",
            ],
            "katowice_2014": [
                "iBUYPOWER | Katowice 2014",
                "Titan | Katowice 2014",
                "Reason Gaming | Katowice 2014",
                "VOX Eminor | Katowice 2014",
            ],
            # Cologne 2014 Holo
            "cologne_2014_holo": [
                "(Holo) | Cologne 2014",
            ],
            # Crown Foil и другие ценные
            "premium_stickers": [
                "Crown (Foil)",
                "Howling Dawn",
                "Flammable (Foil)",
                "Headhunter (Foil)",
            ],
        }

        # CS2: Ценные паттерны
        self.cs2_valuable_patterns = {
            # Case Hardened Blue Gem паттерны (AK-47)
            "case_hardened_blue_gem": [661, 670, 321, 955, 387, 868],
            # Fade 100%
            "fade_100": list(range(1, 50)),
            # Doppler фазы
            "doppler_premium": ["Ruby", "Sapphire", "Black Pearl", "Emerald"],
        }

        # Dota 2: Ценные гемы
        self.dota2_valuable_gems = {
            # Prismatic Gems (цвета)
            "prismatic_rare": [
                "Ethereal Flame",
                "Bewitching Flare",
                "Blossom Red",
                "Creator's Light",
                "Cursed Black",
                "Dungeon Doom",
                "Champion's Aura",
            ],
            # Ethereal Gems (эффекты)
            "ethereal_rare": [
                "Ethereal Flame",
                "Burning Animus",
                "Resonant Energy",
                "Piercing Beams",
                "Affliction of Vermin",
            ],
        }

        # TF2: Ценные атрибуты
        self.tf2_valuable_attributes = {
            # Halloween Spells (больше не выпадают)
            "halloween_spells": [
                "Exorcism",
                "Spectral Spectrum",
                "Sinister Staining",
                "Voices From Below",
                "Pumpkin Bombs",
                "Halloween Fire",
                "Die Job",
                "Corpse Gray",
                "Violent Violet",
                "Bruised Purple",
            ],
            # Strange Parts (счетчики)
            "strange_parts_rare": [
                "Kills",
                "Headshot Kills",
                "Critical Kills",
                "Domination Kills",
                "Revenge Kills",
            ],
            # Unusual Effects (самые ценные)
            "unusual_effects_tier1": [
                "Burning Flames",
                "Scorching Flames",
                "Sunbeams",
                "Cloudy Moon",
            ],
        }

        # Rust: Ценные атрибуты
        self.rust_valuable_attributes = {
            # Glow items (светящиеся)
            "glow_keywords": [
                "Glow",
                "Glowing",
                "Neon",
                "Luminescent",
                "Radiant",
            ],
            # Limited edition
            "limited_keywords": [
                "Limited",
                "Exclusive",
                "Charity",
                "Twitch Drops",
            ],
        }

    def evaluate(self, item_data: dict[str, Any]) -> EvaluationResult:
        """Оценить ценность предмета.

        Args:
            item_data: Данные предмета от DMarket API

        Returns:
            EvaluationResult с оценкой редкости
        """
        # Извлекаем базовые данные
        item_id = item_data.get("itemId") or item_data.get("extra", {}).get(
            "offerId", "unknown"
        )
        game = self._detect_game(item_data)
        title = item_data.get("title", "")

        result = EvaluationResult(
            item_id=item_id,
            game=game,
            title=title,
        )

        # Оцениваем по типу игры
        if game == GameType.CS2:
            self._evaluate_cs2(item_data, result)
        elif game == GameType.DOTA2:
            self._evaluate_dota2(item_data, result)
        elif game == GameType.TF2:
            self._evaluate_tf2(item_data, result)
        elif game == GameType.RUST:
            self._evaluate_rust(item_data, result)

        # Определяем финальный рейтинг
        self._calculate_final_rating(result)

        if result.value_multiplier > 1.0:
            logger.info(
                f"Rare item found: {title} "
                f"(multiplier={result.value_multiplier:.2f}, "
                f"tier={result.rarity_tier})"
            )

        return result

    def _detect_game(self, item_data: dict[str, Any]) -> GameType:
        """Определить игру по данным предмета."""
        game_id = item_data.get("gameId", "").lower()
        game_type = item_data.get("gameType", "").lower()
        game = item_data.get("game", "").lower()

        combined = f"{game_id}{game_type}{game}"

        if "csgo" in combined or "cs2" in combined or "a8db" in combined:
            return GameType.CS2
        if "dota" in combined:
            return GameType.DOTA2
        if "tf2" in combined or "team fortress" in combined:
            return GameType.TF2
        if "rust" in combined:
            return GameType.RUST

        return GameType.CS2  # Default

    def _evaluate_cs2(
        self, item_data: dict[str, Any], result: EvaluationResult
    ) -> None:
        """Оценить CS2 предмет."""
        extra = item_data.get("extra", {})

        # 1. Проверяем Float
        float_value = extra.get("floatValue") or extra.get("float")
        if float_value is not None:
            try:
                result.float_value = float(float_value)
                self._evaluate_cs2_float(result)
            except (ValueError, TypeError):
                pass

        # 2. Проверяем наклейки
        stickers = extra.get("stickers", [])
        if isinstance(stickers, list) and stickers:
            result.stickers = stickers
            self._evaluate_cs2_stickers(result)

        # 3. Проверяем паттерн (paint seed)
        pattern_id = extra.get("paintSeed") or extra.get("pattern")
        if pattern_id is not None:
            try:
                result.pattern_id = int(pattern_id)
                self._evaluate_cs2_pattern(result)
            except (ValueError, TypeError):
                pass

        # 4. Проверяем фазу (для Doppler)
        phase = extra.get("phase", "")
        if phase:
            result.phase = phase
            self._evaluate_cs2_phase(result)

    def _evaluate_cs2_float(self, result: EvaluationResult) -> None:
        """Оценить float value."""
        if result.float_value is None:
            return

        fv = result.float_value

        # Quad Zero (< 0.0001) - JACKPOT
        if fv < self.cs2_float_thresholds["quad_zero"]:
            result.value_multiplier += 0.50  # +50%
            result.detected_attributes.append(f"Quad Zero Float: {fv:.6f}")
            result.bonus_reasons.append("Extremely rare float (Quad Zero)")
            result.requires_manual_review = True

        # Triple Zero (< 0.001)
        elif fv < self.cs2_float_thresholds["triple_zero"]:
            result.value_multiplier += 0.30  # +30%
            result.detected_attributes.append(f"Triple Zero Float: {fv:.4f}")
            result.bonus_reasons.append("Very rare float (Triple Zero)")

        # Double Zero (< 0.01)
        elif fv < self.cs2_float_thresholds["double_zero"]:
            result.value_multiplier += 0.15  # +15%
            result.detected_attributes.append(f"Low Float: {fv:.3f}")
            result.bonus_reasons.append("Low float (Double Zero)")

    def _evaluate_cs2_stickers(self, result: EvaluationResult) -> None:
        """Оценить наклейки."""
        for sticker in result.stickers:
            sticker_name = (
                sticker.get("name", "") if isinstance(sticker, dict) else str(sticker)
            )

            # Проверяем Katowice 2014 Holo (JACKPOT)
            for kato_holo in self.cs2_valuable_stickers["katowice_2014_holo"]:
                if kato_holo.lower() in sticker_name.lower():
                    result.value_multiplier += 1.0  # +100% минимум
                    result.detected_attributes.append(
                        f"Katowice 2014 Holo: {sticker_name}"
                    )
                    result.bonus_reasons.append("Katowice 2014 Holo sticker (JACKPOT)")
                    result.requires_manual_review = True
                    return  # Одной такой наклейки достаточно

            # Проверяем обычные Katowice 2014
            for kato in self.cs2_valuable_stickers["katowice_2014"]:
                if kato.lower() in sticker_name.lower():
                    result.value_multiplier += 0.25  # +25%
                    result.detected_attributes.append(f"Katowice 2014: {sticker_name}")
                    result.bonus_reasons.append("Katowice 2014 sticker")

            # Проверяем Cologne 2014 Holo
            for cologne in self.cs2_valuable_stickers["cologne_2014_holo"]:
                if cologne.lower() in sticker_name.lower():
                    result.value_multiplier += 0.10  # +10%
                    result.detected_attributes.append(
                        f"Cologne 2014 Holo: {sticker_name}"
                    )
                    result.bonus_reasons.append("Cologne 2014 Holo sticker")

            # Проверяем Premium stickers
            for premium in self.cs2_valuable_stickers["premium_stickers"]:
                if premium.lower() in sticker_name.lower():
                    result.value_multiplier += 0.15  # +15%
                    result.detected_attributes.append(
                        f"Premium Sticker: {sticker_name}"
                    )
                    result.bonus_reasons.append("Premium sticker (Crown/Howling Dawn)")

    def _evaluate_cs2_pattern(self, result: EvaluationResult) -> None:
        """Оценить паттерн (paint seed)."""
        if result.pattern_id is None:
            return

        title_lower = result.title.lower()

        # Case Hardened Blue Gem
        if "case hardened" in title_lower:
            if (
                result.pattern_id
                in self.cs2_valuable_patterns["case_hardened_blue_gem"]
            ):
                result.value_multiplier += 0.50  # +50%
                result.detected_attributes.append(
                    f"Blue Gem Pattern: #{result.pattern_id}"
                )
                result.bonus_reasons.append("Case Hardened Blue Gem pattern")
                result.requires_manual_review = True

        # Fade 100%
        if "fade" in title_lower:
            if result.pattern_id in self.cs2_valuable_patterns["fade_100"]:
                result.value_multiplier += 0.20  # +20%
                result.detected_attributes.append(
                    f"High Fade Pattern: #{result.pattern_id}"
                )
                result.bonus_reasons.append("High fade percentage pattern")

    def _evaluate_cs2_phase(self, result: EvaluationResult) -> None:
        """Оценить фазу Doppler."""
        if not result.phase:
            return

        phase_upper = result.phase.upper()

        # Ruby, Sapphire, Black Pearl, Emerald
        for premium in self.cs2_valuable_patterns["doppler_premium"]:
            if premium.upper() in phase_upper:
                result.value_multiplier += 0.40  # +40%
                result.detected_attributes.append(f"Premium Doppler: {result.phase}")
                result.bonus_reasons.append(f"Premium Doppler phase ({result.phase})")
                result.requires_manual_review = True
                return

        # Phase 2 и Phase 4 (более ценные)
        if "PHASE 2" in phase_upper or "PHASE 4" in phase_upper:
            result.value_multiplier += 0.10  # +10%
            result.detected_attributes.append(f"Good Doppler Phase: {result.phase}")
            result.bonus_reasons.append("Desirable Doppler phase")

    def _evaluate_dota2(
        self, item_data: dict[str, Any], result: EvaluationResult
    ) -> None:
        """Оценить Dota 2 предмет."""
        extra = item_data.get("extra", {})
        title = result.title.lower()

        # 1. Проверяем гемы
        gems = extra.get("gems", [])
        if isinstance(gems, list):
            result.gems = gems
            self._evaluate_dota2_gems(result)

        # 2. Проверяем количество гемов (Inscribed)
        gems_count = extra.get("gemsCount") or len(gems)
        if "inscribed" in title and gems_count and int(gems_count) >= 3:
            result.value_multiplier += 0.05  # +5%
            result.detected_attributes.append(f"Multi-gem Inscribed: {gems_count} gems")
            result.bonus_reasons.append("Multiple inscribed gems")

        # 3. Проверяем открытые стили
        styles = extra.get("styles") or extra.get("unlockedStyles")
        if styles:
            try:
                result.unlocked_styles = int(styles)
                if result.unlocked_styles >= 2:
                    result.value_multiplier += 0.08  # +8%
                    result.detected_attributes.append(
                        f"Unlocked Styles: {result.unlocked_styles}"
                    )
                    result.bonus_reasons.append("Multiple unlocked styles")
            except (ValueError, TypeError):
                pass

    def _evaluate_dota2_gems(self, result: EvaluationResult) -> None:
        """Оценить гемы Dota 2."""
        for gem in result.gems:
            gem_name = gem.get("name", "") if isinstance(gem, dict) else str(gem)
            # gem_type is extracted but currently unused - kept for future enhancements
            _gem_type = (
                gem.get("type", "") if isinstance(gem, dict) else ""
            )  # noqa: F841

            # Проверяем редкие Prismatic гемы
            for rare_gem in self.dota2_valuable_gems["prismatic_rare"]:
                if rare_gem.lower() in gem_name.lower():
                    result.value_multiplier += 0.20  # +20%
                    result.detected_attributes.append(f"Rare Prismatic Gem: {gem_name}")
                    result.bonus_reasons.append("Rare prismatic gem (valuable color)")

            # Проверяем редкие Ethereal гемы
            for rare_gem in self.dota2_valuable_gems["ethereal_rare"]:
                if rare_gem.lower() in gem_name.lower():
                    result.value_multiplier += 0.15  # +15%
                    result.detected_attributes.append(f"Rare Ethereal Gem: {gem_name}")
                    result.bonus_reasons.append("Rare ethereal gem (valuable effect)")

    def _evaluate_tf2(
        self, item_data: dict[str, Any], result: EvaluationResult
    ) -> None:
        """Оценить TF2 предмет."""
        extra = item_data.get("extra", {})
        title = result.title.lower()

        # 1. Проверяем Strange Parts
        parts = extra.get("parts", []) or extra.get("strangeParts", [])
        if parts:
            result.strange_parts = [
                p.get("name", str(p)) if isinstance(p, dict) else str(p) for p in parts
            ]
            self._evaluate_tf2_parts(result)

        # 2. Проверяем Halloween Spells
        spells = extra.get("spells", [])
        if spells:
            result.spells = [
                s.get("name", str(s)) if isinstance(s, dict) else str(s) for s in spells
            ]
            self._evaluate_tf2_spells(result)

        # 3. Проверяем Unusual Effect
        effect = extra.get("effect") or extra.get("unusualEffect")
        if effect:
            result.unusual_effect = effect
            self._evaluate_tf2_unusual(result)

        # 4. Проверяем Strange в названии
        if "strange" in title and result.strange_parts:
            result.value_multiplier += 0.05  # +5%
            result.bonus_reasons.append("Strange item with parts")

    def _evaluate_tf2_parts(self, result: EvaluationResult) -> None:
        """Оценить Strange Parts."""
        for part in result.strange_parts:
            for rare_part in self.tf2_valuable_attributes["strange_parts_rare"]:
                if rare_part.lower() in part.lower():
                    result.value_multiplier += 0.05  # +5% за каждый
                    result.detected_attributes.append(f"Strange Part: {part}")
                    result.bonus_reasons.append(f"Valuable strange part ({part})")

    def _evaluate_tf2_spells(self, result: EvaluationResult) -> None:
        """Оценить Halloween Spells."""
        for spell in result.spells:
            for rare_spell in self.tf2_valuable_attributes["halloween_spells"]:
                if rare_spell.lower() in spell.lower():
                    result.value_multiplier += 0.15  # +15% за заклинание
                    result.detected_attributes.append(f"Halloween Spell: {spell}")
                    result.bonus_reasons.append("Halloween spell (discontinued)")

    def _evaluate_tf2_unusual(self, result: EvaluationResult) -> None:
        """Оценить Unusual Effect."""
        if not result.unusual_effect:
            return

        for tier1_effect in self.tf2_valuable_attributes["unusual_effects_tier1"]:
            if tier1_effect.lower() in result.unusual_effect.lower():
                result.value_multiplier += 0.25  # +25%
                result.detected_attributes.append(
                    f"Tier 1 Unusual: {result.unusual_effect}"
                )
                result.bonus_reasons.append("Top-tier unusual effect")
                return

    def _evaluate_rust(
        self, item_data: dict[str, Any], result: EvaluationResult
    ) -> None:
        """Оценить Rust предмет."""
        title = result.title

        # 1. Проверяем Glow items
        for keyword in self.rust_valuable_attributes["glow_keywords"]:
            if keyword.lower() in title.lower():
                result.is_glow = True
                result.value_multiplier += 0.10  # +10%
                result.detected_attributes.append(f"Glow Item: {keyword}")
                result.bonus_reasons.append("Glow item (higher demand)")
                break

        # 2. Проверяем Limited Edition
        for keyword in self.rust_valuable_attributes["limited_keywords"]:
            if keyword.lower() in title.lower():
                result.is_limited_edition = True
                result.value_multiplier += 0.15  # +15%
                result.detected_attributes.append(f"Limited Edition: {keyword}")
                result.bonus_reasons.append("Limited edition item")
                break

    def _calculate_final_rating(self, result: EvaluationResult) -> None:
        """Рассчитать финальный рейтинг редкости."""
        multiplier = result.value_multiplier

        if result.requires_manual_review or multiplier >= 1.50:
            result.rarity_tier = RarityTier.JACKPOT
        elif multiplier >= 1.30:
            result.rarity_tier = RarityTier.LEGENDARY
        elif multiplier >= 1.20:
            result.rarity_tier = RarityTier.EPIC
        elif multiplier >= 1.10:
            result.rarity_tier = RarityTier.RARE
        elif multiplier >= 1.05:
            result.rarity_tier = RarityTier.UNCOMMON
        else:
            result.rarity_tier = RarityTier.COMMON

        # Флаг прибыльности
        result.is_profitable_rare = multiplier >= 1.10

    def get_max_overpay_percent(self, result: EvaluationResult) -> float:
        """Получить максимальный процент переплаты за редкость.

        Бот готов переплатить только часть от потенциальной прибыли.

        Args:
            result: Результат оценки

        Returns:
            Максимальный процент переплаты (0-10%)
        """
        if result.requires_manual_review:
            return 0.0  # Джекпоты требуют ручной проверки

        # Переплачиваем только 20-30% от потенциальной наценки
        potential_markup = (result.value_multiplier - 1.0) * 100  # %
        max_overpay = min(potential_markup * 0.25, 5.0)  # Макс 5%

        return max(0.0, max_overpay)


# Глобальный экземпляр
_evaluator: ItemValueEvaluator | None = None


def get_item_evaluator() -> ItemValueEvaluator:
    """Получить глобальный экземпляр ItemValueEvaluator."""
    global _evaluator
    if _evaluator is None:
        _evaluator = ItemValueEvaluator()
    return _evaluator
