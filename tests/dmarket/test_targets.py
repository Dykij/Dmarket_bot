"""Тесты для модуля targets.

Этот модуль содержит тесты для управления таргетами (buy orders), включая:
- Создание таргетов с разными параметрами
- Получение активных таргетов пользователя
- Удаление таргетов
- Создание умных таргетов
- Получение статистики по таргетам
"""

from unittest.mock import AsyncMock

import pytest

from src.dmarket.targets import TargetManager

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture()
def mock_api_client():
    """Создает мок DMarketAPI клиента."""
    mock_api = AsyncMock()
    mock_api._request = AsyncMock()
    return mock_api


@pytest.fixture()
def sample_target():
    """Создает образец таргета."""
    return {
        "targetId": "target123",
        "title": "AWP | Asiimov (Field-Tested)",
        "price": {"amount": 5000, "currency": "USD"},  # $50 в центах
        "amount": 1,
        "game": "a8db",
        "status": "active",
    }


# ============================================================================
# ТЕСТЫ ИНИЦИАЛИЗАЦИИ
# ============================================================================


def test_target_manager_initialization(mock_api_client):
    """Тест инициализации TargetManager."""
    manager = TargetManager(mock_api_client)

    assert manager.api is mock_api_client


# ============================================================================
# ТЕСТЫ СОЗДАНИЯ ТАРГЕТОВ
# ============================================================================


@pytest.mark.asyncio()
async def test_create_target_success(mock_api_client):
    """Тест успешного создания таргета."""
    # Настройка мока - используем create_target (метод, который вызывает manager)
    mock_api_client.create_target = AsyncMock(
        return_value={"Result": [{"TargetID": "target123", "Status": "Created"}]}
    )

    manager = TargetManager(mock_api_client)

    # Создаем таргет
    result = await manager.create_target(
        game="csgo",
        title="AWP | Asiimov (Field-Tested)",
        price=50.0,
        amount=1,
    )

    # Проверки
    assert result is not None
    assert "Result" in result or "TargetID" in str(result)


@pytest.mark.asyncio()
async def test_create_target_invalid_price(mock_api_client):
    """Тест создания таргета с невалидной ценой."""
    manager = TargetManager(mock_api_client)

    # Попытка создать таргет с отрицательной ценой
    with pytest.raises(ValueError, match="Цена должна быть больше 0"):
        await manager.create_target(
            game="csgo",
            title="AK-47 | Redline",
            price=-10.0,
            amount=1,
        )


@pytest.mark.asyncio()
async def test_create_target_invalid_amount(mock_api_client):
    """Тест создания таргета с невалидным количеством."""
    manager = TargetManager(mock_api_client)

    # Количество больше максимума
    with pytest.raises(ValueError, match="Количество должно быть от 1 до 100"):
        await manager.create_target(
            game="csgo",
            title="AK-47 | Redline",
            price=10.0,
            amount=150,
        )

    # Количество равно 0
    with pytest.raises(ValueError, match="Количество должно быть от 1 до 100"):
        await manager.create_target(
            game="csgo",
            title="AK-47 | Redline",
            price=10.0,
            amount=0,
        )


@pytest.mark.asyncio()
async def test_create_target_empty_title(mock_api_client):
    """Тест создания таргета с пустым названием."""
    manager = TargetManager(mock_api_client)

    # Пустое название
    with pytest.raises(ValueError, match="Название предмета не может быть пустым"):
        await manager.create_target(
            game="csgo",
            title="",
            price=10.0,
            amount=1,
        )


@pytest.mark.asyncio()
async def test_create_target_with_attrs(mock_api_client):
    """Тест создания таргета с дополнительными атрибутами."""
    # Настройка мока
    mock_api_client.create_target = AsyncMock(return_value={"TargetID": "target124"})

    manager = TargetManager(mock_api_client)

    # Создаем таргет с атрибутами
    result = await manager.create_target(
        game="csgo",
        title="M4A4 | Howl (Factory New)",
        price=1500.0,
        amount=1,
        attrs={"float": 0.01, "paintSeed": 123},
    )

    # Проверки
    assert result is not None


# ============================================================================
# ТЕСТЫ ПОЛУЧЕНИЯ ТАРГЕТОВ
# ============================================================================


@pytest.mark.asyncio()
async def test_get_user_targets_success(mock_api_client):
    """Тест успешного получения таргетов пользователя."""
    # Настройка мока - используем lowercase "items" как в реальном API
    mock_api_client.get_user_targets = AsyncMock(
        return_value={
            "items": [
                {
                    "targetId": "target123",
                    "title": "AWP | Asiimov",
                    "price": {"amount": 5000},
                    "amount": 1,
                    "status": "active",
                }
            ]
        }
    )

    manager = TargetManager(mock_api_client)

    # Получаем таргеты с обязательным параметром game
    result = await manager.get_user_targets(game="csgo")

    # Проверки
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["title"] == "AWP | Asiimov"


