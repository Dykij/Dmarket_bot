"""Тесты для модуля pagination.

Этот модуль тестирует PaginationManager для управления пагинацией результатов:
- Добавление элементов для пользователя
- Получение текущей страницы
- Навигация по страницам (next/prev)
- Фильтрация и сортировка
- НастSwarmки элементов на странице
- Очистка данных пользователя
"""

import operator

import pytest

from src.telegram_bot.pagination import PaginationManager

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture()
def pagination_manager():
    """Создает новый PaginationManager для каждого теста."""
    return PaginationManager()


@pytest.fixture()
def sample_items():
    """Создает примерные элементы для пагинации."""
    return [{"id": i, "name": f"Item {i}", "value": i * 10} for i in range(50)]


# ============================================================================
# ТЕСТЫ ИНИЦИАЛИЗАЦИИ
# ============================================================================


def test_pagination_manager_init():
    """Тест инициализации PaginationManager."""
    pm = PaginationManager()
    assert pm is not None
    assert hasattr(pm, "items_by_user")
    assert hasattr(pm, "current_page_by_user")
    assert hasattr(pm, "mode_by_user")
    assert pm.default_items_per_page == 5


def test_pagination_manager_custom_items_per_page():
    """Тест инициализации с кастомным количеством элементов."""
    pm = PaginationManager(default_items_per_page=10)
    assert pm.default_items_per_page == 10


# ============================================================================
# ТЕСТЫ ДОБАВЛЕНИЯ ЭЛЕМЕНТОВ
# ============================================================================


def test_add_items_for_user(pagination_manager, sample_items):
    """Тест добавления элементов для пользователя."""
    user_id = 12345
    pagination_manager.add_items_for_user(user_id, sample_items)

    assert user_id in pagination_manager.items_by_user
    assert len(pagination_manager.items_by_user[user_id]) == 50
    assert pagination_manager.current_page_by_user[user_id] == 0


def test_add_items_alias(pagination_manager, sample_items):
    """Тест алиаса add_items."""
    user_id = 12345
    pagination_manager.add_items(user_id, sample_items)

    assert user_id in pagination_manager.items_by_user
    assert len(pagination_manager.items_by_user[user_id]) == 50


def test_add_items_with_mode(pagination_manager, sample_items):
    """Тест добавления элементов с режимом."""
    user_id = 12345
    pagination_manager.add_items_for_user(user_id, sample_items, mode="custom")

    assert pagination_manager.mode_by_user[user_id] == "custom"


# ============================================================================
# ТЕСТЫ ПОЛУЧЕНИЯ СТРАНИЦЫ
# ============================================================================


def test_get_page_first(pagination_manager, sample_items):
    """Тест получения первой страницы."""
    user_id = 12345
    pagination_manager.add_items_for_user(user_id, sample_items)

    items, current_page, total_pages = pagination_manager.get_page(user_id)

    assert current_page == 0
    assert len(items) == 5  # Default items_per_page
    assert items[0]["id"] == 0
    assert total_pages == 10  # 50 items / 5 per page


def test_get_page_empty_items(pagination_manager):
    """Тест получения страницы когда нет элементов."""
    user_id = 12345
    pagination_manager.add_items_for_user(user_id, [])

    items, current_page, total_pages = pagination_manager.get_page(user_id)

    assert items == []
    assert current_page == 0
    assert total_pages == 0


def test_get_page_no_user(pagination_manager):
    """Тест получения страницы для несуществующего пользователя."""
    user_id = 99999

    items, current_page, total_pages = pagination_manager.get_page(user_id)

    assert items == []
    assert current_page == 0
    assert total_pages == 0


# ============================================================================
# ТЕСТЫ НАВИГАЦИИ
# ============================================================================


def test_next_page(pagination_manager, sample_items):
    """Тест переключения на следующую страницу."""
    user_id = 12345
    pagination_manager.add_items_for_user(user_id, sample_items)

    # Переключаемся на следующую страницу
    items, current_page, _total_pages = pagination_manager.next_page(user_id)

    assert current_page == 1
    assert len(items) == 5
    assert items[0]["id"] == 5  # ВтоSwarm набор элементов


def test_next_page_at_end(pagination_manager):
    """Тест переключения на следующую страницу когда уже на последней."""
    user_id = 12345
    items = [{"id": i} for i in range(10)]
    pagination_manager.add_items_for_user(user_id, items)

    # Переключаемся на последнюю страницу
    pagination_manager.current_page_by_user[user_id] = 1  # Вторая (последняя) страница

    # Пытаемся переключиться дальше
    _items_result, current_page, _total_pages = pagination_manager.next_page(user_id)

    # Должны остаться на последней странице
    assert current_page == 1


def test_prev_page(pagination_manager, sample_items):
    """Тест переключения на предыдущую страницу."""
    user_id = 12345
    pagination_manager.add_items_for_user(user_id, sample_items)

    # Переключаемся на вторую страницу
    pagination_manager.next_page(user_id)

    # Возвращаемся на первую
    items, current_page, _total_pages = pagination_manager.prev_page(user_id)

    assert current_page == 0
    assert items[0]["id"] == 0


