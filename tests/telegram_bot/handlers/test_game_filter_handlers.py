"""Тесты для обработчика фильтров игровых предметов."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import CallbackQuery, InlineKeyboardMarkup, Update, User
from telegram.constants import ParseMode

from src.telegram_bot.handlers.game_filter_handlers import (
    CS2_CATEGORIES,
    CS2_EXTERIORS,
    CS2_RARITIES,
    DEFAULT_FILTERS,
    DOTA2_HEROES,
    DOTA2_RARITIES,
    DOTA2_SLOTS,
    RUST_CATEGORIES,
    RUST_RARITIES,
    RUST_TYPES,
    TF2_CLASSES,
    TF2_QUALITIES,
    TF2_TYPES,
    build_api_params_for_game,
    get_current_filters,
    get_filter_description,
    get_game_filter_keyboard,
    handle_game_filters,
    handle_price_range_callback,
    handle_select_game_filter_callback,
    update_filters,
)

# ======================== Fixtures ========================


@pytest.fixture()
def mock_user():
    """Создать мок объекта User."""
    user = MagicMock(spec=User)
    user.id = 123456789
    user.username = "testuser"
    user.first_name = "Test"
    return user


@pytest.fixture()
def mock_message(mock_user):
    """Создать мок объекта Message."""
    message = MagicMock()
    message.reply_text = AsyncMock()
    message.from_user = mock_user
    return message


@pytest.fixture()
def mock_callback_query(mock_user):
    """Создать мок объекта CallbackQuery."""
    query = MagicMock(spec=CallbackQuery)
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = "select_game_filter:csgo"
    query.from_user = mock_user
    return query


@pytest.fixture()
def mock_update(mock_user, mock_callback_query, mock_message):
    """Создать мок объекта Update."""
    update = MagicMock(spec=Update)
    update.callback_query = mock_callback_query
    update.effective_user = mock_user
    update.message = mock_message
    update.effective_chat = MagicMock()
    update.effective_chat.id = 123456789
    return update


@pytest.fixture()
def mock_context():
    """Создать мок объекта CallbackContext."""
    context = MagicMock()
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {}
    context.chat_data = {}
    return context


# ======================== Constants Tests ========================


class TestConstants:
    """Тесты для констант модуля."""

    def test_cs2_categories_not_empty(self):
        """CS2 категории должны быть непустыми."""
        assert len(CS2_CATEGORIES) > 0

    def test_cs2_categories_contains_expected(self):
        """CS2 категории должны содержать ожидаемые элементы."""
        expected = ["Pistol", "Rifle", "Knife", "Gloves"]
        for item in expected:
            assert item in CS2_CATEGORIES

    def test_cs2_rarities_not_empty(self):
        """CS2 редкости должны быть непустыми."""
        assert len(CS2_RARITIES) > 0

    def test_cs2_rarities_in_order(self):
        """CS2 редкости должны быть в порядке возрастания."""
        expected_order = [
            "Consumer Grade",
            "Industrial Grade",
            "Mil-Spec Grade",
            "Restricted",
            "Classified",
            "Covert",
            "Contraband",
        ]
        assert expected_order == CS2_RARITIES

    def test_cs2_exteriors_count(self):
        """CS2 внешний вид должен содержать 5 вариантов."""
        assert len(CS2_EXTERIORS) == 5

    def test_cs2_exteriors_contains_expected(self):
        """CS2 внешний вид должен содержать ожидаемые элементы."""
        expected = [
            "Factory New",
            "Minimal Wear",
            "Field-Tested",
            "Well-Worn",
            "Battle-Scarred",
        ]
        assert expected == CS2_EXTERIORS

    def test_dota2_heroes_not_empty(self):
        """Dota 2 герои должны быть непустыми."""
        assert len(DOTA2_HEROES) > 0

    def test_dota2_heroes_contains_expected(self):
        """Dota 2 герои должны содержать популярных героев."""
        expected = ["Axe", "Pudge", "Invoker"]
        for hero in expected:
            assert hero in DOTA2_HEROES

    def test_dota2_rarities_hierarchy(self):
        """Dota 2 редкости должны быть в иерархии."""
        expected = [
            "Common",
            "Uncommon",
            "Rare",
            "Mythical",
            "Legendary",
            "Immortal",
            "Arcana",
        ]
        assert expected == DOTA2_RARITIES

    def test_dota2_slots_not_empty(self):
        """Dota 2 слоты должны быть непустыми."""
        assert len(DOTA2_SLOTS) > 0

    def test_tf2_classes_count(self):
        """TF2 классы должны содержать 10 вариантов."""
        assert len(TF2_CLASSES) == 10

    def test_tf2_classes_contains_expected(self):
        """TF2 классы должны содержать все 9 классов + All Classes."""
        expected = [
            "Scout",
            "Soldier",
            "Pyro",
            "Demoman",
            "Heavy",
            "Engineer",
            "Medic",
            "Sniper",
            "Spy",
        ]
        for cls in expected:
            assert cls in TF2_CLASSES
        assert "All Classes" in TF2_CLASSES

    def test_tf2_qualities_not_empty(self):
        """TF2 качества должны быть непустыми."""
        assert len(TF2_QUALITIES) > 0

    def test_tf2_types_not_empty(self):
        """TF2 типы должны быть непустыми."""
        assert len(TF2_TYPES) > 0

    def test_rust_categories_not_empty(self):
        """Rust категории должны быть непустыми."""
        assert len(RUST_CATEGORIES) > 0

    def test_rust_types_not_empty(self):
        """Rust типы должны быть непустыми."""
        assert len(RUST_TYPES) > 0

    def test_rust_rarities_hierarchy(self):
        """Rust редкости должны быть в иерархии."""
        expected = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]
        assert expected == RUST_RARITIES


class TestDefaultFilters:
    """Тесты для фильтров по умолчанию."""

    def test_default_filters_contains_all_games(self):
        """Фильтры по умолчанию должны содержать все игры."""
        expected_games = ["csgo", "dota2", "tf2", "rust"]
        for game in expected_games:
            assert game in DEFAULT_FILTERS

    def test_csgo_default_filters(self):
        """CSGO фильтры по умолчанию должны иметь правильную структуру."""
        csgo_filters = DEFAULT_FILTERS["csgo"]
        assert "min_price" in csgo_filters
        assert "max_price" in csgo_filters
        assert "float_min" in csgo_filters
        assert "float_max" in csgo_filters
        assert csgo_filters["min_price"] == 1.0
        assert csgo_filters["max_price"] == 1000.0
        assert csgo_filters["float_min"] == 0.0
        assert csgo_filters["float_max"] == 1.0

    def test_dota2_default_filters(self):
        """Dota 2 фильтры по умолчанию должны иметь правильную структуру."""
        dota2_filters = DEFAULT_FILTERS["dota2"]
        assert "min_price" in dota2_filters
        assert "max_price" in dota2_filters
        assert "hero" in dota2_filters
        assert "tradable" in dota2_filters
        assert dota2_filters["tradable"] is True

    def test_tf2_default_filters(self):
        """TF2 фильтры по умолчанию должны иметь правильную структуру."""
        tf2_filters = DEFAULT_FILTERS["tf2"]
        assert "min_price" in tf2_filters
        assert "class" in tf2_filters
        assert "australium" in tf2_filters
        assert tf2_filters["australium"] is False

    def test_rust_default_filters(self):
        """Rust фильтры по умолчанию должны иметь правильную структуру."""
        rust_filters = DEFAULT_FILTERS["rust"]
        assert "min_price" in rust_filters
        assert "category" in rust_filters
        assert "rarity" in rust_filters


# ======================== get_current_filters Tests ========================


class TestGetCurrentFilters:
    """Тесты для функции get_current_filters."""

    def test_returns_default_filters_when_no_user_data(self, mock_context):
        """Должен возвращать фильтры по умолчанию если нет user_data."""
        mock_context.user_data = None
        result = get_current_filters(mock_context, "csgo")
        assert result == DEFAULT_FILTERS["csgo"]

    def test_returns_default_filters_when_empty_user_data(self, mock_context):
        """Должен возвращать фильтры по умолчанию если user_data пустой."""
        mock_context.user_data = {}
        result = get_current_filters(mock_context, "csgo")
        assert result == DEFAULT_FILTERS["csgo"]

    def test_returns_stored_filters_when_present(self, mock_context):
        """Должен возвращать сохраненные фильтры если они есть."""
        custom_filters = {"min_price": 10.0, "max_price": 500.0}
        mock_context.user_data = {"filters": {"csgo": custom_filters}}
        result = get_current_filters(mock_context, "csgo")
        assert result == custom_filters

    def test_returns_default_for_unknown_game_in_context(self, mock_context):
        """Должен возвращать фильтры по умолчанию для другой игры."""
        mock_context.user_data = {"filters": {"csgo": {"min_price": 10.0}}}
        result = get_current_filters(mock_context, "dota2")
        assert result == DEFAULT_FILTERS["dota2"]

    def test_returns_copy_not_reference(self, mock_context):
        """Должен возвращать копию фильтров, а не ссылку."""
        mock_context.user_data = None
        result1 = get_current_filters(mock_context, "csgo")
        result2 = get_current_filters(mock_context, "csgo")
        result1["min_price"] = 999.0
        assert result2["min_price"] != 999.0


# ======================== update_filters Tests ========================


class TestUpdateFilters:
    """Тесты для функции update_filters."""

    def test_updates_filters_in_empty_user_data(self, mock_context):
        """Должен создавать фильтры если user_data пустой."""
        mock_context.user_data = {}
        new_filters = {"min_price": 50.0, "max_price": 200.0}
        update_filters(mock_context, "csgo", new_filters)
        assert mock_context.user_data["filters"]["csgo"] == new_filters

    def test_updates_existing_filters(self, mock_context):
        """Должен обновлять существующие фильтры."""
        mock_context.user_data = {"filters": {"csgo": {"min_price": 1.0}}}
        new_filters = {"min_price": 50.0, "max_price": 200.0}
        update_filters(mock_context, "csgo", new_filters)
        assert mock_context.user_data["filters"]["csgo"] == new_filters

    def test_preserves_other_game_filters(self, mock_context):
        """Должен сохранять фильтры других игр."""
        dota_filters = {"hero": "Axe"}
        mock_context.user_data = {"filters": {"dota2": dota_filters}}
        update_filters(mock_context, "csgo", {"min_price": 10.0})
        assert mock_context.user_data["filters"]["dota2"] == dota_filters

    def test_creates_user_data_if_none(self, mock_context):
        """Должен создавать user_data если его нет."""
        mock_context.user_data = None
        update_filters(mock_context, "csgo", {"min_price": 10.0})
        assert mock_context.user_data is not None
        assert "filters" in mock_context.user_data


# ======================== get_game_filter_keyboard Tests ========================


class TestGetGameFilterKeyboard:
    """Тесты для функции get_game_filter_keyboard."""

    def test_returns_inline_keyboard_markup(self):
        """Должен возвращать InlineKeyboardMarkup."""
        result = get_game_filter_keyboard("csgo")
        assert isinstance(result, InlineKeyboardMarkup)

    def test_csgo_keyboard_has_price_range(self):
        """CSGO клавиатура должна иметь диапазон цен."""
        result = get_game_filter_keyboard("csgo")
        button_texts = [btn.text for row in result.inline_keyboard for btn in row]
        assert "💰 Диапазон цен" in button_texts

    def test_csgo_keyboard_has_float_range(self):
        """CSGO клавиатура должна иметь диапазон Float."""
        result = get_game_filter_keyboard("csgo")
        button_texts = [btn.text for row in result.inline_keyboard for btn in row]
        assert "🔢 Диапазон Float" in button_texts

    def test_csgo_keyboard_has_stattrak(self):
        """CSGO клавиатура должна иметь StatTrak."""
        result = get_game_filter_keyboard("csgo")
        button_texts = [btn.text for row in result.inline_keyboard for btn in row]
        assert "🔢 StatTrak™" in button_texts

    def test_dota2_keyboard_has_hero(self):
        """Dota 2 клавиатура должна иметь выбор героя."""
        result = get_game_filter_keyboard("dota2")
        button_texts = [btn.text for row in result.inline_keyboard for btn in row]
        assert "🦸 ГеSwarm" in button_texts

    def test_dota2_keyboard_has_slot(self):
        """Dota 2 клавиатура должна иметь выбор слота."""
        result = get_game_filter_keyboard("dota2")
        button_texts = [btn.text for row in result.inline_keyboard for btn in row]
        assert "🧩 Слот" in button_texts

    def test_tf2_keyboard_has_class(self):
        """TF2 клавиатура должна иметь выбор класса."""
        result = get_game_filter_keyboard("tf2")
        button_texts = [btn.text for row in result.inline_keyboard for btn in row]
        assert "👤 Класс" in button_texts

    def test_tf2_keyboard_has_australium(self):
        """TF2 клавиатура должна иметь Australium."""
        result = get_game_filter_keyboard("tf2")
        button_texts = [btn.text for row in result.inline_keyboard for btn in row]
        assert "🔶 Australium" in button_texts

    def test_rust_keyboard_has_category(self):
        """Rust клавиатура должна иметь категорию."""
        result = get_game_filter_keyboard("rust")
        button_texts = [btn.text for row in result.inline_keyboard for btn in row]
        assert "🔫 Категория" in button_texts

    def test_all_keyboards_have_reset_button(self):
        """Все клавиатуры должны иметь кнопку сброса."""
        for game in ["csgo", "dota2", "tf2", "rust"]:
            result = get_game_filter_keyboard(game)
            button_texts = [btn.text for row in result.inline_keyboard for btn in row]
            assert "🔄 Сбросить фильтры" in button_texts

    def test_all_keyboards_have_back_button(self):
        """Все клавиатуры должны иметь кнопку назад."""
        for game in ["csgo", "dota2", "tf2", "rust"]:
            result = get_game_filter_keyboard(game)
            button_texts = [btn.text for row in result.inline_keyboard for btn in row]
            assert "⬅️ Назад" in button_texts


# ======================== get_filter_description Tests ========================


class TestGetFilterDescription:
    """Тесты для функции get_filter_description."""

    @patch("src.telegram_bot.handlers.game_filter_handlers.FilterFactory")
    def test_calls_filter_factory(self, mock_factory):
        """Должен вызывать FilterFactory для получения описания."""
        mock_filter = MagicMock()
        mock_filter.get_filter_description.return_value = "Test description"
        mock_factory.get_filter.return_value = mock_filter

        result = get_filter_description("csgo", {"min_price": 10.0})

        mock_factory.get_filter.assert_called_once_with("csgo")
        mock_filter.get_filter_description.assert_called_once()
        assert result == "Test description"

    @patch("src.telegram_bot.handlers.game_filter_handlers.FilterFactory")
    def test_passes_filters_to_factory(self, mock_factory):
        """Должен передавать фильтры в FilterFactory."""
        mock_filter = MagicMock()
        mock_filter.get_filter_description.return_value = ""
        mock_factory.get_filter.return_value = mock_filter

        filters = {"min_price": 100.0, "max_price": 500.0}
        get_filter_description("dota2", filters)

        mock_filter.get_filter_description.assert_called_once_with(filters)


# ======================== build_api_params_for_game Tests ========================


class TestBuildApiParamsForGame:
    """Тесты для функции build_api_params_for_game."""

    @patch("src.telegram_bot.handlers.game_filter_handlers.FilterFactory")
    def test_calls_filter_factory(self, mock_factory):
        """Должен вызывать FilterFactory для построения параметров."""
        mock_filter = MagicMock()
        mock_filter.build_api_params.return_value = {"price_from": 100}
        mock_factory.get_filter.return_value = mock_filter

        result = build_api_params_for_game("csgo", {"min_price": 100.0})

        mock_factory.get_filter.assert_called_once_with("csgo")
        assert result == {"price_from": 100}

    @patch("src.telegram_bot.handlers.game_filter_handlers.FilterFactory")
    def test_passes_filters_to_factory(self, mock_factory):
        """Должен передавать фильтры в FilterFactory."""
        mock_filter = MagicMock()
        mock_filter.build_api_params.return_value = {}
        mock_factory.get_filter.return_value = mock_filter

        filters = {"min_price": 100.0, "rarity": "Rare"}
        build_api_params_for_game("tf2", filters)

        mock_filter.build_api_params.assert_called_once_with(filters)


# ======================== handle_game_filters Tests ========================


class TestHandleGameFilters:
    """Тесты для функции handle_game_filters."""

    @pytest.mark.asyncio()
    async def test_returns_none_if_no_message(self, mock_update, mock_context):
        """Должен возвращать None если нет сообщения."""
        mock_update.message = None
        result = await handle_game_filters(mock_update, mock_context)
        assert result is None

    @pytest.mark.asyncio()
    async def test_sends_game_selection_keyboard(self, mock_update, mock_context):
        """Должен отправлять клавиатуру выбора игры."""
        await handle_game_filters(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_keyboard_contains_all_games(self, mock_update, mock_context):
        """Клавиатура должна содержать все игры."""
        await handle_game_filters(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        reply_markup = call_args.kwargs.get("reply_markup") or call_args[1].get(
            "reply_markup"
        )

        button_texts = [btn.text for row in reply_markup.inline_keyboard for btn in row]
        assert "🎮 CS2" in button_texts
        assert "🎮 Dota 2" in button_texts
        assert "🎮 TF2" in button_texts
        assert "🎮 Rust" in button_texts

    @pytest.mark.asyncio()
    async def test_keyboard_contains_back_button(self, mock_update, mock_context):
        """Клавиатура должна содержать кнопку назад."""
        await handle_game_filters(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        reply_markup = call_args.kwargs.get("reply_markup") or call_args[1].get(
            "reply_markup"
        )

        button_texts = [btn.text for row in reply_markup.inline_keyboard for btn in row]
        assert "⬅️ Назад" in button_texts


# ======================== handle_select_game_filter_callback Tests ========================


class TestHandleSelectGameFilterCallback:
    """Тесты для функции handle_select_game_filter_callback."""

    @pytest.mark.asyncio()
    async def test_returns_none_if_no_query(self, mock_update, mock_context):
        """Должен возвращать None если нет callback_query."""
        mock_update.callback_query = None
        result = await handle_select_game_filter_callback(mock_update, mock_context)
        assert result is None

    @pytest.mark.asyncio()
    async def test_returns_none_if_no_query_data(self, mock_update, mock_context):
        """Должен возвращать None если нет данных в callback_query."""
        mock_update.callback_query.data = None
        result = await handle_select_game_filter_callback(mock_update, mock_context)
        assert result is None

    @pytest.mark.asyncio()
    async def test_answers_callback_query(self, mock_update, mock_context):
        """Должен отвечать на callback_query."""
        mock_update.callback_query.data = "select_game_filter:csgo"
        with patch(
            "src.telegram_bot.handlers.game_filter_handlers.FilterFactory"
        ) as mock_factory:
            mock_filter = MagicMock()
            mock_filter.get_filter_description.return_value = ""
            mock_factory.get_filter.return_value = mock_filter

            await handle_select_game_filter_callback(mock_update, mock_context)

            mock_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio()
    async def test_edits_message_with_filter_keyboard(self, mock_update, mock_context):
        """Должен редактировать сообщение с клавиатуSwarm фильтров."""
        mock_update.callback_query.data = "select_game_filter:csgo"
        with patch(
            "src.telegram_bot.handlers.game_filter_handlers.FilterFactory"
        ) as mock_factory:
            mock_filter = MagicMock()
            mock_filter.get_filter_description.return_value = ""
            mock_factory.get_filter.return_value = mock_filter

            await handle_select_game_filter_callback(mock_update, mock_context)

            mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_extracts_game_from_callback_data(self, mock_update, mock_context):
        """Должен извлекать игру из callback_data."""
        mock_update.callback_query.data = "select_game_filter:dota2"
        with patch(
            "src.telegram_bot.handlers.game_filter_handlers.FilterFactory"
        ) as mock_factory:
            mock_filter = MagicMock()
            mock_filter.get_filter_description.return_value = ""
            mock_factory.get_filter.return_value = mock_filter

            await handle_select_game_filter_callback(mock_update, mock_context)

            # Проверяем что FilterFactory вызван с правильной игSwarm
            mock_factory.get_filter.assert_called_with("dota2")

    @pytest.mark.asyncio()
    async def test_uses_html_parse_mode(self, mock_update, mock_context):
        """Должен использовать HTML parse mode."""
        mock_update.callback_query.data = "select_game_filter:csgo"
        with patch(
            "src.telegram_bot.handlers.game_filter_handlers.FilterFactory"
        ) as mock_factory:
            mock_filter = MagicMock()
            mock_filter.get_filter_description.return_value = ""
            mock_factory.get_filter.return_value = mock_filter

            await handle_select_game_filter_callback(mock_update, mock_context)

            call_args = mock_update.callback_query.edit_message_text.call_args
            assert call_args.kwargs.get("parse_mode") == ParseMode.HTML


# ======================== handle_price_range_callback Tests ========================


class TestHandlePriceRangeCallback:
    """Тесты для функции handle_price_range_callback."""

    @pytest.mark.asyncio()
    async def test_returns_none_if_no_query(self, mock_update, mock_context):
        """Должен возвращать None если нет callback_query."""
        mock_update.callback_query = None
        result = await handle_price_range_callback(mock_update, mock_context)
        assert result is None

    @pytest.mark.asyncio()
    async def test_returns_none_if_no_query_data(self, mock_update, mock_context):
        """Должен возвращать None если нет данных в callback_query."""
        mock_update.callback_query.data = None
        result = await handle_price_range_callback(mock_update, mock_context)
        assert result is None

    @pytest.mark.asyncio()
    async def test_answers_callback_query(self, mock_update, mock_context):
        """Должен отвечать на callback_query."""
        mock_update.callback_query.data = "price_range:csgo"
        await handle_price_range_callback(mock_update, mock_context)
        mock_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio()
    async def test_edits_message_with_price_keyboard(self, mock_update, mock_context):
        """Должен редактировать сообщение с клавиатуSwarm цен."""
        mock_update.callback_query.data = "price_range:csgo"
        await handle_price_range_callback(mock_update, mock_context)
        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_keyboard_has_price_ranges(self, mock_update, mock_context):
        """Клавиатура должна иметь диапазоны цен."""
        mock_update.callback_query.data = "price_range:csgo"
        await handle_price_range_callback(mock_update, mock_context)

        call_args = mock_update.callback_query.edit_message_text.call_args
        reply_markup = call_args.kwargs.get("reply_markup") or call_args[1].get(
            "reply_markup"
        )

        button_texts = [btn.text for row in reply_markup.inline_keyboard for btn in row]
        assert "$1-10" in button_texts
        assert "$10-50" in button_texts
        assert "$50-100" in button_texts


# ======================== Edge Cases Tests ========================


class TestEdgeCases:
    """Тесты для граничных случаев."""

    def test_get_current_filters_unknown_game(self, mock_context):
        """Должен возвращать пустой словарь для неизвестной игры."""
        mock_context.user_data = {}
        result = get_current_filters(mock_context, "unknown_game")
        assert result == {}

    def test_get_game_filter_keyboard_unknown_game(self):
        """Должен возвращать базовую клавиатуру для неизвестной игры."""
        result = get_game_filter_keyboard("unknown_game")
        assert isinstance(result, InlineKeyboardMarkup)
        # Должны быть как минимум кнопки цены, сброса и назад
        button_count = sum(len(row) for row in result.inline_keyboard)
        assert button_count >= 3

    def test_update_filters_with_empty_dict(self, mock_context):
        """Должен корректно обрабатывать пустой словарь фильтров."""
        mock_context.user_data = {}
        update_filters(mock_context, "csgo", {})
        assert mock_context.user_data["filters"]["csgo"] == {}

    def test_default_filters_values_are_numbers(self):
        """Числовые значения фильтров по умолчанию должны быть числами."""
        for filters in DEFAULT_FILTERS.values():
            assert isinstance(filters["min_price"], (int, float))
            assert isinstance(filters["max_price"], (int, float))

    def test_all_game_default_filters_have_min_max_price(self):
        """Все игры должны иметь min_price и max_price."""
        for game in ["csgo", "dota2", "tf2", "rust"]:
            assert "min_price" in DEFAULT_FILTERS[game]
            assert "max_price" in DEFAULT_FILTERS[game]
