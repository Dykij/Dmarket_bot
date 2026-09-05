# Analysis Subsystem — Subsystem Knowledge

## Архитектура и Роли
Папка `src/analysis/` содержит высокоуровневые аналитические модули для торгового ядра, а также служит корнем для вложенных аналитических подпапок (`algo_pack`, `microstructure`, `backtest`).

**Модули корневого уровня:**
- `orderbook.py` — глубокий анализ книги ордеров (Orderbook Analysis), выявление крупных стенок (buy/sell walls), спуфинга и распределения ликвидности.
- `seasonal.py` — сезонный анализ цен (выявление паттернов по дням недели, времени суток или внутриигровым циклам CS2).
- `microstructure.py` — фасад (точка входа) для вложенной подсистемы `src/analysis/microstructure/`.
- `__init__.py` — реэкспорт.

*(Вложенные подсистемы описаны в их собственных `AGENTS.md`).*

## Зависимости (Cross-Module)
*Связи подтверждены через RAW-grep и archy.*

**Входящие вызовы (Кто использует `analysis`):**
- **Trading Core (`src/core/target_sniping`):** Пакет массово используется в торговой логике:
  - `cycle_orchestrator.py`
  - `demand_strategy.py`
  - `position_guard.py`
  - `microstructure_pipeline.py`
  - `resale.py`, `resale_prod.py`
  - `filter.py`, `validations.py`, `ranking.py`

**Исходящие вызовы:**
- `microstructure.py` импортирует внутренний пакет `src.analysis.microstructure`.
- Модули `orderbook.py` и `seasonal.py` являются независимыми утилитами (leaf nodes) и не зависят от остального кода `src.*`.

## Правила для агентов
- **Strictly pure functions:** Модули в корне этой папки (особенно `orderbook.py`) выполняют сложную векторизованную математику. Они не должны делать сетевых запросов.
- При редактировании `orderbook.py` учитывайте, что он может вызываться каждую итерацию торгового цикла для десятков предметов, поэтому `pandas/numpy` оптимизации критически важны.

*Последнее обновление: 2026-09-01. Обновлять при каждом изменении в этой подсистеме.*
