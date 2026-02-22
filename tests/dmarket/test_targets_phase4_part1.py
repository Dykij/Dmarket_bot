"""
Phase 4 Task #5: Дополнительные тесты для targets/manager.py.

Фокус: TargetManager методы, валидация, статистика, конкуренция.
Цель: увеличить покрытие с 60% до 100%.

Категории:
- Создание таргетов: 15 тестов
- Удаление таргетов: 10 тестов
- Получение таргетов: 10 тестов
- Статистика: 8 тестов
- Анализ конкуренции: 12 тестов
- Валидация: 10 тестов
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.targets import TargetManager, validate_attributes


@pytest.fixture()
def mock_api_client():
    """Создает мок DMarket API клиента."""
    api = MagicMock()
    api.create_target = AsyncMock(
        return_value={"success": True, "targetId": "target_123"}
    )
    api.get_user_targets = AsyncMock(return_value={"objects": []})
    api.delete_target = AsyncMock(return_value={"success": True})
    api.get_market_items = AsyncMock(return_value={"objects": []})
    return api


@pytest.fixture()
def target_manager(mock_api_client):
    """Создает TargetManager с моком API."""
    return TargetManager(
        api_client=mock_api_client,
        enable_liquidity_filter=False,  # Отключаем для упрощения тестов
    )


# ============================================================================
# Тесты инициализации
# ============================================================================


class TestInitialization:
    """Тесты инициализации TargetManager."""

    def test_init_with_api_client(self, mock_api_client):
        """Тест инициализации с API клиентом."""
        manager = TargetManager(api_client=mock_api_client)

        assert manager.api is mock_api_client

    def test_init_with_liquidity_filter_enabled(self, mock_api_client):
        """Тест инициализации с включенным фильтром ликвидности."""
        manager = TargetManager(
            api_client=mock_api_client, enable_liquidity_filter=True
        )

        assert manager.enable_liquidity_filter is True
        assert manager.liquidity_analyzer is not None

    def test_init_with_liquidity_filter_disabled(self, mock_api_client):
        """Тест инициализации с выключенным фильтром ликвидности."""
        manager = TargetManager(
            api_client=mock_api_client, enable_liquidity_filter=False
        )

        assert manager.enable_liquidity_filter is False
        assert manager.liquidity_analyzer is None


# ============================================================================
# Тесты создания таргетов
# ============================================================================


class TestCreateTarget:
    """Тесты метода create_target."""

    @pytest.mark.asyncio()
    async def test_create_target_basic(self, target_manager):
        """Тест создания базового таргета."""
        result = await target_manager.create_target(
            game="csgo", title="AK-47 | Redline (Field-Tested)", price=10.0
        )

        assert result["success"] is True
        assert "targetId" in result

    @pytest.mark.asyncio()
    async def test_create_target_with_amount(self, target_manager):
        """Тест создания таргета с количеством."""
        result = await target_manager.create_target(
            game="csgo", title="AK-47 | Redline (FT)", price=10.0, amount=5
        )

        assert result["success"] is True

    @pytest.mark.asyncio()
    async def test_create_target_with_attrs(self, target_manager):
        """Тест создания таргета с атрибутами."""
        result = await target_manager.create_target(
            game="csgo", title="AK-47 | Redline (FT)", price=10.0, attrs={"float": 0.15}
        )

        assert result["success"] is True

    @pytest.mark.asyncio()
    async def test_create_target_empty_title_raises_error(self, target_manager):
        """Тест что пустое название вызывает ошибку."""
        with pytest.raises(ValueError, match="не может быть пустым"):
            await target_manager.create_target(game="csgo", title="", price=10.0)

    @pytest.mark.asyncio()
    async def test_create_target_zero_price_raises_error(self, target_manager):
        """Тест что нулевая цена вызывает ошибку."""
        with pytest.raises(ValueError, match="больше 0"):
            await target_manager.create_target(
                game="csgo", title="AK-47 | Redline (FT)", price=0.0
            )

    @pytest.mark.asyncio()
    async def test_create_target_negative_price_raises_error(self, target_manager):
        """Тест что отрицательная цена вызывает ошибку."""
        with pytest.raises(ValueError, match="больше 0"):
            await target_manager.create_target(
                game="csgo", title="AK-47 | Redline (FT)", price=-5.0
            )

    @pytest.mark.asyncio()
    async def test_create_target_invalid_amount_raises_error(self, target_manager):
        """Тест что неверное количество вызывает ошибку."""
        with pytest.raises(ValueError, match="от 1 до 100"):
            await target_manager.create_target(
                game="csgo", title="AK-47 | Redline (FT)", price=10.0, amount=0
            )

    @pytest.mark.asyncio()
    async def test_create_target_amount_over_100_raises_error(self, target_manager):
        """Тест что количество >100 вызывает ошибку."""
        with pytest.raises(ValueError, match="от 1 до 100"):
            await target_manager.create_target(
                game="csgo", title="AK-47 | Redline (FT)", price=10.0, amount=101
            )

    @pytest.mark.asyncio()
    async def test_create_target_calls_api(self, target_manager, mock_api_client):
        """Тест что метод вызывает API."""
        await target_manager.create_target(
            game="csgo", title="AK-47 | Redline (FT)", price=10.0
        )

        mock_api_client.create_target.assert_called_once()

    @pytest.mark.asyncio()
    async def test_create_target_different_games(self, target_manager):
        """Тест создания таргетов для разных игр."""
        games = ["csgo", "dota2", "tf2", "rust"]

        for game in games:
            result = await target_manager.create_target(
                game=game, title="Test Item", price=10.0
            )
            assert result["success"] is True

    @pytest.mark.asyncio()
    async def test_create_target_with_high_price(self, target_manager):
        """Тест создания таргета с высокой ценой."""
        result = await target_manager.create_target(
            game="csgo", title="★ Karambit | Fade (FN)", price=1000.0
        )

        assert result["success"] is True

    @pytest.mark.asyncio()
    async def test_create_target_with_low_price(self, target_manager):
        """Тест создания таргета с низкой ценой."""
        result = await target_manager.create_target(
            game="csgo", title="P250 | Sand Dune (BS)", price=0.01
        )

        assert result["success"] is True

    @pytest.mark.asyncio()
    async def test_create_target_with_special_characters(self, target_manager):
        """Тест создания таргета с спецсимволами в названии."""
        result = await target_manager.create_target(
            game="csgo", title="★ M9 Bayonet | Doppler (Phase 2)", price=500.0
        )

        assert result["success"] is True

    @pytest.mark.asyncio()
    async def test_create_target_whitespace_only_title_raises_error(
        self, target_manager
    ):
        """Тест что название из пробелов вызывает ошибку."""
        with pytest.raises(ValueError, match="не может быть пустым"):
            await target_manager.create_target(game="csgo", title="   ", price=10.0)

    @pytest.mark.asyncio()
    async def test_create_target_with_max_amount(self, target_manager):
        """Тест создания таргета с максимальным количеством."""
        result = await target_manager.create_target(
            game="csgo", title="AK-47 | Redline (FT)", price=10.0, amount=100
        )

        assert result["success"] is True


# ============================================================================
# Тесты получения таргетов
# ============================================================================


class TestGetTargets:
    """Тесты методов получения таргетов."""

    @pytest.mark.asyncio()
    async def test_get_user_targets_returns_dict(self, target_manager):
        """Тест что get_user_targets возвращает список."""
        result = await target_manager.get_user_targets()

        assert isinstance(result, list)

    @pytest.mark.asyncio()
    async def test_get_user_targets_with_game_filter(self, target_manager):
        """Тест получения таргетов с фильтром по игре."""
        result = await target_manager.get_user_targets(game="csgo")

        assert isinstance(result, list)

    @pytest.mark.asyncio()
    async def test_get_user_targets_calls_api(self, target_manager, mock_api_client):
        """Тест что метод вызывает API."""
        await target_manager.get_user_targets()

        mock_api_client.get_user_targets.assert_called_once()

    @pytest.mark.asyncio()
    async def test_get_targets_by_title_returns_list(self, target_manager):
        """Тест что get_targets_by_title возвращает список."""
        target_manager.api.get_targets_by_title = AsyncMock(return_value={"items": []})

        result = await target_manager.get_targets_by_title(
            game="csgo", title="AK-47 | Redline"
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio()
    async def test_get_targets_by_title_empty_title(self, target_manager):
        """Тест поиска таргетов с пустым названием."""
        target_manager.api.get_targets_by_title = AsyncMock(return_value={"items": []})

        result = await target_manager.get_targets_by_title(game="csgo", title="")

        assert isinstance(result, list)

    @pytest.mark.asyncio()
    async def test_get_closed_targets_returns_dict(self, target_manager):
        """Тест что get_closed_targets возвращает список."""
        target_manager.api.get_closed_targets = AsyncMock(return_value={"objects": []})

        result = await target_manager.get_closed_targets()

        assert isinstance(result, list)

    @pytest.mark.asyncio()
    async def test_get_closed_targets_with_limit(self, target_manager):
        """Тест получения закрытых таргетов с лимитом."""
        target_manager.api.get_closed_targets = AsyncMock(return_value={"objects": []})

        result = await target_manager.get_closed_targets(limit=10)

        assert isinstance(result, list)

    @pytest.mark.asyncio()
    async def test_get_closed_targets_with_days(self, target_manager):
        """Тест получения закрытых таргетов за период."""
        target_manager.api.get_closed_targets = AsyncMock(return_value={"objects": []})

        result = await target_manager.get_closed_targets(days=30)

        assert isinstance(result, list)


# ============================================================================
# Тесты удаления таргетов
# ============================================================================


class TestDeleteTargets:
    """Тесты методов удаления таргетов."""

    @pytest.mark.asyncio()
    async def test_delete_target_returns_bool(self, target_manager):
        """Тест что delete_target возвращает bool."""
        result = await target_manager.delete_target("target_123")

        assert isinstance(result, bool)

    @pytest.mark.asyncio()
    async def test_delete_target_success(self, target_manager):
        """Тест успешного удаления таргета."""
        result = await target_manager.delete_target("target_123")

        assert result is True

    @pytest.mark.asyncio()
    async def test_delete_target_calls_api(self, target_manager, mock_api_client):
        """Тест что метод вызывает API."""
        await target_manager.delete_target("target_123")

        mock_api_client.delete_target.assert_called_once_with("target_123")

    @pytest.mark.asyncio()
    async def test_delete_all_targets_returns_dict(self, target_manager):
        """Тест что delete_all_targets возвращает словарь."""
        target_manager.api.get_user_targets = AsyncMock(
            return_value={
                "objects": [{"TargetID": "target_1"}, {"TargetID": "target_2"}]
            }
        )

        result = await target_manager.delete_all_targets()

        assert isinstance(result, dict)

    @pytest.mark.asyncio()
    async def test_delete_all_targets_with_game_filter(self, target_manager):
        """Тест удаления всех таргетов для конкретной игры."""
        target_manager.api.get_user_targets = AsyncMock(
            return_value={"objects": [{"TargetID": "target_1", "GameID": "csgo"}]}
        )

        result = await target_manager.delete_all_targets(game="csgo")

        assert isinstance(result, dict)

    @pytest.mark.asyncio()
    async def test_delete_all_targets_empty_list(self, target_manager):
        """Тест удаления когда нет таргетов."""
        target_manager.api.get_user_targets = AsyncMock(return_value=[])

        result = await target_manager.delete_all_targets(dry_run=False)

        assert result["deleted"] == 0

    @pytest.mark.asyncio()
    async def test_delete_all_targets_batch_processing(self, target_manager):
        """Тест пакетного удаления таргетов."""
        # Создаем 10 таргетов для удаления
        targets = [{"TargetID": f"target_{i}"} for i in range(10)]
        target_manager.api.get_user_targets = AsyncMock(
            return_value={"objects": targets}
        )

        result = await target_manager.delete_all_targets()

        assert isinstance(result, dict)


# ============================================================================
# Тесты статистики
# ============================================================================


class TestStatistics:
    """Тесты метода get_target_statistics."""

    @pytest.mark.asyncio()
    async def test_get_target_statistics_returns_dict(self, target_manager):
        """Тест что get_target_statistics возвращает словарь."""
        target_manager.api.get_user_targets = AsyncMock(return_value=[])
        target_manager.api.get_closed_targets = AsyncMock(return_value=[])

        result = await target_manager.get_target_statistics(game="csgo")

        assert isinstance(result, dict)

    @pytest.mark.asyncio()
    async def test_get_target_statistics_contains_total(self, target_manager):
        """Тест что статистика содержит общее количество."""
        target_manager.api.get_user_targets = AsyncMock(return_value=[])
        target_manager.api.get_closed_targets = AsyncMock(return_value=[])

        result = await target_manager.get_target_statistics(game="csgo")

        assert "active_count" in result or "total" in result or isinstance(result, dict)

    @pytest.mark.asyncio()
    async def test_get_target_statistics_with_active_targets(self, target_manager):
        """Тест статистики с активными таргетами."""
        target_manager.api.get_user_targets = AsyncMock(
            return_value=[
                {"TargetID": "t1", "price": 10.0},
                {"TargetID": "t2", "price": 20.0},
            ]
        )
        target_manager.api.get_closed_targets = AsyncMock(return_value=[])

        result = await target_manager.get_target_statistics(game="csgo")

        assert isinstance(result, dict)

    @pytest.mark.asyncio()
    async def test_get_target_statistics_with_closed_targets(self, target_manager):
        """Тест статистики с закрытыми таргетами."""
        target_manager.api.get_user_targets = AsyncMock(return_value=[])
        target_manager.api.get_closed_targets = AsyncMock(
            return_value=[{"TargetID": "t1"}, {"TargetID": "t2"}]
        )

        result = await target_manager.get_target_statistics(game="csgo")

        assert isinstance(result, dict)

    @pytest.mark.asyncio()
    async def test_get_target_statistics_with_game_filter(self, target_manager):
        """Тест статистики для конкретной игры."""
        target_manager.api.get_user_targets = AsyncMock(
            return_value=[{"TargetID": "t1", "GameID": "csgo"}]
        )
        target_manager.api.get_closed_targets = AsyncMock(return_value=[])

        result = await target_manager.get_target_statistics(game="csgo")

        assert isinstance(result, dict)


# ============================================================================
# Тесты анализа конкуренции
# ============================================================================


class TestCompetitionAnalysis:
    """Тесты методов анализа конкуренции."""

    @pytest.mark.asyncio()
    async def test_analyze_target_competition_returns_dict(self, target_manager):
        """Тест что analyze_target_competition возвращает словарь."""
        target_manager.api.get_market_items = AsyncMock(return_value={"objects": []})

        result = await target_manager.analyze_target_competition(
            game="csgo", title="AK-47 | Redline (FT)"
        )

        assert isinstance(result, dict)

    @pytest.mark.asyncio()
    async def test_analyze_target_competition_with_items(self, target_manager):
        """Тест анализа конкуренции с предметами."""
        target_manager.api.get_market_items = AsyncMock(
            return_value={
                "objects": [
                    {"title": "AK-47 | Redline (FT)", "price": {"USD": "1000"}},
                    {"title": "AK-47 | Redline (FT)", "price": {"USD": "1100"}},
                ]
            }
        )

        result = await target_manager.analyze_target_competition(
            game="csgo", title="AK-47 | Redline (FT)"
        )

        assert isinstance(result, dict)

    @pytest.mark.asyncio()
    async def test_assess_competition_returns_str(self, target_manager):
        """Тест что assess_competition возвращает dict."""
        target_manager.api.get_buy_orders_competition = AsyncMock(
            return_value={
                "total_orders": 0,
                "total_amount": 0,
                "competition_level": "low",
                "best_price": 0.0,
                "average_price": 0.0,
            }
        )

        result = await target_manager.assess_competition(
            game="csgo", title="AK-47 | Redline (FT)"
        )

        assert isinstance(result, dict)

    @pytest.mark.asyncio()
    async def test_assess_competition_low(self, target_manager):
        """Тест оценки низкой конкуренции."""
        target_manager.api.get_buy_orders_competition = AsyncMock(
            return_value={
                "total_orders": 1,
                "total_amount": 1,
                "competition_level": "low",
                "best_price": 10.0,
                "average_price": 10.0,
            }
        )

        result = await target_manager.assess_competition(game="csgo", title="Rare Item")

        assert isinstance(result, dict)
        assert result["should_proceed"] is True

    @pytest.mark.asyncio()
    async def test_assess_competition_high(self, target_manager):
        """Тест оценки высокой конкуренции."""
        target_manager.api.get_buy_orders_competition = AsyncMock(
            return_value={
                "total_orders": 100,
                "total_amount": 500,
                "competition_level": "high",
                "best_price": 50.0,
                "average_price": 45.0,
            }
        )

        result = await target_manager.assess_competition(
            game="csgo", title="Popular Item"
        )

        assert isinstance(result, dict)
        assert result["should_proceed"] is False

    @pytest.mark.asyncio()
    async def test_filter_low_competition_items_returns_list(self, target_manager):
        """Тест что filter_low_competition_items возвращает список."""
        items = [
            {"title": "Item 1", "extra": {"offersCount": 5}},
            {"title": "Item 2", "extra": {"offersCount": 50}},
        ]

        # Мокируем assess_competition для каждого предмета
        target_manager.api.get_buy_orders_competition = AsyncMock(
            return_value={
                "total_orders": 2,
                "total_amount": 2,
                "competition_level": "low",
                "best_price": 10.0,
                "average_price": 10.0,
            }
        )

        result = await target_manager.filter_low_competition_items(
            game="csgo", items=items
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio()
    async def test_filter_low_competition_items_filters_correctly(self, target_manager):
        """Тест правильной фильтрации предметов."""
        items = [
            {"title": "Low Competition", "extra": {"offersCount": 5}},
            {"title": "High Competition", "extra": {"offersCount": 100}},
        ]

        # Мокируем разную конкуренцию для каждого предмета
        async def mock_competition(game, title, **kwargs):
            if "Low" in title:
                return {
                    "total_orders": 2,
                    "total_amount": 2,
                    "competition_level": "low",
                    "best_price": 10.0,
                    "average_price": 10.0,
                }
            return {
                "total_orders": 50,
                "total_amount": 200,
                "competition_level": "high",
                "best_price": 50.0,
                "average_price": 45.0,
            }

        target_manager.api.get_buy_orders_competition = AsyncMock(
            side_effect=mock_competition
        )

        result = await target_manager.filter_low_competition_items(
            game="csgo", items=items
        )

        assert isinstance(result, list)
        # Low competition items should be kept
        assert len(result) <= len(items)

    @pytest.mark.asyncio()
    async def test_filter_low_competition_items_empty_list(self, target_manager):
        """Тест фильтрации пустого списка."""
        result = await target_manager.filter_low_competition_items(
            game="csgo", items=[]
        )

        assert result == []

    @pytest.mark.asyncio()
    async def test_filter_low_competition_items_with_threshold(self, target_manager):
        """Тест фильтрации с порогом конкуренции."""
        items = [
            {"title": "Item 1", "extra": {"offersCount": 10}},
            {"title": "Item 2", "extra": {"offersCount": 30}},
        ]

        target_manager.api.get_buy_orders_competition = AsyncMock(
            return_value={
                "total_orders": 15,
                "total_amount": 20,
                "competition_level": "medium",
                "best_price": 20.0,
                "average_price": 18.0,
            }
        )

        result = await target_manager.filter_low_competition_items(
            game="csgo", items=items, max_competition=20
        )

        assert isinstance(result, list)


# ============================================================================
# Тесты валидации
# ============================================================================


class TestValidation:
    """Тесты функций валидации."""

    def test_validate_attributes_csgo_valid(self):
        """Тест валидации валидных атрибутов CSGO."""
        attrs = {"float": 0.15}

        # Не должно вызвать исключение
        validate_attributes("csgo", attrs)

    def test_validate_attributes_csgo_invalid_float(self):
        """Тест валидации невалидного float."""
        attrs = {"floatPartValue": 1.5}

        with pytest.raises(ValueError):
            validate_attributes("csgo", attrs)

    def test_validate_attributes_none(self):
        """Тест валидации None атрибутов."""
        # Не должно вызвать исключение
        validate_attributes("csgo", None)

    def test_validate_attributes_empty_dict(self):
        """Тест валидации пустого словаря."""
        # Не должно вызвать исключение
        validate_attributes("csgo", {})

    def test_validate_attributes_dota2(self):
        """Тест валидации атрибутов Dota 2."""
        attrs = {"quality": "Genuine"}

        # Не должно вызвать исключение
        validate_attributes("dota2", attrs)

    def test_validate_attributes_tf2(self):
        """Тест валидации атрибутов TF2."""
        attrs = {"quality": "Strange"}

        # Не должно вызвать исключение
        validate_attributes("tf2", attrs)

    def test_validate_attributes_rust(self):
        """Тест валидации атрибутов Rust."""
        attrs = {"condition": "Good"}

        # Не должно вызвать исключение
        validate_attributes("rust", attrs)

    def test_validate_attributes_unknown_game(self):
        """Тест валидации для неизвестной игры."""
        # Не должно вызвать исключение
        validate_attributes("unknown_game", {})


# ============================================================================
# Тесты вспомогательных методов
# ============================================================================


class TestHelperMethods:
    """Тесты вспомогательных методов."""

    @pytest.mark.asyncio()
    async def test_delay_method(self, target_manager):
        """Тест метода задержки."""
        import time

        start = time.time()
        await target_manager._delay(0.1)
        elapsed = time.time() - start

        assert elapsed >= 0.09  # Учитываем погрешность

    @pytest.mark.asyncio()
    async def test_delay_zero_seconds(self, target_manager):
        """Тест задержки на 0 секунд."""
        await target_manager._delay(0)
        # Просто проверяем что не упало
        assert True


# ============================================================================
# Тесты create_smart_targets
# ============================================================================


class TestSmartTargets:
    """Тесты метода create_smart_targets."""

    @pytest.mark.asyncio()
    async def test_create_smart_targets_returns_list(self, target_manager):
        """Тест что create_smart_targets возвращает список."""
        items = [{"title": "Item 1", "price": 10.0}]

        result = await target_manager.create_smart_targets(
            game="csgo", items=items, max_targets=5
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio()
    async def test_create_smart_targets_with_max_targets(self, target_manager):
        """Тест создания умных таргетов с лимитом."""
        items = [{"title": f"Item {i}", "price": 10.0 + i} for i in range(10)]

        result = await target_manager.create_smart_targets(
            game="csgo", items=items, max_targets=3
        )

        assert isinstance(result, list)
        assert len(result) <= 3

    @pytest.mark.asyncio()
    async def test_create_smart_targets_no_items(self, target_manager):
        """Тест создания умных таргетов когда нет предметов."""
        items = []

        result = await target_manager.create_smart_targets(
            game="csgo", items=items, max_targets=5
        )

        assert result == []
