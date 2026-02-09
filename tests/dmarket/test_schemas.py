"""
Unit-тесты для Pydantic схем DMarket API (src/dmarket/schemas.py).

Тестирование включает:
- Валидацию корректных данных
- Обработку некорректных данных
- Проверку helper-методов (get_usd_decimal, to_usd_decimal, get_price_decimal)
- Алиасы полей (camelCase ↔ snake_case)
- Точность Decimal для финансовых данных
- Кастомные валидаторы (@field_validator)
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.dmarket.schemas import (
    AggregatedPricesResponse,
    BalanceResponse,
    BuyOffersResponse,
    CreateTargetsResponse,
    MarketItemsResponse,
    SalesHistoryResponse,
    UserTargetsResponse,
)


class TestBalanceResponse:
    """Тесты для схемы BalanceResponse."""

    def test_valid_balance_response(self):
        """Тест валидации корректного ответа баланса."""
        data = {
            "usd": "12345",  # $123.45
            "dmc": "50000",  # 500.00 DMC
        }

        response = BalanceResponse(**data)

        assert response.usd == "12345"
        assert response.dmc == "50000"

    def test_get_usd_decimal(self):
        """Тест конвертации USD центов в Decimal."""
        data = {"usd": "12345", "dmc": "0"}
        response = BalanceResponse(**data)

        usd_value = response.get_usd_decimal()

        assert isinstance(usd_value, Decimal)
        assert usd_value == Decimal("123.45")

    def test_get_usd_decimal_zero(self):
        """Тест конвертации нулевого баланса."""
        data = {"usd": "0", "dmc": "0"}
        response = BalanceResponse(**data)

        assert response.get_usd_decimal() == Decimal(0)

    def test_get_available_usd_decimal(self):
        """Тест метода get_available_usd_decimal."""
        data = {"usd": "10000", "dmc": "0", "usdAvailableToWithdraw": "8000"}
        response = BalanceResponse(**data)

        available = response.get_available_usd_decimal()

        assert isinstance(available, Decimal)
        assert available == Decimal("80.00")

    def test_extra_fields_allowed(self):
        """Тест что дополнительные поля разрешены (forward compatibility)."""
        data = {
            "usd": "10000",
            "dmc": "5000",
            "new_currency": "1000",  # Новое поле
        }

        response = BalanceResponse(**data)

        # Pydantic v2 with extra="allow"
        assert response.usd == "10000"
        assert hasattr(response, "new_currency")


class TestMarketItemsResponse:
    """Тесты для схемы MarketItemsResponse."""

    def test_valid_market_items_response(self):
        """Тест валидации корректного ответа списка предметов."""
        data = {
            "cursor": "next_page_token",
            "objects": [
                {
                    "itemId": "item_123",
                    "title": "AK-47 | Redline (Field-Tested)",
                    "price": {"USD": "1250"},
                    "imageUrl": "https://example.com/image.png",
                }
            ],
            "total": "150",  # total - строка или число, не dict
        }

        response = MarketItemsResponse(**data)

        assert response.cursor == "next_page_token"
        assert len(response.objects) == 1
        # objects содержит MarketItemModel, используем атрибуты
        assert response.objects[0].item_id == "item_123"
        assert response.objects[0].title == "AK-47 | Redline (Field-Tested)"
        assert response.total == 150  # Валидатор конвертирует в int

    def test_empty_objects_list(self):
        """Тест пустого списка предметов."""
        data = {"objects": [], "total": "0"}

        response = MarketItemsResponse(**data)

        assert response.objects == []
        assert response.cursor is None
        assert response.total == 0

    def test_price_conversion(self):
        """Тест конвертации цены в Decimal через PriceModel."""
        data = {
            "objects": [
                {
                    "itemId": "item_123",
                    "title": "Test Item",
                    "price": {"USD": "2500"},  # $25.00
                }
            ],
            "total": "1",
        }

        response = MarketItemsResponse(**data)
        item = response.objects[0]

        # Проверка конвертации цены через PriceModel
        price_usd = item.price.to_usd_decimal()
        assert isinstance(price_usd, Decimal)
        assert price_usd == Decimal("25.00")


class TestCreateTargetsResponse:
    """Тесты для схемы CreateTargetsResponse."""

    def test_valid_create_targets_response(self):
        """Тест валидации корректного ответа создания таргетов."""
        data = {
            "Result": [
                {
                    "TargetID": "target_123",
                    "Title": "AK-47 | Redline (FT)",
                    "Status": "Created",
                }
            ]
        }

        response = CreateTargetsResponse(**data)

        assert len(response.result) == 1
        # TargetResultModel - Pydantic модель, доступ через атрибуты
        assert response.result[0].target_id == "target_123"
        assert response.result[0].status == "Created"

    def test_camel_case_alias(self):
        """Тест алиаса Result -> result."""
        # DMarket API возвращает "Result", но мы используем snake_case
        data = {"Result": [{"TargetID": "t1", "Status": "Created"}]}

        response = CreateTargetsResponse(**data)

        # Доступ через snake_case атрибуты Pydantic модели
        assert response.result[0].target_id == "t1"


class TestUserTargetsResponse:
    """Тесты для схемы UserTargetsResponse."""

    def test_valid_user_targets_response(self):
        """Тест валидации корректного ответа списка таргетов."""
        data = {
            "Items": [
                {
                    "TargetID": "target_456",
                    "Title": "AWP | Asiimov (FT)",
                    "Amount": 2,
                    "Price": {
                        "amount": "3000",
                        "currency": "USD",
                    },  # TargetPriceModel использует lowercase
                    "Status": "TargetStatusActive",
                    "CreatedAt": 1699876543,  # Обязательное поле для UserTargetModel
                }
            ],
            "Total": "10",
        }

        response = UserTargetsResponse(**data)

        assert len(response.items) == 1
        # UserTargetModel - Pydantic модель, доступ через атрибуты
        assert response.items[0].target_id == "target_456"
        assert response.total == 10  # Валидатор преобразует str в int

    def test_optional_cursor(self):
        """Тест опционального поля Cursor."""
        data = {"Items": [], "Total": "0", "Cursor": "next_cursor"}

        response = UserTargetsResponse(**data)

        assert response.cursor == "next_cursor"


class TestBuyOffersResponse:
    """Тесты для схемы BuyOffersResponse."""

    def test_valid_buy_offers_response(self):
        """Тест валидации корректного ответа покупки."""
        data = {
            "orderId": "order_789",
            "status": "TxSuccess",
            "txId": "tx_12345",
            "dmOffersStatus": {
                "offer_1": {"status": "Success"},
                "offer_2": {"status": "Pending"},
            },
        }

        response = BuyOffersResponse(**data)

        assert response.order_id == "order_789"
        assert response.status == "TxSuccess"
        assert response.dm_offers_status["offer_1"]["status"] == "Success"

    def test_camel_case_aliases(self):
        """Тест алиасов для camelCase полей."""
        data = {
            "orderId": "o1",  # -> order_id
            "status": "TxPending",  # Обязательное поле
            "txId": "t1",  # -> tx_id
            "dmOffersStatus": {},  # -> dm_offers_status
        }

        response = BuyOffersResponse(**data)

        assert response.order_id == "o1"
        assert response.status == "TxPending"
        assert response.tx_id == "t1"


class TestAggregatedPricesResponse:
    """Тесты для схемы AggregatedPricesResponse."""

    def test_valid_aggregated_prices_response(self):
        """Тест валидации корректного ответа агрегированных цен."""
        data = {
            "aggregatedPrices": [
                {
                    "title": "AK-47 | Redline (FT)",
                    "orderBestPrice": "1100",
                    "orderCount": 15,
                    "offerBestPrice": "1250",
                    "offerCount": 23,
                }
            ],
            "nextCursor": "cursor_abc",
        }

        response = AggregatedPricesResponse(**data)

        assert len(response.aggregated_prices) == 1
        # AggregatedPriceModel - Pydantic модель, доступ через атрибуты
        assert response.aggregated_prices[0].order_best_price == "1100"
        assert response.next_cursor == "cursor_abc"

    def test_camel_case_conversion(self):
        """Тест конвертации camelCase в snake_case."""
        data = {
            "aggregatedPrices": [{"title": "Item", "orderBestPrice": "100"}],
            "nextCursor": "c1",
        }

        response = AggregatedPricesResponse(**data)

        # Доступ через snake_case атрибуты Pydantic модели
        assert response.aggregated_prices[0].title == "Item"
        assert response.next_cursor == "c1"


class TestSalesHistoryResponse:
    """Тесты для схемы SalesHistoryResponse."""

    def test_valid_sales_history_response(self):
        """Тест валидации корректного ответа истории продаж."""
        data = {
            "sales": [
                {
                    "price": "1300",
                    "date": 1699876543,
                    "txOperationType": "Offer",
                }
            ]
        }

        response = SalesHistoryResponse(**data)

        assert len(response.sales) == 1
        # SaleModel - Pydantic модель, доступ через атрибуты
        assert response.sales[0].price == "1300"
        assert response.sales[0].tx_operation_type == "Offer"

    def test_empty_sales_list(self):
        """Тест пустой истории продаж."""
        data = {"sales": []}

        response = SalesHistoryResponse(**data)

        assert response.sales == []


class TestValidationErrors:
    """Тесты обработки ошибок валидации."""

    def test_missing_required_field(self):
        """Тест ошибки при отсутствии обязательного поля."""
        # SaleModel требует "price" и "date"
        data = {"sales": [{"price": "100"}]}  # Отсутствует "date"

        with pytest.raises(ValidationError) as exc_info:
            SalesHistoryResponse(**data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("sales", 0, "date")
        assert errors[0]["type"] == "missing"

    def test_wrong_type_field(self):
        """Тест ошибки при неправильном типе поля."""
        # MarketItemsResponse.objects должен быть list
        data = {"objects": "not_a_list"}  # Строка вместо списка

        with pytest.raises(ValidationError) as exc_info:
            MarketItemsResponse(**data)

        errors = exc_info.value.errors()
        assert any("list" in str(err).lower() for err in errors)


class TestDecimalPrecision:
    """Тесты точности Decimal для финансовых данных."""

    def test_decimal_precision_balance(self):
        """Тест точности Decimal для баланса."""
        data = {"usd": "123456789", "dmc": "0"}  # $1,234,567.89
        response = BalanceResponse(**data)

        balance = response.get_usd_decimal()

        # Проверка точности до 2 знаков после запятой
        assert balance == Decimal("1234567.89")
        assert str(balance) == "1234567.89"

    def test_decimal_precision_small_values(self):
        """Тест точности Decimal для малых значений."""
        # 1 цент = $0.01
        balance1 = BalanceResponse(usd="1", dmc="0")
        assert balance1.get_usd_decimal() == Decimal("0.01")

        # Проверка что не происходит потери точности
        balance3 = BalanceResponse(usd="3", dmc="0")
        small_value = balance3.get_usd_decimal()
        assert small_value == Decimal("0.03")
        assert small_value * 3 == Decimal("0.09")  # Точное умножение

    def test_decimal_no_float_errors(self):
        """Тест отсутствия ошибок округления float."""
        # С float: 0.1 + 0.2 = 0.30000000000000004
        # С Decimal: 0.1 + 0.2 = 0.3

        balance1 = BalanceResponse(usd="10", dmc="0")
        balance2 = BalanceResponse(usd="20", dmc="0")

        price1 = balance1.get_usd_decimal()  # $0.10
        price2 = balance2.get_usd_decimal()  # $0.20

        total = price1 + price2

        assert total == Decimal("0.30")
        # Decimal удаляет trailing zeros: "0.30" -> "0.3"
        assert str(total) == "0.3"  # Без артефактов округления float


class TestBackwardCompatibility:
    """Тесты обратной совместимости с изменениями API."""

    def test_new_fields_in_balance(self):
        """Тест что новые поля в API не ломают валидацию."""
        data = {
            "usd": "10000",
            "dmc": "5000",
            "eur": "9000",  # Новое поле (гипотетически)
            "availableToWithdraw": "8000",  # Новое поле
        }

        # Схема должна принять данные с новыми полями
        response = BalanceResponse(**data)

        assert response.usd == "10000"
        # Новые поля доступны через __dict__ или model_extra
        assert hasattr(response, "eur") or "eur" in response.__dict__

    def test_missing_optional_fields(self):
        """Тест что отсутствие опциональных полей не ломает валидацию."""
        # MarketItemsResponse.cursor опционален
        data = {"objects": []}

        response = MarketItemsResponse(**data)

        assert response.cursor is None
        # total имеет default="0" и validator преобразует в int(0)
        assert response.total == 0
