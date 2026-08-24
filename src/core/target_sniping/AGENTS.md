# Target Sniping — Subsystem Knowledge

## Архитектура
- `execution.py` — _ExecutionMixin: мгновенные покупки, батч-отправка,
  парсинг ответов DMarket, запись в price_db.
- `filter.py` — фильтрация и pre-trade checks (upstream от execution).
- `cycle_orchestrator.py` — оркестрация циклов сканирования.
- `demand_strategy.py` — стратегия выбора предметов.
- `pricing.py` — расчёт цен и маржи.

## Исправленные баги execution.py (2026-08-23, ветка feature/execution-fixes)

### 1. `successful_titles` → `successful_offer_ids` (коммит 72e25da)
**Проблема:** Успешные покупки трекались по `title` (название предмета).
При батче с одинаковыми названиями (например два "AK-47 | Redline"),
если один провалился — оба считались успешными, потому что `title`
совпадал. Это приводило к ложной записи в `price_db`.

**Исправление:** Трекинг по уникальному `offerId`. Финальная проверка:
`item_data["buy_offer"].get("offerId") in successful_offer_ids`.

### 2. TxFailed + dmOffersStatus (коммит 67f3124)
**Проблема:** При `status == "TxFailed"` код всё равно парсил
`dmOffersStatus` и мог найти `"started": true` для отдельных офферов,
записывая их как успешные. Но `TxFailed` означает провал всей
транзакции — `started` в этом контексте не означает реальную покупку.

**Исправление:** Ветка `else` (TxFailed/пустой статус) больше не
парсит `dmOffersStatus`. Весь батч считается неуспешным.

### 3. _check_slippage fallback на current_listings[0] (коммит 50edab6)
**Проблема:** Если конкретный оффер не найден в результатах
`get_market_items_v2`, код брал `current_listings[0]` (первый попавшийся
листинг) и сравнивал цену с ним. Это позволяло "проскользнуть"
покупке с неправильной ценой.

**Исправление:** Если `matching` пуст — `return None` (fail-closed).
Логика аналогична блоку "listing disappeared" выше по тому же файлу.

## Известный техдолг (НЕ исправлен)

### Находка 4: DRY_RUN-only dead code в risk-adjustment (Low priority)
В `execution.py` есть блок `if is_dry:` (строки ~415-460), где
`adjusted_size_usd` вычисляется через `risk.pre_trade_check()`.
В PROD-пути этот код **не выполняется** — `pre_trade_check` в PROD
работает как бинарный гейт (pass/block) раньше в пайплайне (filter.py:127).
Soft-adjustment мёртвый код, изолированный в `if is_dry:`.

**Решение:** Низкий приоритет. Можно вычистить, но не критично —
dead code не влияет на production.

## Закрытые вопросы (НЕ переоткрывать)
- **`has_reference_discount`** — удалена как тавтология (коммит 21e489a).
  `cs_price` всегда 0 после удаления oracle, поэтому проверка
  `cs_price > 0 and cs_price < market_price` никогда не срабатывала.
  Не восстанавливать без нового обоснования.

## Правила для агентов
- `pre_trade_check()` в PROD — **бинарный гейт** (pass/block).
  Не пытаться "улучшить" его до soft-adjustment без полного
  прослеживания upstream (filter.py) и downstream (execution.py).
- Любые формульные изменения в pricing.py/demand_strategy.py
  требуют полного бэктеста перед деплоем (см. AGENTS.md корневой).

*Последнее обновление: 2026-08-23. Обновлять при каждом изменении в этой подсистеме.*

## Risk Management (Update)
- Soft-halt in risk_manager.py returns allowed=False (hard block), not a partial size reduction — DMarket assets are indivisible, partial sizing was found as dead/unused code twice (execution.py Kelly block + Finding A) and removed. Do not reintroduce adjusted_size_usd-based partial sizing without solving how downstream code enforces it.
- SYSTEMIC PATTERN WARNING: If a third partial-sizing mechanism is found (after Kelly block and Finding A), treat it as a systemic pattern of architecture mismatch (continuous-math risk model vs discrete inventory) rather than an isolated bug.
