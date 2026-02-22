"""Функции для пакетного создания ордеров и обнаружения существующих.

Этот модуль содержит:
- Создание одного ордера на несколько предметов (batch)
- Обнаружение существующих ордеров пользователя
- Проверка на дубликаты

Документация: docs/DMARKET_API_FULL_SPEC.md
API Endpoint: POST /marketplace-api/v1/user-targets/create
"""

import logging
from typing import TYPE_CHECKING, Any

from src.dmarket.models.target_enhancements import (
    BatchTargetItem,
    ExistingOrderInfo,
    TargetErrorCode,
    TargetOperationResult,
    TargetOperationStatus,
)
from src.dmarket.targets.enhanced_validators import (
    validate_target_attributes,
    validate_target_conditions,
)

if TYPE_CHECKING:
    from src.interfaces import IDMarketAPI


logger = logging.getLogger(__name__)


# ==================== BATCH ORDER CREATION ====================


async def create_batch_target(
    api_client: "IDMarketAPI",
    game: str,
    items: list[BatchTargetItem],
    price: float,
    total_amount: int = 1,
    shared_attrs: dict[str, Any] | None = None,
) -> TargetOperationResult:
    """Создать один ордер на несколько предметов.

    Вместо создания отдельного ордера для каждого предмета,
    создает один составной ордер со списком предметов.

    Args:
        api_client: DMarket API клиент
        game: Код игры (csgo, dota2, tf2, rust)
        items: Список предметов для ордера
        price: Общая цена для всех предметов (USD)
        total_amount: Общее количество (распределяется между предметами)
        shared_attrs: Общие атрибуты для всех предметов

    Returns:
        Результат операции с деталями

    Примеры:
        >>> items = [
        ...     BatchTargetItem(title="AK-47 | Redline (FT)", attrs={"floatPartValue": "0.25"}),
        ...     BatchTargetItem(title="AK-47 | Redline (MW)", attrs={"floatPartValue": "0.12"}),
        ...     BatchTargetItem(title="AK-47 | Redline (FN)", attrs={"floatPartValue": "0.07"}),
        ... ]
        >>> result = await create_batch_target(
        ...     api_client=api,
        ...     game="csgo",
        ...     items=items,
        ...     price=70.80,  # Общая сумма
        ...     total_amount=3,
        ... )
        >>> print(result.message)
        "Batch order created for 3 items"

    Примечания:
        - Экономия API запросов (1 запрос вместо N)
        - Все предметы в одном ордере
        - Цена распределяется по весам (BatchTargetItem.weight)
    """
    if not items:
        return TargetOperationResult(
            success=False,
            status=TargetOperationStatus.FAlgoLED,
            message="No items provided",
            reason="Items list cannot be empty",
            error_code=TargetErrorCode.INVALID_ATTRIBUTES,
            suggestions=["Provide at least one item"],
        )

    if len(items) > 100:
        return TargetOperationResult(
            success=False,
            status=TargetOperationStatus.FAlgoLED,
            message="Too many items",
            reason=f"Maximum 100 items per batch, got {len(items)}",
            error_code=TargetErrorCode.INVALID_ATTRIBUTES,
            suggestions=["Split into multiple batch requests"],
        )

    logger.info(
        f"Creating batch order for {len(items)} items in {game.upper()}, total price ${price:.2f}"
    )

    # Распределить количество между предметами
    total_weight = sum(item.weight for item in items)
    targets_data = []

    for item in items:
        # Рассчитать долю цены и количества для этого предмета
        item_ratio = item.weight / total_weight
        item_amount = max(1, int(total_amount * item_ratio))
        item_price = price * item_ratio

        # Объединить shared_attrs с индивидуальными attrs
        combined_attrs = {**(shared_attrs or {}), **(item.attrs or {})}

        # Валидация атрибутов для этого предмета
        attrs_result = validate_target_attributes(game, combined_attrs)
        if not attrs_result.success:
            return TargetOperationResult(
                success=False,
                status=TargetOperationStatus.FAlgoLED,
                message=f"Invalid attributes for {item.title}",
                reason=attrs_result.reason,
                error_code=TargetErrorCode.INVALID_ATTRIBUTES,
                suggestions=attrs_result.suggestions,
            )

        # Создать таргет
        target = {
            "Title": item.title,
            "Amount": item_amount,
            "Price": {
                "Amount": int(item_price * 100),  # В центах
                "Currency": "USD",
            },
        }

        if combined_attrs:
            target["Attrs"] = combined_attrs

        # Проверить количество условий
        is_valid, msg, suggestions = validate_target_conditions(target)
        if not is_valid:
            return TargetOperationResult(
                success=False,
                status=TargetOperationStatus.FAlgoLED,
                message=f"Too many conditions for {item.title}",
                reason=msg,
                error_code=TargetErrorCode.TOO_MANY_CONDITIONS,
                suggestions=suggestions,
            )

        targets_data.append(target)

    # Отправить batch запрос к API
    try:
        response = await api_client.create_targets(game=game, targets=targets_data)

        result_items = response.get("Result", [])
        success_count = sum(1 for r in result_items if r.get("Status") == "Created")
        failed_count = len(result_items) - success_count

        if success_count == len(items):
            return TargetOperationResult(
                success=True,
                status=TargetOperationStatus.SUCCESS,
                message=f"Batch order created for {success_count} items",
                reason=f"All {success_count} targets created successfully",
                metadata={
                    "total_items": len(items),
                    "success_count": success_count,
                    "total_price": price,
                    "target_ids": [r.get("TargetID") for r in result_items],
                },
            )
        if success_count > 0:
            return TargetOperationResult(
                success=True,
                status=TargetOperationStatus.PARTIAL,
                message=f"Partial success: {success_count}/{len(items)} items",
                reason=f"{success_count} created, {failed_count} failed",
                metadata={
                    "total_items": len(items),
                    "success_count": success_count,
                    "failed_count": failed_count,
                    "results": result_items,
                },
                suggestions=["Check failed items and retry if needed"],
            )
        return TargetOperationResult(
            success=False,
            status=TargetOperationStatus.FAlgoLED,
            message="Batch order failed",
            reason="All targets failed to create",
            error_code=TargetErrorCode.UNKNOWN_ERROR,
            metadata={"results": result_items},
        )

    except Exception as e:
        logger.error(f"Batch order creation failed: {e}", exc_info=True)
        return TargetOperationResult(
            success=False,
            status=TargetOperationStatus.FAlgoLED,
            message="API request failed",
            reason=str(e),
            error_code=TargetErrorCode.UNKNOWN_ERROR,
            suggestions=["Check API connection", "Verify credentials", "Retry later"],
        )


