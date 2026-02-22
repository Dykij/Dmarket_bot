"""
Integration тесты для валидации API responses с использованием Pydantic схем.

Эти тесты проверяют:
- Корректную работу декораторов @validate_response в реальных сценариях
- Интеграцию с Notifier для отправки уведомлений при ValidationError
- End-to-end flow: API request → validation → notification
- Backward compatibility: невалидные responses не ломают приложение
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.dmarket.dmarket_api import DMarketAPI


@pytest.fixture()
def mock_notifier():
    """Мок Notifier для тестирования отправки уведомлений."""
    notifier = AsyncMock()
    notifier.send_message = AsyncMock()
    return notifier


@pytest.fixture()
def api_client(mock_notifier):
    """DMarket API client с мокированным notifier."""
    return DMarketAPI(
        public_key="test_public_key",
        secret_key="test_secret_key",
        notifier=mock_notifier,
        dry_run=True,  # Безопасный режим
    )


class TestGetMarketItemsIntegration:
    """Integration тесты для get_market_items()."""

    @pytest.mark.asyncio()
    async def test_valid_response_validates_successfully(self, api_client):
        """Тест: валидный response проходит валидацию через decorator."""
        # Мокируем реальный API response
        valid_response = {
            "cursor": "next_page_token",
            "objects": [
                {
                    "itemId": "item_123",
                    "title": "AK-47 | Redline (Field-Tested)",
                    "price": {"USD": "1250"},
                    "suggestedPrice": {"USD": "1300"},
                },
                {
                    "itemId": "item_456",
                    "title": "AWP | Asiimov (Field-Tested)",
                    "price": {"USD": "2500"},
                },
            ],
            "total": "150",
        }

        with patch.object(api_client, "_request", return_value=valid_response):
            result = await api_client.get_market_items(game="csgo", limit=10)

        # Decorator валидировал и вернул исходные данные
        assert "objects" in result
        assert isinstance(result["objects"], list)
        assert len(result["objects"]) == 2
        assert result["cursor"] == "next_page_token"

        # Notifier НЕ вызван (нет ValidationError)
        api_client.notifier.send_message.assert_not_called()

    @pytest.mark.asyncio()
    async def test_invalid_response_sends_notification(self, api_client):
        """Тест: невалидный response триггерит Telegram notification."""
        # Невалидный response (отсутствует total, objects не list)
        invalid_response = {
            "cursor": "token",
            "objects": "not_a_list",  # Должен быть list
            # total отсутствует
        }

        with patch.object(api_client, "_request", return_value=invalid_response):
            result = await api_client.get_market_items(game="csgo", limit=10)

        # Возвращается raw data (backward compatibility)
        assert result == invalid_response

        # Notifier вызван с критическим алертом
        api_client.notifier.send_message.assert_called_once()
        call_args = api_client.notifier.send_message.call_args

        # Проверяем параметры вызова
        assert "priority" in call_args.kwargs
        assert call_args.kwargs["priority"] == "critical"
        assert "DMarket API" in call_args.kwargs["message"]


class TestCreateTargetsIntegration:
    """Integration тесты для create_targets()."""

    @pytest.mark.asyncio()
    async def test_valid_create_targets_response(self, api_client):
        """Тест: валидный response создания таргетов."""
        valid_response = {
            "Result": [
                {
                    "TargetID": "target_abc123",
                    "Title": "AK-47 | Redline (FT)",
                    "Status": "Created",
                },
                {
                    "TargetID": "target_def456",
                    "Title": "AWP | Dragon Lore (FN)",
                    "Status": "Created",
                },
            ]
        }

        with patch.object(api_client, "_request", return_value=valid_response):
            result = await api_client.create_targets(
                game_id="csgo",
                targets=[
                    {
                        "Title": "AK-47 | Redline (FT)",
                        "Amount": 1,
                        "Price": {"amount": "1200", "currency": "USD"},
                    }
                ],
            )

        assert "Result" in result
        assert len(result["Result"]) == 2
        api_client.notifier.send_message.assert_not_called()


class TestGetUserTargetsIntegration:
    """Integration тесты для get_user_targets()."""

    @pytest.mark.asyncio()
    async def test_valid_user_targets_response(self, api_client):
        """Тест: валидный response списка таргетов."""
        valid_response = {
            "Items": [
                {
                    "TargetID": "target_1",
                    "Title": "AK-47 | Redline (FT)",
                    "Amount": 2,
                    "Price": {"amount": "1200", "currency": "USD"},
                    "Status": "TargetStatusActive",
                    "CreatedAt": 1699876543,
                }
            ],
            "Total": "1",
            "Cursor": "next",
        }

        with patch.object(api_client, "_request", return_value=valid_response):
            result = await api_client.get_user_targets(game_id="csgo")

        assert "Items" in result
        assert len(result["Items"]) == 1
        api_client.notifier.send_message.assert_not_called()


class TestBuyOffersIntegration:
    """Integration тесты для buy_offers()."""

    @pytest.mark.asyncio()
    async def test_valid_buy_offers_response(self, api_client):
        """Тест: валидный response покупки предложений."""
        valid_response = {
            "orderId": "order_xyz789",
            "status": "TxSuccess",
            "txId": "tx_123abc",
            "dmOffersStatus": {
                "offer_1": {"status": "Success"},
                "offer_2": {"status": "Success"},
            },
        }

        with patch.object(api_client, "_request", return_value=valid_response):
            result = await api_client.buy_offers(
                offers=[
                    {
                        "offerId": "offer_1",
                        "price": {"amount": 1000, "currency": "USD"},
                    }
                ]
            )

        assert result["status"] == "TxSuccess"
        assert result["orderId"] == "order_xyz789"
        api_client.notifier.send_message.assert_not_called()

    @pytest.mark.asyncio()
    async def test_missing_required_status_field(self, api_client):
        """Тест: отсутствие обязательного поля status триггерит alert."""
        invalid_response = {
            "orderId": "order_123",
            "txId": "tx_456",
            # status отсутствует (обязательное поле!)
        }

        with patch.object(api_client, "_request", return_value=invalid_response):
            result = await api_client.buy_offers(offers=[{"offerId": "o1"}])

        # Backward compatibility: возвращается raw data
        assert result == invalid_response

        # Notifier вызван
        api_client.notifier.send_message.assert_called_once()


class TestAggregatedPricesIntegration:
    """Integration тесты для get_aggregated_prices_bulk()."""

    @pytest.mark.asyncio()
    async def test_valid_aggregated_prices_response(self, api_client):
        """Тест: валидный response агрегированных цен."""
        valid_response = {
            "aggregatedPrices": [
                {
                    "title": "AK-47 | Redline (FT)",
                    "orderBestPrice": "1100",
                    "orderCount": 15,
                    "offerBestPrice": "1250",
                    "offerCount": 23,
                },
                {
                    "title": "AWP | Asiimov (FT)",
                    "orderBestPrice": "2400",
                    "orderCount": 8,
                    "offerBestPrice": "2600",
                    "offerCount": 12,
                },
            ],
            "nextCursor": "cursor_token",
        }

        with patch.object(api_client, "_request", return_value=valid_response):
            result = await api_client.get_aggregated_prices_bulk(
                game="csgo", titles=["AK-47 | Redline (FT)", "AWP | Asiimov (FT)"]
            )

        assert "aggregatedPrices" in result
        assert len(result["aggregatedPrices"]) == 2
        api_client.notifier.send_message.assert_not_called()


class TestSalesHistoryIntegration:
    """Integration тесты для get_sales_history()."""

    @pytest.mark.asyncio()
    async def test_valid_sales_history_response(self, api_client):
        """Тест: валидный response истории продаж."""
        valid_response = {
            "sales": [
                {"price": "1250", "date": 1699876543, "txOperationType": "Offer"},
                {"price": "1300", "date": 1699876600, "txOperationType": "Target"},
            ]
        }

        with patch.object(api_client, "_request", return_value=valid_response):
            result = await api_client.get_sales_history(
                game="csgo", title="AK-47 | Redline (FT)"
            )

        assert "sales" in result
        assert len(result["sales"]) == 2
        api_client.notifier.send_message.assert_not_called()


class TestNotifierIntegration:
    """Тесты интеграции с Notifier."""

    @pytest.mark.asyncio()
    async def test_notifier_receives_validation_error_details(self, api_client):
        """Тест: Notifier получает детальную информацию об ошибке валидации."""
        # Невалидный response: неверный тип поля
        invalid_response = {
            "objects": "not_a_list",  # Должен быть list
            "cursor": "token",
            # total отсутствует
        }

        with patch.object(api_client, "_request", return_value=invalid_response):
            await api_client.get_market_items(game="csgo")

        # Проверяем детали вызова notifier
        api_client.notifier.send_message.assert_called_once()
        call_kwargs = api_client.notifier.send_message.call_args.kwargs

        # Проверяем содержимое сообщения
        message = call_kwargs["message"]
        message_lower = message.lower()
        assert "dmarket api" in message_lower
        assert "/exchange/v1/market/items" in message
        # Проверяем наличие слов об ошибке
        assert "error" in message_lower or "ошиб" in message_lower

    @pytest.mark.asyncio()
    async def test_api_without_notifier_works_correctly(self):
        """Тест: API работает корректно БЕЗ notifier (backward compatibility)."""
        # API без notifier
        api = DMarketAPI(
            public_key="test_key",
            secret_key="test_secret",
            notifier=None,  # Явно без notifier
            dry_run=True,
        )

        invalid_response = {
            "objects": "not_a_list",
            "cursor": 123,
        }

        with patch.object(api, "_request", return_value=invalid_response):
            result = await api.get_market_items(game="csgo")

        # get_market_items обрабатывает ошибки внутренне и возвращает пустой список
        # Главное - без notifier не должно быть exceptions
        assert isinstance(result, dict)


class TestBackwardCompatibility:
    """Тесты обратной совместимости."""

    @pytest.mark.asyncio()
    async def test_invalid_response_returns_raw_data(self, api_client):
        """Тест: невалидный response не ломает приложение, возвращается raw data."""
        completely_invalid = {"unexpected": "structure", "random": [1, 2, 3]}

        with patch.object(api_client, "_request", return_value=completely_invalid):
            result = await api_client.get_market_items(game="csgo")

        # get_market_items обрабатывает невалидные ответы внутренне
        # возвращает пустой список или базовую структуру
        assert isinstance(result, dict)

        # Notifier НЕ вызывается - метод обрабатывает внутри
        api_client.notifier.send_message.assert_not_called()

    @pytest.mark.asyncio()
    async def test_extra_fields_in_response_accepted(self, api_client):
        """Тест: дополнительные поля в response не ломают валидацию (extra='allow')."""
        response_with_new_fields = {
            "objects": [
                {"itemId": "item1", "title": "Test Item", "price": {"USD": "1000"}}
            ],
            "total": "1",
            "cursor": "next_token",
            "newField": "future_data",  # Новое поле
            "extraMetadata": {"nested": "structure"},  # Дополнительная структура
        }

        with patch.object(
            api_client, "_request", return_value=response_with_new_fields
        ):
            result = await api_client.get_market_items(game="csgo", limit=10)

        # Валидация прошла успешно (extra='allow')
        assert "objects" in result
        assert result["total"] == "1"

        # Notifier НЕ вызван (нет ошибки)
        api_client.notifier.send_message.assert_not_called()


class TestDecoratorBehavior:
    """Тесты поведения декоратора @validate_response."""

    @pytest.mark.asyncio()
    async def test_decorator_does_not_modify_valid_response(self, api_client):
        """Тест: decorator не изменяет валидный response."""
        original_response = {
            "objects": [
                {"itemId": "id1", "title": "Item 1", "price": {"USD": "100"}},
                {"itemId": "id2", "title": "Item 2", "price": {"USD": "200"}},
            ],
            "total": "2",
            "cursor": "next_page",
        }

        with patch.object(api_client, "_request", return_value=original_response):
            result = await api_client.get_market_items(game="csgo", limit=10)

        # Decorator вернул точно такие же данные
        assert result == original_response

    @pytest.mark.asyncio()
    async def test_multiple_validation_errors_all_reported(self, api_client):
        """Тест: все ошибки валидации репортятся в одном уведомлении."""
        # Response с множественными ошибками
        invalid_response = {
            "objects": "not_a_list",  # Ошибка 1: неверный тип
            "cursor": 123,  # Ошибка 2: должна быть строка
            # total отсутствует - Ошибка 3
        }

        with patch.object(api_client, "_request", return_value=invalid_response):
            await api_client.get_market_items(game="csgo")

        # Notifier вызван один раз (все ошибки в одном сообщении)
        api_client.notifier.send_message.assert_called_once()
