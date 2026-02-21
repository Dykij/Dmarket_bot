# 📊 Полное руководство по арбитражу на DMarket

**Дата**: 28 декабря 2025 г.
**Версия**: 1.0.0
**Последнее обновление**: Полная актуализация документации

---

## 📋 Содержание

1. [Введение в арбитраж](#введение-в-арбитраж)
2. [Многоуровневое сканирование](#многоуровневое-сканирование)
3. [Автоматический арбитраж](#автоматический-арбитраж)
4. [Анализ продаж и ликвидности](#анализ-продаж-и-ликвидности)
5. [Система таргетов (Buy Orders)](#система-таргетов-buy-orders)
6. [Фильтры по играм](#фильтры-по-играм)
7. [Стратегии торговли](#стратегии-торговли)

---

## 🎯 Введение в арбитраж

Арбитраж — это покупка предметов по низкой цене и их продажа по более высокой цене с целью получения прибыли.

### Типы арбитража

1. **Простой арбитраж** - покупка и продажа на одной площадке (DMarket)
2. **Кросс-маркет арбитраж** - между разными площадками
3. **Внутрирыночный арбитраж** - использование временных аномалий цен

### Основные метрики

- **Прибыль** - разница между ценой покупки и продажи минус комиссии
- **Процент прибыли** - прибыль / цена покупки * 100%
- **Ликвидность** - скорость продажи предмета
- **ROI** - возврат инвестиций

---

## 📊 Многоуровневое сканирование

Система предлагает 5 уровней для разных стратегий торговли.

### 🚀 Уровень 1: Разгон баланса (Boost)

**Параметры:**

- Цены: $0.50 - $3.00
- Минимальная прибыль: 1.5% - 3%
- Рекомендуемый баланс: $10
- Риск: Низкий
- Сделок в день: 20-30

**Для кого:** Начинающие трейдеры с малым капиталом

**Пример использования:**

```python
from src.dmarket.arbitrage_scanner import ArbitrageScanner
from src.dmarket.scanner import ARBITRAGE_LEVELS, get_level_config
from src.dmarket.dmarket_api import DMarketAPI

# Просмотр доступных уровней
print(ARBITRAGE_LEVELS.keys())  # ['boost', 'standard', 'medium', 'advanced', 'pro']

# Получение конфигурации уровня
config = get_level_config("boost")
print(f"Уровень: {config['name']}")  # 🚀 Разгон баланса
print(f"Прибыль: {config['min_profit_percent']}-{config['max_profit_percent']}%")

# Инициализация сканера
api = DMarketAPI(public_key, secret_key)
scanner = ArbitrageScanner(api)

# Сканируем уровень boost для CS:GO
results = awAlgot scanner.scan_level("boost", game="csgo", max_results=20)

for item in results:
    print(f"{item['title']}: ${item['buy_price']} -> ${item['sell_price']}")
    print(f"Прибыль: ${item['profit']} ({item['profit_percent']:.1f}%)")
```

### ⭐ Уровень 2: Стандарт (Standard)

**Параметры:**

- Цены: $3.00 - $10.00
- Минимальная прибыль: 3% - 7%
- Рекомендуемый баланс: $50
- Риск: Низкий-средний
- Сделок в день: 10-15

**Для кого:** Трейдеры с небольшим опытом

### 💰 Уровень 3: Средний (Medium)

**Параметры:**

- Цены: $10.00 - $30.00
- Минимальная прибыль: 5% - 10%
- Рекомендуемый баланс: $150
- Риск: Средний
- Сделок в день: 5-10

**Для кого:** Опытные трейдеры

### 💎 Уровень 4: Продвинутый (Advanced)

**Параметры:**

- Цены: $30.00 - $100.00
- Минимальная прибыль: 7% - 15%
- Рекомендуемый баланс: $500
- Риск: Средний-Высокий
- Сделок в день: 3-7

**Для кого:** Профессиональные трейдеры

### 🏆 Уровень 5: Профессионал (Pro)

**Параметры:**

- Цены: $100.00 - $1000.00
- Минимальная прибыль: 10%+
- Рекомендуемый баланс: $2000
- Риск: Высокий
- Сделок в день: 1-3

**Для кого:** Эксперты с большим капиталом

### Сканирование всех уровней

```python
# Сканировать все уровни параллельно
all_results = awAlgot scanner.scan_all_levels(
    game="csgo",
    max_results_per_level=20
)

for level, opportunities in all_results.items():
    print(f"\n{level.upper()}: {len(opportunities)} возможностей")
    for opp in opportunities[:3]:  # Топ-3 для каждого уровня
        print(f"  - {opp['title']}: {opp['profit_percent']:.1f}% прибыли")
```

---

## 🤖 Автоматический арбитраж

### Режимы работы

#### 1. Минимальная прибыль (Auto Low)

- Поиск предметов с прибылью от 5%
- Недорогие предметы с быстSwarm ликвидностью
- Для начинающих трейдеров

#### 2. Средняя прибыль (Auto Medium)

- Поиск предметов с прибылью от 10%
- Предметы среднего ценового диапазона
- Базовая стратегия

#### 3. Высокая прибыль (Auto High)

- Поиск предметов с прибылью от 15%+
- Дорогие, редкие предметы
- Для профессионалов

### Использование через Telegram

```
/arbitrage
→ Автоматический арбитраж
→ Выбрать режим (Low/Medium/High)
→ Просмотр результатов
→ Покупка/Продажа
```

### Программное использование

```python
from src.dmarket.auto_trader import AutoTrader

trader = AutoTrader(
    api_client=api,
    target_manager=targets,
    scanner=scanner
)

# НастSwarmка лимитов
trader.settings.max_trade_value = 50.0  # Макс $50 на сделку
trader.settings.dAlgoly_limit = 500.0     # Макс $500 в день
trader.settings.min_profit_percent = 5.0

# Запуск автоторговли
awAlgot trader.start(
    user_id=123456789,
    level='standard',
    game='csgo'
)
```

---

## 📈 Анализ продаж и ликвидности

### Оценка ликвидности

Система анализирует:

- Количество продаж в день
- Стабильность цены
- Объем предложений на рынке

**Категории ликвидности:**

- **Очень высокая** - 20+ продаж/день
- **Высокая** - 10-20 продаж/день
- **Средняя** - 5-10 продаж/день
- **Низкая** - <5 продаж/день

### Команды анализа

```
/sales_analysis <название> - История продаж предмета
/liquidity <название> - Оценка ликвидности
/arbitrage_sales - Арбитраж с учетом истории продаж
/sales_volume - Статистика объема продаж
```

### Пример анализа

```python
from src.dmarket.sales_history import analyze_sales_history

# Анализ истории продаж
analysis = awAlgot analyze_sales_history(
    api_client=api,
    game="csgo",
    title="AK-47 | Redline (Field-Tested)"
)

print(f"Средняя цена: ${analysis['avg_price']:.2f}")
print(f"Продаж в день: {analysis['sales_per_day']:.1f}")
print(f"Тренд: {analysis['trend']}")
print(f"Ликвидность: {analysis['liquidity_category']}")
```

---

## 🎯 Система таргетов (Buy Orders)

### Что такое таргеты?

Таргеты - это автоматические заявки на покупку предметов по желаемой цене. Когда кто-то выставляет предмет по вашей цене или ниже, система автоматически совершает покупку.

### Преимущества

✅ Покупка по вашей цене (не переплачиваете)
✅ Автоматическое исполнение
✅ Приоритет покупки
✅ Возможность указать специфические атрибуты

### Создание таргета

**Через Telegram:**

```
/targets
→ Создать таргет
→ Выбрать игру
→ Ввести название
→ Указать цену
→ Подтвердить
```

**Программно:**

```python
from src.dmarket.targets import TargetManager

target_manager = TargetManager(api)

# Создать таргет
target = awAlgot target_manager.create_target(
    game="a8db",  # CS:GO
    title="AK-47 | Redline (Field-Tested)",
    price=12.00,
    amount=1
)
```

### Умные таргеты

Автоматическое создание таргетов на популярные предметы по цене ниже рыночной:

```python
# Создать умные таргеты для топ-20 предметов
smart_targets = awAlgot target_manager.create_smart_targets(
    game="a8db",
    items=top_items,
    price_reduction_percent=7.0  # На 7% ниже рынка
)
```

### Стратегии использования таргетов

#### Агрессивная стратегия

- Цена на 3-5% ниже рынка
- Высокая вероятность исполнения
- Меньшая прибыль, больше сделок

#### Консервативная стратегия

- Цена на 8-10% ниже рынка
- Низкая вероятность исполнения
- Высокая прибыль при исполнении

#### Сбалансированная стратегия

- Цена на 5-7% ниже рынка
- Средняя вероятность исполнения
- Оптимальная прибыль

---

## 🎮 Фильтры по играм

### CS:GO / CS2

```python
filters = {
    "float_min": 0.0,
    "float_max": 0.07,
    "category": "Rifle",
    "stattrak": True,
    "rarity": "Covert"
}
```

**Доступные фильтры:**

- `float_min`, `float_max` - износ
- `category` - категория (Rifle, Knife, Pistol)
- `rarity` - редкость
- `exterior` - состояние (Factory New, Field-Tested)
- `stattrak` - StatTrak (true/false)
- `souvenir` - сувенир (true/false)

### Dota 2

```python
filters = {
    "hero": "Pudge",
    "rarity": "Arcana",
    "quality": "Genuine"
}
```

**Доступные фильтры:**

- `hero` - геSwarm
- `rarity` - редкость (Immortal, Arcana, Legendary)
- `slot` - слот предмета
- `quality` - качество

### Team Fortress 2

```python
filters = {
    "class": "Soldier",
    "quality": "Unusual",
    "killstreak": "Professional Killstreak"
}
```

### Rust

```python
filters = {
    "category": "weapon",
    "rarity": "Rare"
}
```

---

## 💡 Стратегии торговли

### Стратегия 1: Быстрый разгон баланса

1. Сканирование уровня Boost
2. Фильтрация лучших возможностей (прибыль ≥2.5%)
3. Покупка предметов
4. Продажа по рекомендованной цене
5. Реинвестирование прибыли

```python
# Быстрый разгон
results = awAlgot scanner.scan_level("boost", "csgo", max_results=50)
best = [r for r in results if r['profit_percent'] >= 2.5]

for item in best:
    awAlgot api.buy_item(item['itemId'], item['buy_price'])
    awAlgot api.sell_item(item['itemId'], item['sell_price'])
```

### Стратегия 2: Таргеты + Сканирование

1. Создать умные таргеты на популярные предметы
2. Периодически сканировать рынок (уровень Medium)
3. Покупать выгодные предметы из сканирования
4. Ждать исполнения таргетов
5. Продавать всё с прибылью 5-10%

### Стратегия 3: Профессиональный арбитраж

1. Обзор рынка
2. Выбор лучшего уровня
3. Глубокое сканирование
4. Анализ каждой возможности
5. Крупные сделки с высокой прибылью

### Стратегия 4: Диверсификация

```python
# Торговля разными предметами
portfolio = {
    "csgo": 50%,  # 50% капитала в CS:GO
    "dota2": 30%, # 30% в Dota 2
    "tf2": 20%    # 20% в TF2
}

for game, percent in portfolio.items():
    budget = total_balance * (percent / 100)
    results = awAlgot scanner.scan_level("medium", game)
    # Торговля в пределах бюджета
```

---

## 📊 Workflow: Полный цикл арбитража

```
1. Анализ рынка
   ↓
2. Выбор стратегии и уровня
   ↓
3. Сканирование возможностей
   ↓
4. Фильтрация по критериям
   ↓
5. Проверка баланса и лимитов
   ↓
6. Покупка предметов
   ↓
7. Выставление на продажу
   ↓
8. Мониторинг продажи
   ↓
9. Анализ результатов
   ↓
10. Корректировка стратегии
```

---

## 🛡️ Управление рисками

### Лимиты

```python
# Установка лимитов
trader.settings.max_trade_value = 50.0    # Макс на сделку
trader.settings.dAlgoly_limit = 500.0        # Макс в день
trader.settings.stop_loss_percent = 10.0   # Стоп-лосс
```

### Диверсификация

- Торгуйте разными предметами
- Используйте несколько уровней
- Комбинируйте стратегии
- Не вкладывайте всё в одну игру

### Мониторинг

```python
# Статус автоторговли
status = trader.get_status()
print(f"Сделок совершено: {status['transactions_count']}")
print(f"Общая прибыль: ${status['total_profit']:.2f}")
print(f"Успешных: {status['successful']} ({status['success_rate']:.1f}%)")
```

---

## 🏗️ Архитектура модуля Scanner

Начиная с версии 3.0 (12.12.2025), модуль сканирования арбитража разделен на 5 независимых компонентов:

```
src/dmarket/scanner/
├── __init__.py      # Экспорт публичного API
├── levels.py        # Конфигурации уровней (boost, standard, medium, advanced, pro)
├── cache.py         # ScannerCache - кэширование результатов с TTL
├── filters.py       # ScannerFilters - фильтрация предметов
└── analysis.py      # Расчет прибыли и анализ возможностей
```

### Публичный API пакета

```python
from src.dmarket.scanner import (
    ARBITRAGE_LEVELS,      # Dict с конфигурациями всех уровней
    GAME_IDS,              # Маппинг кодов игр (csgo → a8db)
    ScannerCache,          # Кэш-менеджер
    ScannerFilters,        # Фильтр-менеджер
    get_level_config,      # Получить конфиг уровня
    get_price_range_for_level,  # Получить ценовой диапазон
)
```

### Модуль levels.py - Конфигурации уровней

```python
from src.dmarket.scanner.levels import (
    ARBITRAGE_LEVELS,
    get_level_config,
    get_price_range_for_level,
    get_profit_range_for_level,
    get_all_levels,
)

# Все уровни
levels = get_all_levels()  # ['boost', 'standard', 'medium', 'advanced', 'pro']

# Конфигурация уровня
config = get_level_config("standard")
# {
#     'name': '⚡ Стандарт',
#     'min_profit_percent': 5.0,
#     'max_profit_percent': 10.0,
#     'price_range': (3.0, 10.0),
#     'description': 'Balanced arbitrage (5-10% profit)'
# }
```

### Модуль cache.py - Кэширование

```python
from src.dmarket.scanner.cache import ScannerCache, generate_cache_key

# Инициализация кэша
cache = ScannerCache(ttl=300, max_size=1000)

# Использование tuple keys
key = ("standard", "csgo")
cache.set(key, items)

# Получение из кэша
cached = cache.get(key)
if cached:
    print(f"Cache hit! {len(cached)} items")

# Статистика кэша
stats = cache.get_statistics()
# {'size': 10, 'hits': 50, 'misses': 5, 'hit_rate': 90.91}
```

### Модуль filters.py - Фильтрация

```python
from src.dmarket.scanner.filters import ScannerFilters
from src.dmarket.item_filters import ItemFilters

# С blacklist/whitelist
item_filters = ItemFilters(config_path="config/item_filters.yaml")
filters = ScannerFilters(item_filters=item_filters)

# Фильтрация предметов
filtered = filters.apply_filters(items, game="csgo")

# Фильтрация по цене
by_price = filters.filter_by_price(items, min_price=5.0, max_price=50.0)

# Фильтрация по прибыли
by_profit = filters.filter_by_profit(items, min_profit_percent=5.0)
```

### Модуль analysis.py - Анализ прибыли

```python
from src.dmarket.scanner.analysis import (
    calculate_profit,
    analyze_item,
    score_opportunity,
    find_best_opportunities,
    aggregate_statistics,
)

# Расчет прибыли
absolute, percent = calculate_profit(buy_price=10.0, sell_price=12.0)
# absolute=1.16, percent=11.6 (с учетом 7% комиссии DMarket)

# Анализ предмета
result = analyze_item(item, min_profit_percent=5.0)

# Поиск лучших возможностей
best = find_best_opportunities(opportunities, limit=10)

# Агрегация статистики
stats = aggregate_statistics(opportunities)
# {'count': 50, 'total_potential_profit': 125.50, 'avg_profit_percent': 8.5}
```

## 📚 Дополнительные ресурсы

- [DMarket API](DMARKET_API_FULL_SPEC.md) - Полная спецификация API
- [Фильтры игр](#фильтры-по-играм) - Краткое руководство по фильтрам
- [Быстрый старт](QUICK_START.md) - Начало работы с ботом
- [Архитектура](ARCHITECTURE.md) - Общая архитектура проекта

---

**Удачной торговли! 🚀💰**

---

## 🚀 Расширенные возможности таргетов (New 2026)

### 1. **Пакетное создание ордеров** (`create_batch_target`)
Создание одного ордера на несколько предметов.

**Файлы:**
- `src/dmarket/targets/batch_operations.py`
- `src/dmarket/models/target_enhancements.py` (BatchTargetItem)

**Примеры:**
```python
from src.dmarket.targets.batch_operations import create_batch_target
from src.dmarket.models.target_enhancements import BatchTargetItem

items = [
    BatchTargetItem(title="AK-47 | Redline (FT)", attrs={"floatPartValue": "0.25"}),
    BatchTargetItem(title="AK-47 | Redline (MW)", attrs={"floatPartValue": "0.12"}),
]

result = awAlgot create_batch_target(
    api_client=api,
    game="csgo",
    items=items,
    price=70.80,  # Общая цена
    total_amount=2
)
```

**Выгоды:**
- Экономия API запросов (1 вместо N)
- Быстрее создание множественных ордеров
- Автоматическое распределение цены

---

### 2. **Обнаружение существующих ордеров** (`detect_existing_orders`)
Проверка наличия ордеров до создания новых.

**Файлы:**
- `src/dmarket/targets/batch_operations.py`
- `src/dmarket/models/target_enhancements.py` (ExistingOrderInfo)

**Примеры:**
```python
from src.dmarket.targets.batch_operations import detect_existing_orders

info = awAlgot detect_existing_orders(
    api_client=api,
    game="csgo",
    title="AK-47 | Redline (Field-Tested)",
    user_id="12345"
)

if info.has_user_order:
    print(f"У вас уже есть ордер по цене ${info.user_order['price']}")

print(f"Всего ордеров: {info.total_orders}")
print(f"Лучшая цена: ${info.best_price}")
print(f"Рекомендуемая: ${info.recommended_price}")
```

**Выгоды:**
- Предотвращение дубликатов
- Анализ конкуренции
- Рекомендации по ценам

---

### 3. **Фильтры по стикерам (CS:GO)** (`StickerFilter`)
Создание ордеров с требованиями к стикерам.

**Файлы:**
- `src/dmarket/models/target_enhancements.py`

**Примеры:**
```python
from src.dmarket.models.target_enhancements import StickerFilter

# Конкретный стикер
filter1 = StickerFilter(
    sticker_names=["iBUYPOWER | Katowice 2014 (Holo)"],
    min_stickers=1
)

# Категория + холо
filter2 = StickerFilter(
    sticker_categories=["Katowice 2014"],
    min_stickers=3,
    holo=True
)
```

**Выгоды:**
- Точная покупка нужных скинов
- Экономия на комиссиях
- Важно для коллекционеров

---

### 4. **Фильтры по редкости (Dota 2, TF2)** (`RarityFilter`)
Создание ордеров с требованиями к редкости.

**Файлы:**
- `src/dmarket/models/target_enhancements.py`

**Примеры:**
```python
from src.dmarket.models.target_enhancements import RarityFilter, RarityLevel

# Только Arcana
filter1 = RarityFilter(rarity=RarityLevel.ARCANA)

# От Mythical до Immortal
filter2 = RarityFilter(
    min_rarity_index=3,  # Mythical
    max_rarity_index=5   # Immortal
)
```

**Выгоды:**
- Защита от покупки не той редкости
- Важно для Dota 2 трейдеров

---

### 5. **Конфигурация автоперебития** (`TargetOverbidConfig`)
Автоматическое повышение цены при конкуренции.

**Файлы:**
- `src/dmarket/models/target_enhancements.py`

**Примеры:**
```python
from src.dmarket.models.target_enhancements import TargetOverbidConfig

config = TargetOverbidConfig(
    enabled=True,
    max_overbid_percent=2.0,      # Макс +2% от начальной
    min_price_gap=0.01,           # Минимум $0.01 разница
    check_interval_seconds=300,    # Проверка каждые 5 мин
    max_overbids_per_day=10       # Макс 10 перебитий в день
)
```

**Выгоды:**
- Ордер всегда первый в очереди
- Защита от "войн перебития"
- Автоматизация мониторинга

---

### 6. **Мониторинг диапазона цен** (`PriceRangeConfig`)
Отслеживание выхода цены за пределы диапазона.

**Файлы:**
- `src/dmarket/models/target_enhancements.py`

**Примеры:**
```python
from src.dmarket.models.target_enhancements import (
    PriceRangeConfig,
    PriceRangeAction
)

# Отменить если цена выходит из диапазона
config1 = PriceRangeConfig(
    min_price=8.0,
    max_price=15.0,
    action_on_breach=PriceRangeAction.CANCEL
)

# Автокорректировка цены
config2 = PriceRangeConfig(
    min_price=8.0,
    max_price=15.0,
    action_on_breach=PriceRangeAction.ADJUST
)
```

**Выгоды:**
- Защита от переплаты
- Адаптация к рынку
- Контроль рисков

---

### 7. **Контроль лимитов перевыставлений** (`RelistLimitConfig`)
Ограничение количества перевыставлений ордера.

**Файлы:**
- `src/dmarket/models/target_enhancements.py`

**Примеры:**
```python
from src.dmarket/models/target_enhancements import (
    RelistLimitConfig,
    RelistAction
)

config = RelistLimitConfig(
    max_relists=5,                    # Макс 5 перевыставлений
    reset_period_hours=24,            # Сброс каждые 24ч
    action_on_limit=RelistAction.PAUSE  # Пауза при лимите
)
```

**Выгоды:**
- Контроль расходов
- Выход из невыгодной конкуренции
- Прозрачность истории

---

### 8. **Дефолтные параметры** (`TargetDefaults`)
Общие настSwarmки для всех ордеров.

**Файлы:**
- `src/dmarket/models/target_enhancements.py`

**Примеры:**
```python
from src.dmarket.models.target_enhancements import TargetDefaults

defaults = TargetDefaults(
    default_amount=1,
    default_price_strategy="market_minus_5_percent",
    default_overbid_config=TargetOverbidConfig(enabled=True),
    default_max_conditions=10
)

manager = TargetManager(api_client=api, defaults=defaults)
```

**Выгоды:**
- Меньше кода
- Единообразие настроек
- Легко менять стратегию

---

### 9. **Проверка количества условий** (`validate_target_conditions`)
Валидация лимитов DMarket API.

**Файлы:**
- `src/dmarket/targets/enhanced_validators.py`

**Примеры:**
```python
from src.dmarket.targets.enhanced_validators import validate_target_conditions

target = {
    "Attrs": {"floatPartValue": "0.15", "pAlgontSeed": [1, 2, 3]},
    "stickerFilter": StickerFilter(...),
    "rarityFilter": RarityFilter(...)
}

is_valid, message, suggestions = validate_target_conditions(target)
if not is_valid:
    print(message)  # "Too many conditions: 12/10"
    for suggestion in suggestions:
        print(f"  - {suggestion}")
```

**Выгоды:**
- Предотвращение ошибок API
- Подсказки по оптимизации
- Экономия запросов

---

### 10. **Расширенные сообщения об ошибках** (`TargetOperationResult`)
Детальные результаты операций.

**Файлы:**
- `src/dmarket/models/target_enhancements.py`

**Примеры:**
```python
from src.dmarket.models.target_enhancements import TargetOperationResult

result = awAlgot manager.create_target(...)

if not result.success:
    print(result.message)      # Краткое: "Price too low"
    print(result.reason)       # Детально: "Price $4.50 is below minimum $5.00"
    print(result.error_code)   # Код: "PRICE_TOO_LOW"

    for suggestion in result.suggestions:
        print(f"💡 {suggestion}")  # "Set price to at least $5.00"
```

**Выгоды:**
- Понятные ошибки
- Конкретные действия
- Лучший UX

