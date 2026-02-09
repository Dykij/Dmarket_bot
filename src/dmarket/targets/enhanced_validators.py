"""Валидаторы для расширенной системы таргетов.

Этот модуль содержит функции для валидации таргетов перед отправкой в DMarket API:
- Проверка количества условий (DMarket лимит: обычно 10)
- Валидация цен и атрибутов
- Проверка совместимости фильтров с игрой
- Проверка на дубликаты ордеров

Документация: docs/DMARKET_API_FULL_SPEC.md
API Limitations: Макс 100 таргетов в запросе, Amount до 100
"""

import logging
from typing import Any

from src.dmarket.models.target_enhancements import (
    RarityFilter,
    StickerFilter,
    TargetErrorCode,
    TargetOperationResult,
    TargetOperationStatus,
)

logger = logging.getLogger(__name__)


# ==================== CONDITION COUNTING ====================


def count_target_conditions(target: dict[str, Any]) -> int:
    """Подсчитать количество условий в таргете.

    DMarket API ограничивает количество фильтров/условий в одном ордере
    (обычно до 10-15 условий).

    Args:
        target: Словарь с данными таргета (включая фильтры)

    Returns:
        Количество условий

    Пример:
        >>> target = {
        ...     "Attrs": {"floatPartValue": "0.15", "paintSeed": 123, "phase": "Ruby"},
        ...     "stickerFilter": {...},  # +3 условия
        ... }
        >>> count_target_conditions(target)
        6
    """
    count = 0

    # Базовые атрибуты
    attrs = target.get("Attrs", {})
    if attrs:
        # Float value (мин/макс = 2 условия, или просто значение = 1)
        if "floatPartValue" in attrs:
            count += 1
        if "floatMin" in attrs:
            count += 1
        if "floatMax" in attrs:
            count += 1

        # Paint seed (каждое значение = 1 условие)
        if "paintSeed" in attrs:
            paint_seed = attrs["paintSeed"]
            if isinstance(paint_seed, list):
                count += len(paint_seed)
            else:
                count += 1

        # Phase
        if "phase" in attrs:
            count += 1

        # Exterior
        if "exterior" in attrs:
            count += 1

    # Фильтр по стикерам
    sticker_filter = target.get("stickerFilter")
    if sticker_filter:
        if isinstance(sticker_filter, dict):
            sticker_obj = StickerFilter(**sticker_filter)
            count += sticker_obj.count_conditions()
        elif isinstance(sticker_filter, StickerFilter):
            count += sticker_filter.count_conditions()

    # Фильтр по редкости
    rarity_filter = target.get("rarityFilter")
    if rarity_filter:
        if isinstance(rarity_filter, dict):
            rarity_obj = RarityFilter(**rarity_filter)
            count += rarity_obj.count_conditions()
        elif isinstance(rarity_filter, RarityFilter):
            count += rarity_filter.count_conditions()

    return count


def validate_target_conditions(
    target: dict[str, Any],
    max_conditions: int = 10,
) -> tuple[bool, str, list[str]]:
    """Проверить что количество условий не превышает лимит DMarket API.

    Args:
        target: Данные таргета
        max_conditions: Максимум условий (обычно 10)

    Returns:
        (is_valid, message, suggestions)

    Пример:
        >>> target = {...}  # Таргет с 12 условиями
        >>> is_valid, msg, suggestions = validate_target_conditions(target)
        >>> print(msg)
        "Too many conditions: 12/10. Remove 2 conditions."
        >>> print(suggestions)
        ["Remove some paint seed values", "Simplify sticker filter"]
    """
    count = count_target_conditions(target)

    if count <= max_conditions:
        return True, f"Valid: {count}/{max_conditions} conditions", []

    # Превышен лимит - формируем suggestions
    excess = count - max_conditions
    message = f"Too many conditions: {count}/{max_conditions}. Remove {excess} condition(s)."

    suggestions = []
    attrs = target.get("Attrs", {})

    # Анализируем что можно упростить
    if "paintSeed" in attrs and isinstance(attrs["paintSeed"], list):
        paint_count = len(attrs["paintSeed"])
        if paint_count > 2:
            suggestions.append(f"Remove some paint seed values (currently {paint_count})")

    sticker_filter = target.get("stickerFilter")
    if sticker_filter:
        if isinstance(sticker_filter, dict):
            sticker_obj = StickerFilter(**sticker_filter)
        else:
            sticker_obj = sticker_filter

        sticker_conditions = sticker_obj.count_conditions()
        if sticker_conditions > 3:
            suggestions.append(
                f"Simplify sticker filter (currently {sticker_conditions} conditions)"
            )

    if "floatMin" in attrs and "floatMax" in attrs and "floatPartValue" in attrs:
        suggestions.append("Use either floatPartValue OR floatMin/floatMax, not both")

    if not suggestions:
        suggestions.append("Simplify filters to meet DMarket API limits")

    return False, message, suggestions


