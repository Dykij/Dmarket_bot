"""Hypothesis strategies для генерации тестовых данных DMarket бота.

Этот модуль содержит переиспользуемые стратегии для property-based тестирования
компонентов арбитража, таргетов и API клиента.
"""

from hypothesis import strategies as st

# ============================================================================
# СТРАТЕГИИ ДЛЯ ЦЕН
# ============================================================================

# Цены в USD (float, от $0.01 до $10,000)
price_usd = st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False)

# Цены в центах (integer, от 1 до 1,000,000 центов)
price_cents = st.integers(min_value=1, max_value=1_000_000)

# Процент комиссии DMarket (от 2% до 15%)
commission_percent = st.floats(min_value=2.0, max_value=15.0, allow_nan=False)

# Процент прибыли (от 0.1% до 100%)
profit_percent = st.floats(min_value=0.1, max_value=100.0, allow_nan=False)


# ============================================================================
# СТРАТЕГИИ ДЛЯ ИГР
# ============================================================================

# Поддерживаемые игры
supported_games = st.sampled_from(["csgo", "dota2", "tf2", "rust"])

# Режимы арбитража
arbitrage_modes = st.sampled_from(["low", "medium", "high", "boost", "pro"])


# ============================================================================
# СТРАТЕГИИ ДЛЯ ПРЕДМЕТОВ
# ============================================================================

# Название предмета (строка с ограничениями)
item_title = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"), min_codepoint=32, max_codepoint=126
    ),
    min_size=1,
    max_size=100,
)

# Item ID (UUID-подобная строка)
item_id = st.text(
    alphabet="0123456789abcdef",
    min_size=32,
    max_size=32,
)

# Редкость предмета
item_rarity = st.sampled_from([
    "Consumer Grade",
    "Industrial Grade",
    "Mil-Spec Grade",
    "Restricted",
    "Classified",
    "Covert",
    "Contraband",
    "Extraordinary",
    "Ancient",
    "Mythical",
    "Immortal",
    "Arcana",
])

# Категория предмета
item_category = st.sampled_from([
    "Rifle",
    "Pistol",
    "SMG",
    "Heavy",
    "Knife",
    "Gloves",
    "Sticker",
    "ContAlgoner",
    "Key",
])

# Экстерьер предмета CS:GO
item_exterior = st.sampled_from([
    "Factory New",
    "Minimal Wear",
    "Field-Tested",
    "Well-Worn",
    "Battle-Scarred",
])

# Популярность предмета (0.0 до 1.0)
item_popularity = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)


# ============================================================================
# СОСТАВНЫЕ СТРАТЕГИИ
# ============================================================================


@st.composite
def market_item(draw: st.DrawFn) -> dict:
    """Генерирует структуру предмета рынка DMarket.

    Returns:
        dict: Словарь с данными предмета

    """
    price = draw(price_cents)
    suggested_price = draw(
        st.integers(min_value=price, max_value=int(price * 1.5)),
    )

    return {
        "itemId": draw(item_id),
        "title": draw(item_title),
        "price": {"amount": str(price), "USD": str(price)},
        "suggestedPrice": {"amount": str(suggested_price), "USD": str(suggested_price)},
        "extra": {
            "category": draw(item_category),
            "rarity": draw(item_rarity),
            "exterior": draw(item_exterior),
            "popularity": draw(item_popularity),
        },
    }


@st.composite
def arbitrage_opportunity(draw: st.DrawFn) -> dict:
    """Генерирует структуру арбитражной возможности.

    Returns:
        dict: Словарь с арбитражной возможностью

    """
    buy_price = draw(price_usd)
    # Цена продажи всегда выше покупки для прибыльной сделки
    sell_price = draw(
        st.floats(
            min_value=buy_price * 1.01,
            max_value=buy_price * 2.0,
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    commission = draw(commission_percent)

    # Рассчитываем прибыль
    net_sell = sell_price * (1 - commission / 100)
    profit = net_sell - buy_price
    profit_pct = (profit / buy_price) * 100 if buy_price > 0 else 0

    return {
        "item_name": draw(item_title),
        "buy_price": buy_price,
        "sell_price": sell_price,
        "profit": profit,
        "profit_percent": profit_pct,
        "commission_percent": commission,
        "game": draw(supported_games),
    }


@st.composite
def target_request(draw: st.DrawFn) -> dict:
    """Генерирует запрос на создание таргета.

    Returns:
        dict: Словарь с параметрами таргета

    """
    return {
        "game": draw(supported_games),
        "title": draw(item_title),
        "price": draw(price_usd),
        "amount": draw(st.integers(min_value=1, max_value=100)),
    }


@st.composite
def price_pAlgor(draw: st.DrawFn) -> tuple[float, float]:
    """Генерирует пару цен (покупка, продажа).

    Returns:
        tuple: (цена покупки, цена продажи)

    """
    buy = draw(price_usd)
    # Добавляем минимум 1% к цене покупки
    sell = draw(
        st.floats(
            min_value=buy * 1.01,
            max_value=buy * 3.0,
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    return (buy, sell)


# ============================================================================
# EDGE CASE СТРАТЕГИИ
# ============================================================================

# Экстремальные цены для edge cases
extreme_prices = st.one_of(
    st.just(0.01),  # Минимальная цена
    st.just(0.001),  # Ниже минимума (должна быть отклонена)
    st.just(9999.99),  # Близко к максимуму
    st.just(10000.0),  # Максимум
    st.floats(min_value=0.01, max_value=1.0, allow_nan=False),  # Низкие цены
    st.floats(min_value=1000.0, max_value=10000.0, allow_nan=False),  # Высокие цены
)

# Проблемные строки для названий
problematic_titles = st.one_of(
    st.just(""),  # Пустая строка
    st.just(" " * 100),  # Только пробелы
    st.just("A" * 500),  # Очень длинная строка
    st.text(min_size=1, max_size=10),  # Короткие строки
    item_title,  # Нормальные названия
)