# ==================== EXISTING ORDER DETECTION ====================


async def detect_existing_orders(
    api_client: "IDMarketAPI",
    game: str,
    title: str,
    user_id: str | None = None,
) -> ExistingOrderInfo:
    """Обнаружить существующие ордера для предмета.

    Проверяет:
    1. Есть ли у пользователя активный ордер на этот предмет
    2. Сколько всего ордеров на этот предмет на рынке
    3. Какие цены у конкурентов

    Args:
        api_client: DMarket API клиент
        game: Код игры
        title: Название предмета
        user_id: ID пользователя (опционально)

    Returns:
        Информация о существующих ордерах

    Примеры:
        >>> info = await detect_existing_orders(
        ...     api_client=api, game="csgo", title="AK-47 | Redline (Field-Tested)", user_id="12345"
        ... )
        >>> if info.has_user_order:
        ...     print(f"You already have an order at ${info.user_order['price']}")
        >>> print(f"Total orders: {info.total_orders}")
        >>> print(f"Best price: ${info.best_price}")
    """
    logger.info(f"Checking existing orders for '{title}' in {game.upper()}")

    has_user_order = False
    user_order = None
    total_orders = 0
    best_price = None
    average_price = None
    can_create = True
    reason = "No existing orders found"
    suggestions = []

    try:
        # 1. Получить ордера пользователя (если user_id указан)
        if user_id:
            try:
                user_targets = await api_client.get_user_targets(
                    game=game,
                    status="TargetStatusActive",
                    title=title,
                )

                user_items = user_targets.get("Items", [])
                if user_items:
                    has_user_order = True
                    user_order = user_items[0]  # Первый найденный ордер
                    can_create = False
                    reason = (
                        f"You already have an active order for this item "
                        f"at ${float(user_order.get('Price', {}).get('Amount', 0)) / 100:.2f}"
                    )
                    suggestions.extend(
                        (
                            "Cancel existing order first",
                            "Or increase amount in existing order",
                        )
                    )

            except Exception as e:
                logger.warning(f"Failed to get user targets: {e}")

        # 2. Получить все ордера на рынке для этого предмета
        try:
            market_orders = await api_client.get_targets_by_title(
                game_id=game,
                title=title,
            )

            orders = market_orders.get("orders", [])
            total_orders = len(orders)

            if orders:
                prices = []
                for order in orders:
                    price_str = order.get("price", "0")
                    try:
                        price_val = float(price_str) / 100  # Из центов в доллары
                        prices.append(price_val)
                    except (ValueError, TypeError):
                        continue

                if prices:
                    best_price = max(prices)  # Лучшая (самая высокая) цена
                    average_price = sum(prices) / len(prices)

                    if not has_user_order:
                        reason = f"Found {total_orders} existing order(s). Best price: ${best_price:.2f}"
                        suggestions.extend(
                            (
                                f"Set your price above ${best_price:.2f} for priority",
                                f"Or set ${average_price:.2f} for average position",
                            )
                        )

        except Exception as e:
            logger.warning(f"Failed to get market orders: {e}")

        # 3. Рекомендуемая цена
        recommended_price = None
        if best_price:
            # Рекомендуем на $0.01 выше лучшей цены
            recommended_price = round(best_price + 0.01, 2)

    except Exception as e:
        logger.error(f"Error detecting existing orders: {e}", exc_info=True)
        reason = f"Error checking orders: {e}"
        suggestions.append("Retry the check")

    return ExistingOrderInfo(
        has_user_order=has_user_order,
        user_order=user_order,
        total_orders=total_orders,
        best_price=best_price,
        average_price=average_price,
        can_create=can_create,
        reason=reason,
        suggestions=suggestions,
        recommended_price=recommended_price,
    )