# ==================== PRICE VALIDATION ====================


def validate_target_price(
    price: float,
    min_price: float = 0.01,
    max_price: float = 100000.0,
) -> TargetOperationResult:
    """Валидация цены таргета.

    Args:
        price: Цена в USD
        min_price: Минимальная цена
        max_price: Максимальная цена

    Returns:
        Результат валидации

    Примеры:
        >>> result = validate_target_price(4.50, min_price=5.00)
        >>> print(result.reason)
        "Price $4.50 is below minimum $5.00"
    """
    if price <= 0:
        return TargetOperationResult(
            success=False,
            status=TargetOperationStatus.FAILED,
            message="Invalid price",
            reason=f"Price must be positive, got ${price:.2f}",
            error_code=TargetErrorCode.PRICE_TOO_LOW,
            suggestions=["Set a positive price value"],
        )

    if price < min_price:
        return TargetOperationResult(
            success=False,
            status=TargetOperationStatus.FAILED,
            message="Price too low",
            reason=f"Price ${price:.2f} is below minimum ${min_price:.2f}",
            error_code=TargetErrorCode.PRICE_TOO_LOW,
            suggestions=[
                f"Set price to at least ${min_price:.2f}",
                "Check current market prices",
            ],
        )

    if price > max_price:
        return TargetOperationResult(
            success=False,
            status=TargetOperationStatus.FAILED,
            message="Price too high",
            reason=f"Price ${price:.2f} exceeds maximum ${max_price:.2f}",
            error_code=TargetErrorCode.PRICE_TOO_HIGH,
            suggestions=[
                f"Set price below ${max_price:.2f}",
                "Verify if this price is intentional",
            ],
        )

    return TargetOperationResult(
        success=True,
        status=TargetOperationStatus.SUCCESS,
        message="Price is valid",
        reason=f"Price ${price:.2f} is within acceptable range",
    )


# ==================== ATTRIBUTE VALIDATION ====================


