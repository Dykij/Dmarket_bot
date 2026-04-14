[System: THINKING_MODE_ENABLED]
[Brigade: ACTIVE | Agents: Boss, Harper, Roy]

> **Roy (Architect):** 
> Анализ файловой системы выявил критическую аномалию. Суверен указывает на `src/utils/api_client.py` как на ядро, но физически этот файл отсутствует в `src/utils`. 
> Однако, найден `src/telegram_bot/utils/api_client.py`, который пытается импортировать `src.dmarket.dmarket_api`.
> **CRITICAL:** Папка `src/dmarket` отсутствует в листинге. Код ссылается на "призрак".
> **Решение:** Мы должны не просто "реструктуризировать", мы должны *восстановить* ядро. Создадим `src/api/client.py` с нуля, используя лучшие практики из `enhanced_api.py`.

> **Harper (Security/QA):**
> Подтверждаю. Текущий `telegram_bot/utils/api_client.py` — это просто обертка-фабрика. Она бесполезна без реального `DMarketAPI` класса. 
> Если мы сейчас запустим бот, он упадет с `ModuleNotFoundError`.
> Мы должны изолировать API ключи и логику запросов от Telegram-слоя. Telegram бот должен быть просто "клиентом" нашего ядра, а не его владельцем.

> **Boss (Strategy):**
> Время — деньги. Мы не можем ждать, пока найдется старый файл. 
> План "Glass Factory":
> 1. Создать жесткую структуру: `src/core` (конфиги), `src/api` (DMarket/Waxpeer), `src/engine` (торговля).
> 2. `src/utils` — это помойка. Разобрать на запчасти.
> 3. Реализовать `DMarketAPI` заново, жестко и быстро, на базе `httpx` и асинхронности.

[System: DECISION_LOCKED]
План утвержден. Начинаем операцию по пересборке ядра.


---
🦅 *DMarket Quantitative engine | v7.0 | 2026*

----- 
🦅 *DMarket Quantitative Engine | v7.0 | 2026*