@pytest.mark.asyncio()
async def test_get_user_targets_empty(mock_api_client):
    """Тест получения таргетов когда их нет."""
    # Настройка мока - пустой результат
    mock_api_client.get_user_targets = AsyncMock(return_value={"items": []})

    manager = TargetManager(mock_api_client)

    # Получаем таргеты
    result = await manager.get_user_targets(game="csgo")

    # Проверки
    assert result == []


@pytest.mark.asyncio()
async def test_get_targets_by_title(mock_api_client):
    """Тест получения таргетов по названию предмета."""
    # Настройка мока - используем get_targets_by_title (специальный метод)
    mock_api_client.get_targets_by_title = AsyncMock(
        return_value={
            "items": [
                {
                    "targetId": "target123",
                    "title": "AWP | Asiimov (Field-Tested)",
                    "price": {"amount": 5000},
                }
            ]
        }
    )

    manager = TargetManager(mock_api_client)

    # Получаем таргеты по названию
    result = await manager.get_targets_by_title(
        game="csgo", title="AWP | Asiimov (Field-Tested)"
    )

    # Проверки
    assert isinstance(result, list)
    assert len(result) == 1


# ============================================================================
# ТЕСТЫ УДАЛЕНИЯ ТАРГЕТОВ
# ============================================================================


@pytest.mark.asyncio()
async def test_delete_target_success(mock_api_client):
    """Тест успешного удаления таргета."""
    # Настройка мока - используем delete_target (singular)
    mock_api_client.delete_target = AsyncMock(return_value={"success": True})

    manager = TargetManager(mock_api_client)

    # Удаляем таргет
    result = await manager.delete_target("target123")

    # Проверки
    assert result is True
    mock_api_client.delete_target.assert_called_once()


@pytest.mark.asyncio()
async def test_delete_target_not_found(mock_api_client):
    """Тест удаления несуществующего таргета."""
    # Настройка мока - delete_target выбрасывает ошибку
    mock_api_client.delete_target = AsyncMock(side_effect=Exception("Target not found"))

    manager = TargetManager(mock_api_client)

    # Удаляем таргет
    result = await manager.delete_target("target999")

    # Проверки - должен вернуть False при ошибке
    assert result is False


@pytest.mark.asyncio()
async def test_delete_all_targets(mock_api_client):
    """Тест удаления всех таргетов."""
    # Настройка моков - используем lowercase keys
    mock_api_client.get_user_targets = AsyncMock(
        return_value={
            "items": [
                {"targetId": "target123", "title": "AWP", "price": {"amount": 5000}}
            ]
        }
    )
    mock_api_client.delete_target = AsyncMock(return_value={"success": True})

    manager = TargetManager(mock_api_client)

    # Удаляем все таргеты с dry_run=False
    result = await manager.delete_all_targets(game="csgo", dry_run=False)

    # Проверки - результат должен быть словарём
    assert result is not None
    assert isinstance(result, dict)


# ============================================================================
# ТЕСТЫ СТАТИСТИКИ И АНАЛИЗА
# ============================================================================


@pytest.mark.asyncio()
async def test_get_target_statistics(mock_api_client):
    """Тест получения статистики по таргетам."""
    # Настройка моков - используем lowercase keys
    mock_api_client.get_user_targets = AsyncMock(return_value={"items": []})

    manager = TargetManager(mock_api_client)

    # Получаем статистику с обязательным параметром game
    stats = await manager.get_target_statistics(game="csgo")

    # Проверки - проверяем ключи, которые действительно возвращаются
    assert "active_count" in stats
    assert "total_spent" in stats  # Правильный ключ
    assert stats["active_count"] >= 0


@pytest.mark.asyncio()
async def test_get_closed_targets(mock_api_client):
    """Тест получения закрытых (исполненных) таргетов."""
    # Настройка мока - используем lowercase keys
    mock_api_client.get_user_targets = AsyncMock(return_value={"items": []})

    manager = TargetManager(mock_api_client)

    # Получаем закрытые таргеты
    result = await manager.get_closed_targets()

    # Проверки
    assert isinstance(result, list)


# ============================================================================
# ТЕСТЫ УМНОГО СОЗДАНИЯ ТАРГЕТОВ
# ============================================================================


@pytest.mark.asyncio()
async def test_create_smart_targets_basic(mock_api_client):
    """Тест создания умных таргетов - упрощенный."""
    manager = TargetManager(mock_api_client)

    # Тестируем, что метод существует и может быть вызван
    items = []
    result = await manager.create_smart_targets(game="csgo", items=items)

    # Проверки - метод возвращает список результатов
    assert isinstance(result, (dict, list))