# ==================== DUPLICATE CHECK ====================


async def check_duplicate_order(
    api_client: "IDMarketAPI",
    game: str,
    title: str,
    price: float,
    tolerance: float = 0.01,
) -> tuple[bool, str]:
    """Проверить на дубликаты ордеров с похожей ценой.

    Args:
        api_client: DMarket API клиент
        game: Код игры
        title: Название предмета
        price: Цена нового ордера (USD)
        tolerance: Допустимая разница цены для считания дубликатом (USD)

    Returns:
        (is_duplicate, message)

    Примеры:
        >>> is_dup, msg = await check_duplicate_order(
        ...     api_client=api,
        ...     game="csgo",
        ...     title="AK-47 | Redline (FT)",
        ...     price=10.00,
        ...     tolerance=0.05,  # $0.05 разница
        ... )
        >>> if is_dup:
        ...     print(msg)  # "Similar order exists at $9.97"
    """
    try:
        user_targets = await api_client.get_user_targets(
            game=game,
            status="TargetStatusActive",
            title=title,
        )

        items = user_targets.get("Items", [])
        for item in items:
            existing_price = float(item.get("Price", {}).get("Amount", 0)) / 100

            price_diff = abs(existing_price - price)
            if price_diff <= tolerance:
                return True, (
                    f"Similar order exists at ${existing_price:.2f} (difference: ${price_diff:.2f})"
                )

        return False, "No duplicate orders found"

    except Exception as e:
        logger.exception(f"Error checking duplicates: {e}")
        return False, f"Error checking duplicates: {e}"