def test_prev_page_at_start(pagination_manager, sample_items):
    """Тест переключения на предыдущую страницу когда на первой."""
    user_id = 12345
    pagination_manager.add_items_for_user(user_id, sample_items)

    # Пытаемся переключиться на предыдущую с первой страницы
    _items, current_page, _total_pages = pagination_manager.prev_page(user_id)

    # Должны остаться на первой странице
    assert current_page == 0


# ============================================================================
# ТЕСТЫ НАСТРОЕК
# ============================================================================


def test_get_items_per_page_default(pagination_manager):
    """Тест получения дефолтного количества элементов на странице."""
    user_id = 12345

    items_per_page = pagination_manager.get_items_per_page(user_id)

    assert items_per_page == 5


def test_set_items_per_page(pagination_manager, sample_items):
    """Тест установки количества элементов на странице."""
    user_id = 12345
    pagination_manager.add_items_for_user(user_id, sample_items)

    pagination_manager.set_items_per_page(user_id, 10)

    assert pagination_manager.get_items_per_page(user_id) == 10

    # Проверяем, что текущая страница сброшена
    assert pagination_manager.current_page_by_user[user_id] == 0


def test_set_items_per_page_limits(pagination_manager):
    """Тест ограничений при установке количества элементов."""
    user_id = 12345

    # Слишком маленькое значение
    pagination_manager.set_items_per_page(user_id, 0)
    assert pagination_manager.get_items_per_page(user_id) == 1

    # Слишком большое значение
    pagination_manager.set_items_per_page(user_id, 100)
    assert pagination_manager.get_items_per_page(user_id) == 20


# ============================================================================
# ТЕСТЫ ФИЛЬТРАЦИИ И СОРТИРОВКИ
# ============================================================================


def test_filter_items(pagination_manager, sample_items):
    """Тест фильтрации элементов."""
    user_id = 12345
    pagination_manager.add_items_for_user(user_id, sample_items)

    # Фильтруем только элементы с id < 10
    pagination_manager.filter_items(user_id, lambda item: item["id"] < 10)

    _items, _current_page, _total_pages = pagination_manager.get_page(user_id)

    assert len(pagination_manager.items_by_user[user_id]) == 10
    assert all(item["id"] < 10 for item in pagination_manager.items_by_user[user_id])


def test_sort_items(pagination_manager, sample_items):
    """Тест сортировки элементов."""
    user_id = 12345
    # Добавляем элементы в обратном порядке
    pagination_manager.add_items_for_user(user_id, sample_items[:10][::-1])

    # Сортируем по id (метод принимает key_func)
    pagination_manager.sort_items(user_id, key_func=operator.itemgetter("id"))

    items, _current_page, _total_pages = pagination_manager.get_page(user_id)

    # Проверяем, что элементы отсортированы
    assert items[0]["id"] == 0
    assert items[1]["id"] == 1


# ============================================================================
# ТЕСТЫ РЕЖИМА
# ============================================================================


def test_get_mode_default(pagination_manager, sample_items):
    """Тест получения дефолтного режима."""
    user_id = 12345
    pagination_manager.add_items_for_user(user_id, sample_items)

    mode = pagination_manager.get_mode(user_id)

    assert mode == "default"


def test_get_mode_custom(pagination_manager, sample_items):
    """Тест получения кастомного режима."""
    user_id = 12345
    pagination_manager.add_items_for_user(user_id, sample_items, mode="arbitrage")

    mode = pagination_manager.get_mode(user_id)

    assert mode == "arbitrage"


# ============================================================================
# ТЕСТЫ ОЧИСТКИ
# ============================================================================


def test_clear_user_data(pagination_manager, sample_items):
    """Тест очистки данных пользователя."""
    user_id = 12345
    pagination_manager.add_items_for_user(user_id, sample_items)
    pagination_manager.set_items_per_page(user_id, 10)

    # Очищаем данные
    pagination_manager.clear_user_data(user_id)

    # Проверяем, что данные удалены
    assert user_id not in pagination_manager.items_by_user
    assert user_id not in pagination_manager.current_page_by_user
    assert user_id not in pagination_manager.mode_by_user
    assert user_id not in pagination_manager.user_settings


# ============================================================================
# ТЕСТЫ КЛАВИАТУРЫ ПАГИНАЦИИ
# ============================================================================


def test_get_pagination_keyboard(pagination_manager, sample_items):
    """Тест получения клавиатуры пагинации."""
    user_id = 12345
    pagination_manager.add_items_for_user(user_id, sample_items)

    keyboard = pagination_manager.get_pagination_keyboard(user_id, prefix="test")

    # Проверяем, что клавиатура создана
    assert keyboard is not None
    from telegram import InlineKeyboardMarkup

    assert isinstance(keyboard, InlineKeyboardMarkup)


# ============================================================================
# ТЕСТЫ ФОРМАТИРОВАНИЯ
# ============================================================================


def test_format_current_page(pagination_manager, sample_items):
    """Тест форматирования текущей страницы."""
    user_id = 12345
    pagination_manager.add_items_for_user(user_id, sample_items)

    # Используем дефолтный форматтер
    formatted = pagination_manager.format_current_page(user_id)

    # Проверяем, что результат - строка
    assert isinstance(formatted, str)
    assert len(formatted) > 0