def validate_target_attributes(
    game: str,
    attrs: dict[str, Any] | None,
) -> TargetOperationResult:
    """Валидация атрибутов таргета в зависимости от игры.

    Args:
        game: Код игры (csgo, dota2, tf2, rust)
        attrs: Атрибуты таргета

    Returns:
        Результат валидации

    Примеры:
        >>> # CS:GO - float допустим
        >>> result = validate_target_attributes("csgo", {"floatPartValue": "0.15"})
        >>> result.success
        True
        >>>
        >>> # Dota 2 - float недопустим
        >>> result = validate_target_attributes("dota2", {"floatPartValue": "0.15"})
        >>> result.success
        False
    """
    if not attrs:
        return TargetOperationResult(
            success=True,
            status=TargetOperationStatus.SUCCESS,
            message="No attributes to validate",
        )

    game = game.lower()

    # CS:GO специфичные атрибуты
    if game == "csgo":
        # Float value
        float_value = attrs.get("floatPartValue")
        if float_value is not None:
            try:
                float_val = float(float_value)
                if not 0 <= float_val <= 1:
                    return TargetOperationResult(
                        success=False,
                        status=TargetOperationStatus.FAILED,
                        message="Invalid float value",
                        reason=f"Float value {float_val} must be between 0 and 1",
                        error_code=TargetErrorCode.INVALID_ATTRIBUTES,
                        suggestions=["Set float value between 0.00 and 1.00"],
                    )
            except (ValueError, TypeError) as e:
                return TargetOperationResult(
                    success=False,
                    status=TargetOperationStatus.FAILED,
                    message="Invalid float format",
                    reason=f"Cannot parse float value: {e}",
                    error_code=TargetErrorCode.INVALID_ATTRIBUTES,
                )

        # Paint seed
        paint_seed = attrs.get("paintSeed")
        if paint_seed is not None:
            if isinstance(paint_seed, list):
                for seed in paint_seed:
                    if not isinstance(seed, int) or seed < 0 or seed > 1000:
                        return TargetOperationResult(
                            success=False,
                            status=TargetOperationStatus.FAILED,
                            message="Invalid paint seed",
                            reason=f"Paint seed {seed} must be 0-1000",
                            error_code=TargetErrorCode.INVALID_ATTRIBUTES,
                        )
            elif not isinstance(paint_seed, int) or paint_seed < 0 or paint_seed > 1000:
                return TargetOperationResult(
                    success=False,
                    status=TargetOperationStatus.FAILED,
                    message="Invalid paint seed",
                    reason=f"Paint seed must be integer 0-1000, got {paint_seed}",
                    error_code=TargetErrorCode.INVALID_ATTRIBUTES,
                )

    # Dota 2 / TF2 - float не применим
    elif game in {"dota2", "tf2"}:
        if "floatPartValue" in attrs:
            return TargetOperationResult(
                success=False,
                status=TargetOperationStatus.FAILED,
                message="Invalid attribute for game",
                reason=f"Float value is not applicable for {game.upper()}",
                error_code=TargetErrorCode.INVALID_ATTRIBUTES,
                suggestions=[
                    "Remove floatPartValue attribute",
                    "Use rarity or quality attributes instead",
                ],
            )

    return TargetOperationResult(
        success=True,
        status=TargetOperationStatus.SUCCESS,
        message="Attributes are valid",
        reason=f"All attributes are valid for {game.upper()}",
    )


# ==================== FILTER COMPATIBILITY ====================


def validate_filter_compatibility(
    game: str,
    sticker_filter: StickerFilter | None = None,
    rarity_filter: RarityFilter | None = None,
) -> TargetOperationResult:
    """Проверить совместимость фильтров с игрой.

    Args:
        game: Код игры
        sticker_filter: Фильтр по стикерам (только для CS:GO)
        rarity_filter: Фильтр по редкости (только для Dota 2, TF2)

    Returns:
        Результат валидации

    Примеры:
        >>> # CS:GO + sticker filter = OK
        >>> result = validate_filter_compatibility("csgo", sticker_filter=StickerFilter(...))
        >>> result.success
        True
        >>>
        >>> # Dota 2 + sticker filter = ERROR
        >>> result = validate_filter_compatibility("dota2", sticker_filter=StickerFilter(...))
        >>> result.success
        False
    """
    game = game.lower()

    # Стикеры только для CS:GO
    if sticker_filter and game != "csgo":
        return TargetOperationResult(
            success=False,
            status=TargetOperationStatus.FAILED,
            message="Invalid filter for game",
            reason=f"Sticker filters are only applicable for CS:GO, not {game.upper()}",
            error_code=TargetErrorCode.INVALID_ATTRIBUTES,
            suggestions=[
                "Remove sticker filter",
                "Use rarity filter for Dota 2/TF2 instead",
            ],
        )

    # Rarity для Dota 2 / TF2
    if rarity_filter and game not in {"dota2", "tf2"}:
        return TargetOperationResult(
            success=False,
            status=TargetOperationStatus.FAILED,
            message="Invalid filter for game",
            reason=f"Rarity filters are for Dota 2/TF2, not {game.upper()}",
            error_code=TargetErrorCode.INVALID_ATTRIBUTES,
            suggestions=[
                "Remove rarity filter",
                "Use sticker filter for CS:GO or exterior/float filters",
            ],
        )

    return TargetOperationResult(
        success=True,
        status=TargetOperationStatus.SUCCESS,
        message="Filters are compatible",
        reason=f"All filters are compatible with {game.upper()}",
    )


