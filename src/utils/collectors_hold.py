"""Collector's Hold - модуль автоматического удержания редких предметов.

Этот модуль анализирует купленные предметы и автоматически:
1. Помечает редкие как HOLD_RARE (не выставлять на продажу)
2. Отправляет уведомление в Telegram с описанием находки
3. Предлагает альтернативные площадки для продажи (Buff163, CSFloat и др.)

Триггеры редкости:
- CS2: Float < 0.01, Katowice 2014/Crown stickers, Doppler Ruby/Sapphire/Emerald
- Dota 2: Prismatic/Ethereal gems, 3+ inscribed gems
- TF2: Halloween Spells, Strange Parts
- Rust: Glow items, Limited Edition

Использование:
    ```python
    from src.utils.collectors_hold import CollectorsHoldManager

    manager = CollectorsHoldManager(db, telegram_bot, evaluator)

    # После покупки предмета
    decision = await manager.process_purchased_item(item_data)
    if decision.should_hold:
        # НЕ выставляем на продажу
        print(f"Редкий предмет сохранен: {decision.reason}")
    else:
        # Выставляем на DMarket
        await listing_manager.list_for_sale(item_data)
    ```
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.dmarket.item_value_evaluator import EvaluationResult, ItemValueEvaluator
    from src.utils.trading_persistence import TradingPersistence

logger = logging.getLogger(__name__)


class HoldReason(StrEnum):
    """Причины удержания предмета."""

    # CS2
    RARE_FLOAT = "rare_float"  # Редкий wear/float
    VALUABLE_STICKER = "valuable_sticker"  # Дорогая наклейка
    RARE_PATTERN = "rare_pattern"  # Редкий паттерн (Blue Gem, Fade)
    RARE_PHASE = "rare_phase"  # Редкая фаза (Ruby, Sapphire)

    # Dota 2
    RARE_GEM = "rare_gem"  # Prismatic/Ethereal гем
    MULTI_GEM = "multi_gem"  # Много инскрайбов
    UNLOCKED_STYLES = "unlocked_styles"  # Открытые стили

    # TF2
    HALLOWEEN_SPELL = "halloween_spell"  # Хэллоуинское заклинание
    STRANGE_PARTS = "strange_parts"  # Редкие Strange Parts
    UNUSUAL_EFFECT = "unusual_effect"  # Топовый Unusual эффект

    # Rust
    GLOW_ITEM = "glow_item"  # Светящийся предмет
    LIMITED_EDITION = "limited_edition"  # Лимитированный

    # Generic
    MANUAL_REVIEW = "manual_review"  # Требуется ручная проверка
    JACKPOT = "jackpot"  # Джекпот находка


class ItemStatus(StrEnum):
    """Статус предмета в системе."""

    PENDING = "pending"  # Ожидает обработки
    FOR_SALE = "for_sale"  # Выставлен на продажу
    HOLD_RARE = "hold_rare"  # Удержан как редкий
    SOLD = "sold"  # Продан


@dataclass
class HoldDecision:
    """Решение об удержании предмета."""

    item_id: str
    title: str
    game: str
    should_hold: bool
    reason: HoldReason | None = None
    reason_details: str = ""
    estimated_value_multiplier: float = 1.0  # Во сколько раз дороже обычного
    recommended_platforms: list[str] = field(default_factory=list)
    evaluation_result: EvaluationResult | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Преобразовать в словарь."""
        return {
            "item_id": self.item_id,
            "title": self.title,
            "game": self.game,
            "should_hold": self.should_hold,
            "reason": self.reason,
            "reason_details": self.reason_details,
            "estimated_value_multiplier": self.estimated_value_multiplier,
            "recommended_platforms": self.recommended_platforms,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class CollectorsHoldConfig:
    """Конфигурация Collector's Hold."""

    # Минимальные пороги для удержания
    min_value_multiplier: float = 1.20  # Мин. +20% для удержания
    min_float_for_hold: float = 0.01  # Float < 0.01 = hold
    max_float_for_hold: float = 0.99  # Float > 0.99 = hold (Battle-Scarred rare)

    # Стикеры (CS2)
    always_hold_sticker_collections: list[str] = field(
        default_factory=lambda: [
            "Katowice 2014",
            "Katowice 2015",
            "Cologne 2014",
            "DreamHack 2014",
        ]
    )
    always_hold_sticker_names: list[str] = field(
        default_factory=lambda: [
            "iBUYPOWER (Holo)",
            "Titan (Holo)",
            "Crown (Foil)",
            "King on the Field",
            "Reason Gaming (Holo)",
            "Vox Eminor (Holo)",
            "Dignitas (Holo)",
            "Natus Vincere (Holo) | Katowice 2014",
            "LGB eSports (Holo) | Katowice 2014",
            "mousesports (Holo) | Katowice 2014",
        ]
    )

    # Фазы Doppler (CS2)
    always_hold_phases: list[str] = field(
        default_factory=lambda: [
            "Ruby",
            "Sapphire",
            "Emerald",
            "Black Pearl",
        ]
    )

    # Паттерны (CS2)
    blue_gem_patterns: list[int] = field(
        default_factory=lambda: [661, 387, 321, 955, 670, 179, 695, 868, 592, 442]
    )

    # Гемы (Dota 2)
    always_hold_gem_types: list[str] = field(default_factory=lambda: ["Prismatic", "Ethereal"])
    rare_prismatic_colors: list[str] = field(
        default_factory=lambda: [
            "Creator's Light",
            "Ethereal Flame",
            "Bleak Hallucination",
            "Reflections of the Eternal Darkness",
            "Diretide Shimmer",
        ]
    )

    # Unusual эффекты (TF2)
    tier1_unusual_effects: list[str] = field(
        default_factory=lambda: [
            "Burning Flames",
            "Scorching Flames",
            "Sunbeams",
            "Cloudy Moon",
            "Purple Energy",
            "Green Energy",
        ]
    )

    # Glow items (Rust)
    glow_keywords: list[str] = field(
        default_factory=lambda: [
            "Neon",
            "Glowing",
            "Glow",
            "Alien Red",
            "Glitch",
            "Bioluminescent",
        ]
    )

    # Рекомендуемые площадки
    platforms_by_game: dict[str, list[str]] = field(
        default_factory=lambda: {
            "csgo": ["Buff163", "CSFloat", "Skinport", "SkinBid"],
            "dota2": ["Buff163", "LOOT.Farm", "CS.Money"],
            "tf2": ["Backpack.tf", "Marketplace.tf", "STN Trading"],
            "rust": ["Skinport", "RustySaloon", "Rust Market"],
        }
    )


class CollectorsHoldManager:
    """Менеджер удержания редких предметов.

    Анализирует купленные предметы и решает:
    - Выставить на продажу (обычный арбитраж)
    - Удержать в инвентаре (редкость, требует ручной продажи)
    """

    def __init__(
        self,
        db: TradingPersistence | None = None,
        evaluator: ItemValueEvaluator | None = None,
        config: CollectorsHoldConfig | None = None,
    ) -> None:
        """Инициализация менеджера.

        Args:
            db: База данных для сохранения решений
            evaluator: Оценщик ценности предметов
            config: Конфигурация (опционально)
        """
        self.db = db
        self.evaluator = evaluator
        self.config = config or CollectorsHoldConfig()

        # Статистика
        self._total_processed = 0
        self._total_held = 0
        self._treasures: list[HoldDecision] = []

        logger.info("CollectorsHoldManager initialized")

    async def process_purchased_item(
        self,
        item_data: dict[str, Any],
    ) -> HoldDecision:
        """Обработать купленный предмет.

        Args:
            item_data: Данные о предмете

        Returns:
            HoldDecision с решением
        """
        self._total_processed += 1

        item_id = item_data.get("itemId") or item_data.get("asset_id", "")
        title = item_data.get("title", "Unknown")
        game = item_data.get("gameId") or item_data.get("game", "csgo")

        logger.debug(f"Processing item: {title} ({game})")

        # 1. Используем ItemValueEvaluator если доступен
        evaluation = None
        if self.evaluator:
            evaluation = self.evaluator.evaluate(item_data)

            # Если требуется ручная проверка - сразу hold
            if evaluation.requires_manual_review:
                decision = HoldDecision(
                    item_id=item_id,
                    title=title,
                    game=game,
                    should_hold=True,
                    reason=HoldReason.JACKPOT,
                    reason_details=", ".join(evaluation.detected_attributes),
                    estimated_value_multiplier=evaluation.value_multiplier,
                    recommended_platforms=self.config.platforms_by_game.get(game, []),
                    evaluation_result=evaluation,
                )
                await self._save_treasure(decision)
                return decision

        # 2. Дополнительные проверки по игре
        hold_reason, details, multiplier = self._check_game_specific(item_data, game, evaluation)

        if hold_reason:
            decision = HoldDecision(
                item_id=item_id,
                title=title,
                game=game,
                should_hold=True,
                reason=hold_reason,
                reason_details=details,
                estimated_value_multiplier=multiplier,
                recommended_platforms=self.config.platforms_by_game.get(game, []),
                evaluation_result=evaluation,
            )
            await self._save_treasure(decision)
            return decision

        # 3. Проверяем value_multiplier
        if evaluation and evaluation.value_multiplier >= self.config.min_value_multiplier:
            decision = HoldDecision(
                item_id=item_id,
                title=title,
                game=game,
                should_hold=True,
                reason=HoldReason.MANUAL_REVIEW,
                reason_details=f"Value multiplier: {evaluation.value_multiplier:.2f}x",
                estimated_value_multiplier=evaluation.value_multiplier,
                recommended_platforms=self.config.platforms_by_game.get(game, []),
                evaluation_result=evaluation,
            )
            await self._save_treasure(decision)
            return decision

        # Не редкий - выставляем на продажу
        return HoldDecision(
            item_id=item_id,
            title=title,
            game=game,
            should_hold=False,
            evaluation_result=evaluation,
        )

    def _check_game_specific(
        self,
        item_data: dict[str, Any],
        game: str,
        evaluation: EvaluationResult | None,
    ) -> tuple[HoldReason | None, str, float]:
        """Проверить специфичные для игры триггеры.

        Returns:
            Tuple of (reason, details, multiplier) or (None, "", 1.0)
        """
        if game in {"csgo", "cs2"}:
            return self._check_cs2_triggers(item_data, evaluation)
        if game == "dota2":
            return self._check_dota2_triggers(item_data, evaluation)
        if game == "tf2":
            return self._check_tf2_triggers(item_data, evaluation)
        if game == "rust":
            return self._check_rust_triggers(item_data)

        return None, "", 1.0

    def _check_cs2_triggers(
        self,
        item_data: dict[str, Any],
        evaluation: EvaluationResult | None,
    ) -> tuple[HoldReason | None, str, float]:
        """Проверить триггеры CS2."""
        extra = item_data.get("extra", {})

        # 1. Float
        float_val = extra.get("floatValue") or extra.get("float", 1.0)
        if float_val < self.config.min_float_for_hold:
            return HoldReason.RARE_FLOAT, f"Low float: {float_val:.6f}", 1.30
        if float_val > self.config.max_float_for_hold:
            return HoldReason.RARE_FLOAT, f"Max float: {float_val:.6f}", 1.15

        # 2. Стикеры
        stickers = extra.get("stickers", [])
        for sticker in stickers:
            sticker_name = sticker.get("name", "")

            # Проверяем конкретные имена
            for rare_name in self.config.always_hold_sticker_names:
                if rare_name.lower() in sticker_name.lower():
                    return HoldReason.VALUABLE_STICKER, f"Rare sticker: {sticker_name}", 2.0

            # Проверяем коллекции
            for collection in self.config.always_hold_sticker_collections:
                if collection.lower() in sticker_name.lower():
                    if "holo" in sticker_name.lower():
                        return HoldReason.VALUABLE_STICKER, f"Holo from {collection}", 1.50
                    if "foil" in sticker_name.lower():
                        return HoldReason.VALUABLE_STICKER, f"Foil from {collection}", 1.25

        # 3. Фаза Doppler
        phase = extra.get("phase", "")
        if phase in self.config.always_hold_phases:
            return HoldReason.RARE_PHASE, f"Rare phase: {phase}", 1.50

        # 4. Blue Gem паттерн
        paint_seed = extra.get("paintSeed") or extra.get("pattern_id")
        if paint_seed and int(paint_seed) in self.config.blue_gem_patterns:
            title = item_data.get("title", "")
            if "case hardened" in title.lower():
                return HoldReason.RARE_PATTERN, f"Blue Gem pattern: {paint_seed}", 2.0

        return None, "", 1.0

    def _check_dota2_triggers(
        self,
        item_data: dict[str, Any],
        evaluation: EvaluationResult | None,
    ) -> tuple[HoldReason | None, str, float]:
        """Проверить триггеры Dota 2."""
        extra = item_data.get("extra", {})

        # 1. Гемы
        gems = extra.get("gems", [])
        for gem in gems:
            gem_name = gem.get("name", "")
            gem_type = gem.get("type", "")

            # Редкие типы гемов
            if gem_type in self.config.always_hold_gem_types:
                return HoldReason.RARE_GEM, f"Rare gem: {gem_name} ({gem_type})", 1.30

            # Редкие цвета Prismatic
            for rare_color in self.config.rare_prismatic_colors:
                if rare_color.lower() in gem_name.lower():
                    return HoldReason.RARE_GEM, f"Rare Prismatic: {gem_name}", 1.50

        # 2. Много гемов
        gems_count = extra.get("gemsCount") or len(gems)
        if gems_count >= 3:
            return HoldReason.MULTI_GEM, f"Multi-gem item ({gems_count} gems)", 1.15

        # 3. Открытые стили
        unlocked_styles = extra.get("unlockedStyles", 0)
        if unlocked_styles >= 2:
            return HoldReason.UNLOCKED_STYLES, f"{unlocked_styles} styles unlocked", 1.10

        return None, "", 1.0

    def _check_tf2_triggers(
        self,
        item_data: dict[str, Any],
        evaluation: EvaluationResult | None,
    ) -> tuple[HoldReason | None, str, float]:
        """Проверить триггеры TF2."""
        extra = item_data.get("extra", {})
        # title extracted but currently using extra for spell detection
        _title = item_data.get("title", "")  # noqa: F841

        # 1. Halloween Spells
        spells = extra.get("spells", [])
        if spells:
            spell_names = [s.get("name", "") for s in spells]
            return HoldReason.HALLOWEEN_SPELL, f"Spells: {', '.join(spell_names)}", 1.50

        # Проверяем атрибуты
        attributes = str(extra.get("attributes", ""))
        if "spell" in attributes.lower():
            return HoldReason.HALLOWEEN_SPELL, "Halloween Spell detected", 1.40

        # 2. Unusual эффекты
        effect = extra.get("effect", "")
        if effect in self.config.tier1_unusual_effects:
            return HoldReason.UNUSUAL_EFFECT, f"Tier 1 effect: {effect}", 1.30

        # 3. Strange Parts
        parts = extra.get("parts", [])
        if len(parts) >= 2:
            part_names = [p.get("name", "") for p in parts]
            return HoldReason.STRANGE_PARTS, f"Parts: {', '.join(part_names)}", 1.15

        return None, "", 1.0

    def _check_rust_triggers(
        self,
        item_data: dict[str, Any],
    ) -> tuple[HoldReason | None, str, float]:
        """Проверить триггеры Rust."""
        title = item_data.get("title", "")

        # 1. Glow items
        for keyword in self.config.glow_keywords:
            if keyword.lower() in title.lower():
                return HoldReason.GLOW_ITEM, f"Glow item: {keyword}", 1.20

        # 2. Limited Edition
        if "limited" in title.lower() or "exclusive" in title.lower():
            return HoldReason.LIMITED_EDITION, "Limited Edition item", 1.25

        return None, "", 1.0

    async def _save_treasure(self, decision: HoldDecision) -> None:
        """Сохранить решение о сокровище."""
        self._total_held += 1
        self._treasures.append(decision)

        logger.info(
            f"💎 TREASURE FOUND: {decision.title} "
            f"(reason: {decision.reason}, multiplier: {decision.estimated_value_multiplier:.2f}x)"
        )

        # Сохраняем в БД если доступна
        if self.db:
            try:
                await self.db.update_item_status(
                    decision.item_id,
                    ItemStatus.HOLD_RARE,
                    metadata={
                        "hold_reason": decision.reason,
                        "reason_details": decision.reason_details,
                        "estimated_multiplier": decision.estimated_value_multiplier,
                        "recommended_platforms": decision.recommended_platforms,
                    },
                )
            except Exception as e:
                logger.exception(f"Failed to save treasure to DB: {e}")

    def get_treasures(self) -> list[HoldDecision]:
        """Получить список всех сокровищ."""
        return self._treasures.copy()

    def get_statistics(self) -> dict[str, Any]:
        """Получить статистику."""
        return {
            "total_processed": self._total_processed,
            "total_held": self._total_held,
            "hold_rate_percent": (
                (self._total_held / self._total_processed * 100) if self._total_processed > 0 else 0
            ),
            "treasures_by_reason": self._count_by_reason(),
        }

    def _count_by_reason(self) -> dict[str, int]:
        """Подсчитать сокровища по причинам."""
        counts: dict[str, int] = {}
        for treasure in self._treasures:
            reason = treasure.reason or "unknown"
            counts[reason] = counts.get(reason, 0) + 1
        return counts

    def format_treasure_notification(self, decision: HoldDecision) -> str:
        """Форматировать уведомление о сокровище.

        Args:
            decision: Решение об удержании

        Returns:
            Текст для Telegram
        """
        emoji = "💎" if decision.estimated_value_multiplier >= 1.5 else "✨"

        lines = [
            f"{emoji} **СОКРОВИЩЕ НАЙДЕНО!** {emoji}",
            "",
            f"📦 **Предмет:** {decision.title}",
            f"🎮 **Игра:** {decision.game.upper()}",
            f"💰 **Оценочный множитель:** {decision.estimated_value_multiplier:.2f}x",
            "",
            "📝 **Причина удержания:**",
            f"{decision.reason_details}",
            "",
            "🏪 **Рекомендуемые площадки для продажи:**",
        ]

        for platform in decision.recommended_platforms[:3]:
            lines.append(f"  • {platform}")

        lines.extend([
            "",
            "⚠️ Бот НЕ выставил этот предмет на DMarket.",
            "Продайте его вручную на специализированных площадках.",
        ])

        return "\n".join(lines)


# Глобальный экземпляр
_manager: CollectorsHoldManager | None = None


def get_collectors_hold_manager() -> CollectorsHoldManager:
    """Получить глобальный экземпляр менеджера."""
    global _manager
    if _manager is None:
        _manager = CollectorsHoldManager()
    return _manager
