"""Дополнительные тесты для функций проверки алертов в notifier.py."""

from unittest.mock import AsyncMock, patch

import pytest

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture(autouse=True)
def reset_user_alerts():
    """Сбрасывает глобальный словарь alerts перед каждым тестом."""
    import src.telegram_bot.notifier as notifier_module

    notifier_module._user_alerts = {}
    notifier_module._current_prices_cache = {}
    yield
    notifier_module._user_alerts = {}
    notifier_module._current_prices_cache = {}


# ============================================================================
# ТЕСТЫ CHECK_ALL_ALERTS С ОТПРАВКОЙ УВЕДОМЛЕНИЙ
# ============================================================================


@pytest.mark.asyncio()
async def test_check_all_alerts_with_no_triggered_alerts():
    """Тест check_all_alerts без сработавших алертов."""
    import src.telegram_bot.notifier as notifier_module
    from src.telegram_bot.notifier import check_all_alerts

    notifier_module._user_alerts["12345"] = {
        "alerts": [
            {
                "id": "alert_1",
                "item_id": "item_123",
                "title": "Test Item",
                "type": "price_drop",
                "threshold": 10.0,
                "active": True,
            }
        ],
        "settings": {"enabled": True},
        "last_notification": 0,
        "dAlgoly_notifications": 0,
        "last_day": "2023-06-01",
    }

    mock_api = AsyncMock()
    mock_bot = AsyncMock()

    # Алерт не сработал
    with (
        patch(
            "src.telegram_bot.notifier.check_price_alert",
            return_value=None,
        ),
        patch("asyncio.sleep", return_value=None),
    ):
        awAlgot check_all_alerts(mock_api, mock_bot)

        # Сообщение не должно быть отправлено
        mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio()
async def test_format_alert_message_volume_type():
    """Тест форматирования сообщения для типа volume_increase."""
    from src.telegram_bot.notifier import format_alert_message

    alert = {
        "id": "alert_vol",
        "title": "Popular Item",
        "game": "csgo",
        "type": "volume_increase",
        "threshold": 500,
        "item_id": "item_123",
        "active": True,
    }

    message = format_alert_message(alert)

    assert "Popular Item" in message
    assert "500" in message


@pytest.mark.asyncio()
async def test_format_alert_message_good_deal_type():
    """Тест форматирования сообщения для типа good_deal."""
    from src.telegram_bot.notifier import format_alert_message

    alert = {
        "id": "alert_deal",
        "title": "Discounted Item",
        "game": "dota2",
        "type": "good_deal",
        "threshold": 25.0,
        "item_id": "item_456",
        "active": True,
    }

    message = format_alert_message(alert)

    assert "Discounted Item" in message
    assert "25" in message


@pytest.mark.asyncio()
async def test_format_alert_message_trend_change_type():
    """Тест форматирования сообщения для типа trend_change."""
    from src.telegram_bot.notifier import format_alert_message

    alert = {
        "id": "alert_trend",
        "title": "Trending Item",
        "game": "csgo",
        "type": "trend_change",
        "threshold": 75.0,
        "item_id": "item_789",
        "active": True,
    }

    message = format_alert_message(alert)

    assert "Trending Item" in message
    assert "75" in message