# ==================== COMPREHENSIVE VALIDATION ====================


def validate_target_complete(
    game: str,
    title: str,
    price: float,
    amount: int = 1,
    attrs: dict[str, Any] | None = None,
    sticker_filter: StickerFilter | None = None,
    rarity_filter: RarityFilter | None = None,
    max_conditions: int = 10,
) -> TargetOperationResult:
    """Полная валидация таргета перед созданием.

    Проверяет все аспекты: цену, атрибуты, фильтры, количество условий.

    Args:
        game: Код игры
        title: Название предмета
        price: Цена в USD
        amount: Количество
        attrs: Атрибуты
        sticker_filter: Фильтр по стикерам
        rarity_filter: Фильтр по редкости
        max_conditions: Макс условий

    Returns:
        Результат валидации со всеми проверками

    Пример:
        >>> result = validate_target_complete(
        ...     game="csgo",
        ...     title="AK-47 | Redline (FT)",
        ...     price=10.50,
        ...     attrs={"floatPartValue": "0.25"},
        ... )
        >>> if not result.success:
        ...     print(result.reason)
        ...     for suggestion in result.suggestions:
        ...         print(f"  - {suggestion}")
    """
    # Проверка названия
    if not title or not title.strip():
        return TargetOperationResult(
            success=False,
            status=TargetOperationStatus.FAILED,
            message="Invalid title",
            reason="Title cannot be empty",
            error_code=TargetErrorCode.INVALID_ATTRIBUTES,
            suggestions=["Provide a valid item title"],
        )

    # Проверка количества
    if amount < 1 or amount > 100:
        return TargetOperationResult(
            success=False,
            status=TargetOperationStatus.FAILED,
            message="Invalid amount",
            reason=f"Amount must be 1-100, got {amount}",
            error_code=TargetErrorCode.INVALID_ATTRIBUTES,
            suggestions=["Set amount between 1 and 100"],
        )

    # Проверка цены
    price_result = validate_target_price(price)
    if not price_result.success:
        return price_result

    # Проверка атрибутов
    attrs_result = validate_target_attributes(game, attrs)
    if not attrs_result.success:
        return attrs_result

    # Проверка совместимости фильтров
    filter_result = validate_filter_compatibility(game, sticker_filter, rarity_filter)
    if not filter_result.success:
        return filter_result

    # Проверка количества условий
    target_dict = {
        "Title": title,
        "Amount": str(amount),
        "Price": {"Amount": int(price * 100), "Currency": "USD"},
        "Attrs": attrs or {},
    }
    if sticker_filter:
        target_dict["stickerFilter"] = sticker_filter
    if rarity_filter:
        target_dict["rarityFilter"] = rarity_filter

    is_valid, conditions_msg, suggestions = validate_target_conditions(target_dict, max_conditions)

    if not is_valid:
        return TargetOperationResult(
            success=False,
            status=TargetOperationStatus.FAILED,
            message="Too many conditions",
            reason=conditions_msg,
            error_code=TargetErrorCode.TOO_MANY_CONDITIONS,
            suggestions=suggestions,
        )

    # Все проверки пройдены
    return TargetOperationResult(
        success=True,
        status=TargetOperationStatus.SUCCESS,
        message="Target is valid",
        reason=f"All validations passed. {conditions_msg}",
        metadata={
            "game": game,
            "title": title,
            "price": price,
            "amount": amount,
            "conditions_count": count_target_conditions(target_dict),
        },
    )
