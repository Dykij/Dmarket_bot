"""Тесты для модуля отслеживания цен в реальном времени.

Модуль тестирует функциональность RealtimePriceWatcher и PriceAlert
для отслеживания изменений цен на DMarket через WebSocket и REST API.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.dmarket.realtime_price_watcher import PriceAlert, RealtimePriceWatcher

# ==================== Фикстуры ====================


@pytest.fixture()
def mock_api_client():
    """Мок DMarket API клиента."""
    client = MagicMock()
    client._request = AsyncMock()
    return client


@pytest.fixture()
def mock_websocket_client():
    """Мок WebSocket клиента."""
    client = MagicMock()
    client.connect = AsyncMock(return_value=True)
    client.close = AsyncMock()
    client.listen = AsyncMock()
    client.subscribe_to_item_updates = AsyncMock(return_value=True)
    client.subscribe_to_market_updates = AsyncMock(return_value=True)
    client.register_handler = MagicMock()
    return client


@pytest.fixture()
def price_watcher(mock_api_client, mock_websocket_client):
    """Экземпляр RealtimePriceWatcher с моками."""
    with patch(
        "src.dmarket.realtime_price_watcher.DMarketWebSocketClient",
        return_value=mock_websocket_client,
    ):
        return RealtimePriceWatcher(mock_api_client)


@pytest.fixture()
def sample_price_alert():
    """Пример оповещения о цене."""
    return PriceAlert(
        item_id="item_123",
        market_hash_name="AK-47 | Redline (Field-Tested)",
        target_price=10.0,
        condition="below",
        game="csgo",
    )


# ==================== Тесты PriceAlert ====================


def test_price_alert_initialization(sample_price_alert):
    """Тест инициализации оповещения о цене."""
    assert sample_price_alert.item_id == "item_123"
    assert sample_price_alert.market_hash_name == "AK-47 | Redline (Field-Tested)"
    assert sample_price_alert.target_price == 10.0
    assert sample_price_alert.condition == "below"
    assert sample_price_alert.game == "csgo"
    assert sample_price_alert.is_triggered is False
    assert sample_price_alert.triggered_at is None
    assert sample_price_alert.created_at > 0


def test_price_alert_check_condition_below_true():
    """Тест проверки условия 'below' - должно сработать."""
    alert = PriceAlert(
        item_id="test",
        market_hash_name="Test Item",
        target_price=10.0,
        condition="below",
    )

    # Цена ниже целевой - должно сработать
    assert alert.check_condition(9.5) is True
    assert alert.triggered_at is not None


def test_price_alert_check_condition_below_false():
    """Тест проверки условия 'below' - не должно сработать."""
    alert = PriceAlert(
        item_id="test",
        market_hash_name="Test Item",
        target_price=10.0,
        condition="below",
    )

    # Цена выше целевой - не должно сработать
    assert alert.check_condition(10.5) is False
    assert alert.triggered_at is None


def test_price_alert_check_condition_above_true():
    """Тест проверки условия 'above' - должно сработать."""
    alert = PriceAlert(
        item_id="test",
        market_hash_name="Test Item",
        target_price=10.0,
        condition="above",
    )

    # Цена выше целевой - должно сработать
    assert alert.check_condition(10.5) is True
    assert alert.triggered_at is not None


def test_price_alert_check_condition_above_false():
    """Тест проверки условия 'above' - не должно сработать."""
    alert = PriceAlert(
        item_id="test",
        market_hash_name="Test Item",
        target_price=10.0,
        condition="above",
    )

    # Цена ниже целевой - не должно сработать
    assert alert.check_condition(9.5) is False
    assert alert.triggered_at is None


def test_price_alert_check_condition_equal():
    """Тест проверки условия при равной цене."""
    alert_below = PriceAlert(
        item_id="test",
        market_hash_name="Test Item",
        target_price=10.0,
        condition="below",
    )
    alert_above = PriceAlert(
        item_id="test",
        market_hash_name="Test Item",
        target_price=10.0,
        condition="above",
    )

    # При равной цене 'below' должно сработать
    assert alert_below.check_condition(10.0) is True

    # При равной цене 'above' должно сработать
    assert alert_above.check_condition(10.0) is True


def test_price_alert_reset():
    """Тест сброса состояния оповещения."""
    alert = PriceAlert(
        item_id="test",
        market_hash_name="Test Item",
        target_price=10.0,
        condition="below",
    )

    # Срабатываем оповещение
    result = alert.check_condition(9.0)
    assert result is True
    assert alert.triggered_at is not None

    # Сбрасываем
    alert.reset()
    assert alert.is_triggered is False
    assert alert.triggered_at is None


def test_price_alert_multiple_checks_after_trigger():
    """Тест повторных проверок после срабатывания."""
    alert = PriceAlert(
        item_id="test",
        market_hash_name="Test Item",
        target_price=10.0,
        condition="below",
    )

    # Первая проверка - срабатывает
    first_time = alert.check_condition(9.0)
    first_triggered_at = alert.triggered_at

    # Вторая проверка - условие все еще истинно
    time.sleep(0.01)
    second_time = alert.check_condition(8.0)
    second_triggered_at = alert.triggered_at

    assert first_time is True
    assert second_time is True
    # Время срабатывания будет обновлено
    assert first_triggered_at is not None
    assert second_triggered_at is not None
    assert second_triggered_at >= first_triggered_at


# ==================== Тесты RealtimePriceWatcher - Инициализация ====================


def test_watcher_initialization(price_watcher, mock_api_client):
    """Тест инициализации наблюдателя за ценами."""
    assert price_watcher.api_client == mock_api_client
    assert price_watcher.websocket_client is not None
    assert price_watcher.price_cache == {}
    assert len(price_watcher.price_history) == 0
    assert len(price_watcher.price_alerts) == 0
    assert len(price_watcher.price_change_handlers) == 0
    assert price_watcher.alert_handlers == []
    assert len(price_watcher.watched_items) == 0
    assert price_watcher.item_metadata == {}
    assert price_watcher.is_running is False
    assert price_watcher.max_history_points == 100
    assert price_watcher.price_update_interval == 300


# ==================== Тесты RealtimePriceWatcher - Start/Stop ====================


@pytest.mark.asyncio()
async def test_watcher_start_success(price_watcher, mock_websocket_client):
    """Тест успешного запуска наблюдателя."""
    with patch("asyncio.create_task") as mock_create_task:
        result = await price_watcher.start()

        assert result is True
        assert price_watcher.is_running is True

        # Проверяем регистрацию обработчиков
        assert mock_websocket_client.register_handler.call_count == 2
        calls = mock_websocket_client.register_handler.call_args_list
        assert calls[0][0][0] == "market:update"
        assert calls[1][0][0] == "items:update"

        # Проверяем подключение к WebSocket
        mock_websocket_client.connect.assert_called_once()

        # Проверяем создание задач
        assert mock_create_task.call_count == 2


@pytest.mark.asyncio()
async def test_watcher_start_already_running(price_watcher):
    """Тест запуска уже работающего наблюдателя."""
    price_watcher.is_running = True

    result = await price_watcher.start()

    assert result is True
    # WebSocket connect не должен вызываться
    price_watcher.websocket_client.connect.assert_not_called()


@pytest.mark.asyncio()
async def test_watcher_start_connection_failed(price_watcher, mock_websocket_client):
    """Тест неудачного подключения к WebSocket."""
    mock_websocket_client.connect = AsyncMock(return_value=False)

    result = await price_watcher.start()

    assert result is False
    assert price_watcher.is_running is False


@pytest.mark.asyncio()
async def test_watcher_stop(price_watcher):
    """Тест остановки наблюдателя."""
    # Создаём мок задачи которая уже завершена (done=True)
    # Тогда await не будет вызван
    mock_ws_task = MagicMock()
    mock_ws_task.done = MagicMock(return_value=True)
    mock_ws_task.cancel = MagicMock()

    mock_update_task = MagicMock()
    mock_update_task.done = MagicMock(return_value=True)
    mock_update_task.cancel = MagicMock()

    price_watcher.is_running = True
    price_watcher.ws_task = mock_ws_task
    price_watcher.price_update_task = mock_update_task

    await price_watcher.stop()

    assert price_watcher.is_running is False
    # cancel() не должен вызываться для завершенных задач
    mock_ws_task.cancel.assert_not_called()
    mock_update_task.cancel.assert_not_called()
    price_watcher.websocket_client.close.assert_called_once()


@pytest.mark.asyncio()
async def test_watcher_stop_not_running(price_watcher):
    """Тест остановки неработающего наблюдателя."""
    price_watcher.is_running = False

    await price_watcher.stop()

    # close не должен вызываться
    price_watcher.websocket_client.close.assert_not_called()


# ==================== Тесты RealtimePriceWatcher - Watch Items ====================


def test_watch_item_without_price(price_watcher):
    """Тест добавления предмета без начальной цены."""
    price_watcher.watch_item("item_123")

    assert "item_123" in price_watcher.watched_items
    assert "item_123" not in price_watcher.price_cache


def test_watch_item_with_price(price_watcher):
    """Тест добавления предмета с начальной ценой."""
    price_watcher.watch_item("item_123", initial_price=15.50)

    assert "item_123" in price_watcher.watched_items
    assert price_watcher.price_cache["item_123"] == 15.50
    assert len(price_watcher.price_history["item_123"]) == 1


def test_unwatch_item(price_watcher):
    """Тест удаления предмета из отслеживания."""
    price_watcher.watch_item("item_123", initial_price=15.50)
    price_watcher.unwatch_item("item_123")

    assert "item_123" not in price_watcher.watched_items
    assert "item_123" not in price_watcher.price_cache


def test_unwatch_item_not_watched(price_watcher):
    """Тест удаления неотслеживаемого предмета."""
    # Не должно вызывать ошибок
    price_watcher.unwatch_item("nonexistent")

    assert "nonexistent" not in price_watcher.watched_items


# ==================== Тесты RealtimePriceWatcher - Alerts ====================


def test_add_price_alert(price_watcher, sample_price_alert):
    """Тест добавления оповещения о цене."""
    price_watcher.add_price_alert(sample_price_alert)

    assert "item_123" in price_watcher.price_alerts
    assert sample_price_alert in price_watcher.price_alerts["item_123"]
    # Предмет должен быть добавлен в отслеживаемые
    assert "item_123" in price_watcher.watched_items


def test_add_multiple_alerts_same_item(price_watcher):
    """Тест добавления нескольких оповещений для одного предмета."""
    alert1 = PriceAlert("item_123", "Test Item", 10.0, "below")
    alert2 = PriceAlert("item_123", "Test Item", 15.0, "above")

    price_watcher.add_price_alert(alert1)
    price_watcher.add_price_alert(alert2)

    assert len(price_watcher.price_alerts["item_123"]) == 2


def test_remove_price_alert(price_watcher, sample_price_alert):
    """Тест удаления оповещения о цене."""
    price_watcher.add_price_alert(sample_price_alert)
    price_watcher.remove_price_alert(sample_price_alert)

    assert "item_123" not in price_watcher.price_alerts


def test_remove_nonexistent_alert(price_watcher, sample_price_alert):
    """Тест удаления несуществующего оповещения."""
    # Не должно вызывать ошибок
    price_watcher.remove_price_alert(sample_price_alert)

    assert "item_123" not in price_watcher.price_alerts


def test_get_all_alerts(price_watcher):
    """Тест получения всех оповещений."""
    alert1 = PriceAlert("item_1", "Item 1", 10.0, "below")
    alert2 = PriceAlert("item_2", "Item 2", 20.0, "above")

    price_watcher.add_price_alert(alert1)
    price_watcher.add_price_alert(alert2)

    all_alerts = price_watcher.get_all_alerts()

    assert len(all_alerts) == 2
    assert "item_1" in all_alerts
    assert "item_2" in all_alerts


def test_get_triggered_alerts_empty(price_watcher):
    """Тест получения сработавших оповещений - пусто."""
    alert = PriceAlert("item_123", "Test Item", 10.0, "below")
    price_watcher.add_price_alert(alert)

    triggered = price_watcher.get_triggered_alerts()

    assert len(triggered) == 0


def test_get_triggered_alerts_with_triggers(price_watcher):
    """Тест получения сработавших оповещений."""
    alert1 = PriceAlert("item_1", "Item 1", 10.0, "below")
    alert2 = PriceAlert("item_2", "Item 2", 20.0, "above")

    price_watcher.add_price_alert(alert1)
    price_watcher.add_price_alert(alert2)

    # Срабатываем первое оповещение
    alert1.check_condition(9.0)
    alert1.is_triggered = True  # Вручную устанавливаем флаг

    triggered = price_watcher.get_triggered_alerts()

    assert len(triggered) == 1
    assert triggered[0] == alert1


def test_reset_triggered_alerts(price_watcher):
    """Тест сброса сработавших оповещений."""
    alert1 = PriceAlert("item_1", "Item 1", 10.0, "below")
    alert2 = PriceAlert("item_2", "Item 2", 20.0, "above")

    price_watcher.add_price_alert(alert1)
    price_watcher.add_price_alert(alert2)

    # Срабатываем оба оповещения
    alert1.check_condition(9.0)
    alert1.is_triggered = True  # Вручную устанавливаем флаг
    alert2.check_condition(21.0)
    alert2.is_triggered = True  # Вручную устанавливаем флаг

    count = price_watcher.reset_triggered_alerts()

    assert count == 2
    assert alert1.is_triggered is False
    assert alert2.is_triggered is False


# ==================== Тесты RealtimePriceWatcher - Handlers ====================


def test_register_price_change_handler(price_watcher):
    """Тест регистрации обработчика изменения цены."""
    handler = AsyncMock()
    price_watcher.register_price_change_handler(handler, item_id="item_123")

    assert handler in price_watcher.price_change_handlers["item_123"]


def test_register_global_price_change_handler(price_watcher):
    """Тест регистрации глобального обработчика изменения цены."""
    handler = AsyncMock()
    price_watcher.register_price_change_handler(handler)  # По умолчанию "*"

    assert handler in price_watcher.price_change_handlers["*"]


def test_register_alert_handler(price_watcher):
    """Тест регистрации обработчика оповещений."""
    handler = AsyncMock()
    price_watcher.register_alert_handler(handler)

    assert handler in price_watcher.alert_handlers


# ==================== Тесты RealtimePriceWatcher - Price Operations ====================


def test_get_current_price_exists(price_watcher):
    """Тест получения текущей цены существующего предмета."""
    price_watcher.watch_item("item_123", initial_price=15.50)

    price = price_watcher.get_current_price("item_123")

    assert price == 15.50


def test_get_current_price_not_exists(price_watcher):
    """Тест получения текущей цены несуществующего предмета."""
    price = price_watcher.get_current_price("nonexistent")

    assert price is None


def test_add_to_price_history(price_watcher):
    """Тест добавления в историю цен."""
    price_watcher._add_to_price_history("item_123", 15.50)

    history = price_watcher.price_history["item_123"]
    assert len(history) == 1
    assert history[0][1] == 15.50


def test_add_to_price_history_limit(price_watcher):
    """Тест ограничения размера истории цен."""
    price_watcher.max_history_points = 5

    # Добавляем 10 точек
    for i in range(10):
        price_watcher._add_to_price_history("item_123", float(i))

    history = price_watcher.price_history["item_123"]

    # Должно остаться только 5 последних
    assert len(history) == 5
    assert history[0][1] == 5.0
    assert history[-1][1] == 9.0


def test_get_price_history_all(price_watcher):
    """Тест получения всей истории цен."""
    for i in range(5):
        price_watcher._add_to_price_history("item_123", float(i))

    history = price_watcher.get_price_history("item_123")

    assert len(history) == 5


def test_get_price_history_with_limit(price_watcher):
    """Тест получения истории цен с лимитом."""
    for i in range(10):
        price_watcher._add_to_price_history("item_123", float(i))

    history = price_watcher.get_price_history("item_123", limit=3)

    assert len(history) == 3
    # Последние 3 точки
    assert history[0][1] == 7.0
    assert history[-1][1] == 9.0


def test_get_price_history_empty(price_watcher):
    """Тест получения истории несуществующего предмета."""
    history = price_watcher.get_price_history("nonexistent")

    assert len(history) == 0


def test_get_item_metadata_exists(price_watcher):
    """Тест получения метаданных существующего предмета."""
    price_watcher.item_metadata["item_123"] = {
        "title": "AK-47 | Redline",
        "gameId": "csgo",
        "lastUpdated": time.time(),
    }

    metadata = price_watcher.get_item_metadata("item_123")

    assert metadata["title"] == "AK-47 | Redline"
    assert metadata["gameId"] == "csgo"


def test_get_item_metadata_not_exists(price_watcher):
    """Тест получения метаданных несуществующего предмета."""
    metadata = price_watcher.get_item_metadata("nonexistent")

    assert metadata == {}


# ==================== Тесты RealtimePriceWatcher - Subscribe ====================


@pytest.mark.asyncio()
async def test_subscribe_to_item_not_running(price_watcher):
    """Тест подписки на предмет когда наблюдатель не запущен."""
    result = await price_watcher.subscribe_to_item("item_123")

    assert result is False


@pytest.mark.asyncio()
async def test_subscribe_to_item_success(price_watcher):
    """Тест успешной подписки на предмет."""
    price_watcher.is_running = True

    # Мокируем _fetch_item_price
    with patch.object(price_watcher, "_fetch_item_price", return_value=15.50):
        result = await price_watcher.subscribe_to_item("item_123", game="csgo")

        assert result is True
        assert "item_123" in price_watcher.watched_items
        assert price_watcher.price_cache["item_123"] == 15.50


@pytest.mark.asyncio()
async def test_subscribe_to_market_updates_not_running(price_watcher):
    """Тест подписки на обновления рынка когда наблюдатель не запущен."""
    result = await price_watcher.subscribe_to_market_updates("csgo")

    assert result is False


@pytest.mark.asyncio()
async def test_subscribe_to_market_updates_success(price_watcher):
    """Тест успешной подписки на обновления рынка."""
    price_watcher.is_running = True

    result = await price_watcher.subscribe_to_market_updates("csgo")

    assert result is True
    price_watcher.websocket_client.subscribe_to_market_updates.assert_called_once_with(
        "csgo"
    )


# ==================== Тесты RealtimePriceWatcher - Fetch Price ====================


@pytest.mark.asyncio()
async def test_fetch_item_price_success(price_watcher, mock_api_client):
    """Тест успешного получения цены предмета."""
    mock_api_client._request = AsyncMock(
        return_value={
            "items": [
                {
                    "itemId": "item_123",
                    "title": "AK-47 | Redline (Field-Tested)",
                    "price": {"USD": "1550"},  # Цена в центах
                }
            ]
        }
    )

    price = await price_watcher._fetch_item_price("item_123", game="csgo")

    assert price == 15.50
    # Проверяем сохранение метаданных
    assert "item_123" in price_watcher.item_metadata


@pytest.mark.asyncio()
async def test_fetch_item_price_no_items(price_watcher, mock_api_client):
    """Тест получения цены - предмет не найден."""
    mock_api_client._request = AsyncMock(return_value={"items": []})

    price = await price_watcher._fetch_item_price("item_123")

    assert price is None


@pytest.mark.asyncio()
async def test_fetch_item_price_api_error(price_watcher, mock_api_client):
    """Тест получения цены - ошибка API."""
    mock_api_client._request = AsyncMock(side_effect=Exception("API Error"))

    price = await price_watcher._fetch_item_price("item_123")

    assert price is None


# ==================== Тесты RealtimePriceWatcher - Process Price Change ====================


@pytest.mark.asyncio()
async def test_process_price_change_no_change(price_watcher):
    """Тест обработки изменения цены - цена не изменилась."""
    handler = AsyncMock()
    price_watcher.register_price_change_handler(handler, item_id="item_123")

    await price_watcher._process_price_change("item_123", 10.0, 10.0)

    # Обработчик не должен быть вызван
    handler.assert_not_called()


@pytest.mark.asyncio()
async def test_process_price_change_with_handlers(price_watcher):
    """Тест обработки изменения цены с обработчиками."""
    handler1 = AsyncMock()
    handler2 = AsyncMock()
    global_handler = AsyncMock()

    price_watcher.register_price_change_handler(handler1, item_id="item_123")
    price_watcher.register_price_change_handler(handler2, item_id="item_123")
    price_watcher.register_price_change_handler(global_handler)  # Глобальный

    await price_watcher._process_price_change("item_123", 10.0, 12.0)

    # Все обработчики должны быть вызваны
    handler1.assert_called_once_with("item_123", 10.0, 12.0)
    handler2.assert_called_once_with("item_123", 10.0, 12.0)
    global_handler.assert_called_once_with("item_123", 10.0, 12.0)


@pytest.mark.asyncio()
async def test_process_price_change_handler_error(price_watcher):
    """Тест обработки изменения цены - ошибка в обработчике."""
    failing_handler = AsyncMock(side_effect=Exception("Handler error"))
    working_handler = AsyncMock()

    price_watcher.register_price_change_handler(failing_handler, item_id="item_123")
    price_watcher.register_price_change_handler(working_handler, item_id="item_123")

    # Не должно вызывать исключение
    await price_watcher._process_price_change("item_123", 10.0, 12.0)

    # Работающий обработчик должен быть вызван
    working_handler.assert_called_once()


# ==================== Тесты RealtimePriceWatcher - Check Alerts ====================


@pytest.mark.asyncio()
async def test_check_alerts_triggered(price_watcher):
    """Тест проверки оповещений - оповещение срабатывает."""
    alert = PriceAlert("item_123", "Test Item", 10.0, "below")
    alert_handler = AsyncMock()

    price_watcher.add_price_alert(alert)
    price_watcher.register_alert_handler(alert_handler)

    await price_watcher._check_alerts("item_123", 9.0)

    # Оповещение должно сработать
    assert alert.is_triggered is True
    alert_handler.assert_called_once_with(alert, 9.0)


@pytest.mark.asyncio()
async def test_check_alerts_not_triggered(price_watcher):
    """Тест проверки оповещений - оповещение не срабатывает."""
    alert = PriceAlert("item_123", "Test Item", 10.0, "below")
    alert_handler = AsyncMock()

    price_watcher.add_price_alert(alert)
    price_watcher.register_alert_handler(alert_handler)

    await price_watcher._check_alerts("item_123", 11.0)

    # Оповещение не должно сработать
    assert alert.is_triggered is False
    alert_handler.assert_not_called()


@pytest.mark.asyncio()
async def test_check_alerts_already_triggered(price_watcher):
    """Тест проверки оповещений - уже сработавшее оповещение."""
    alert = PriceAlert("item_123", "Test Item", 10.0, "below")
    alert_handler = AsyncMock()

    price_watcher.add_price_alert(alert)
    price_watcher.register_alert_handler(alert_handler)

    # Первая проверка - срабатывает
    await price_watcher._check_alerts("item_123", 9.0)

    # Сбрасываем мок
    alert_handler.reset_mock()

    # Вторая проверка - уже сработало
    await price_watcher._check_alerts("item_123", 8.0)

    # Обработчик не должен быть вызван повторно
    alert_handler.assert_not_called()


# ==================== Тесты RealtimePriceWatcher - Handle Messages ====================


@pytest.mark.asyncio()
async def test_handle_market_update_success(price_watcher):
    """Тест обработки сообщения обновления рынка."""
    price_watcher.watch_item("item_123")

    message = {"data": {"items": [{"itemId": "item_123", "price": {"USD": "1550"}}]}}

    with patch.object(price_watcher, "_process_price_change") as mock_process:
        with patch.object(price_watcher, "_check_alerts") as mock_check:
            await price_watcher._handle_market_update(message)

            # Проверяем обновление цены
            assert price_watcher.price_cache["item_123"] == 15.50

            # Проверяем вызовы обработчиков
            mock_process.assert_called_once()
            mock_check.assert_called_once()


@pytest.mark.asyncio()
async def test_handle_market_update_unwatched_item(price_watcher):
    """Тест обработки сообщения для неотслеживаемого предмета."""
    message = {"data": {"items": [{"itemId": "item_999", "price": {"USD": "1550"}}]}}

    with patch.object(price_watcher, "_process_price_change") as mock_process:
        await price_watcher._handle_market_update(message)

        # Цена не должна быть сохранена
        assert "item_999" not in price_watcher.price_cache

        # Обработчик не должен быть вызван
        mock_process.assert_not_called()


@pytest.mark.asyncio()
async def test_handle_items_update_with_metadata(price_watcher):
    """Тест обработки сообщения обновления предметов с метаданными."""
    price_watcher.watch_item("item_123")

    message = {
        "data": {
            "items": [
                {
                    "itemId": "item_123",
                    "title": "AK-47 | Redline (Field-Tested)",
                    "gameId": "csgo",
                    "price": {"USD": "1550"},
                }
            ]
        }
    }

    await price_watcher._handle_items_update(message)

    # Проверяем сохранение метаданных
    assert "item_123" in price_watcher.item_metadata
    metadata = price_watcher.item_metadata["item_123"]
    assert metadata["title"] == "AK-47 | Redline (Field-Tested)"
    assert metadata["gameId"] == "csgo"


# ==================== Тесты интеграции ====================


@pytest.mark.asyncio()
async def test_full_workflow_with_alert(price_watcher):
    """Интеграционный тест: полный цикл работы с оповещением."""
    # Создаём оповещение
    alert = PriceAlert("item_123", "Test Item", 10.0, "below")
    alert_triggered = []

    async def alert_handler(alert_obj, price):
        alert_triggered.append((alert_obj, price))

    # Регистрируем обработчик и добавляем оповещение
    price_watcher.register_alert_handler(alert_handler)
    price_watcher.add_price_alert(alert)

    # Имитируем получение сообщения с низкой ценой
    message = {"data": {"items": [{"itemId": "item_123", "price": {"USD": "950"}}]}}

    await price_watcher._handle_market_update(message)

    # Проверяем результат
    assert len(alert_triggered) == 1
    assert alert_triggered[0][0] == alert
    assert alert_triggered[0][1] == 9.50
    assert alert.is_triggered is True


@pytest.mark.asyncio()
async def test_full_workflow_price_changes(price_watcher):
    """Интеграционный тест: отслеживание изменений цен."""
    price_changes = []

    async def price_change_handler(item_id, old_price, new_price):
        price_changes.append((item_id, old_price, new_price))

    price_watcher.register_price_change_handler(
        price_change_handler, item_id="item_123"
    )
    price_watcher.watch_item("item_123", initial_price=10.0)

    # Имитируем изменение цены
    message = {"data": {"items": [{"itemId": "item_123", "price": {"USD": "1200"}}]}}

    await price_watcher._handle_market_update(message)

    # Проверяем результат
    assert len(price_changes) == 1
    assert price_changes[0] == ("item_123", 10.0, 12.0)
    assert price_watcher.get_current_price("item_123") == 12.0
    assert len(price_watcher.get_price_history("item_123")) == 2
