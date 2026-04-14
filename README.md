# 🦅 DMarket Quantitative Arbitrage Engine (v7.0)

**High-Performance Deterministic Trading & Target Sniping for CS2 and Rust.**

Автономная торговая система, работающая на строгих математических алгоритмах и количественном анализе рынка. Полностью очищена от legacy-кода и экспериментальных ИИ-моделей в пользу максимальной предсказуемости и профита.

---

## 🚀 Основные Возможности

### 1. 📈 Pure Quantitative Core
- **Deterministic Math:** Все решения о покупке принимаются на основе жесткой формулы прибыли (Net Margin >= 5%) с учетом всех комиссий платформы.
- **SQLite Price Intelligence:** Локальная база данных истории цен для выявления краткосрочных трендов и рыночных аномалий.
- **CSFloat Oracle:** Интеграция с внешним оракулом цен для валидации офферов DMarket в реальном времени.

### 2. 🛡️ Protection Layer (The Shield)
- **Trend Guard:** Автоматическая блокировка покупок при обнаружении устойчивого нисходящего тренда (Anti-Crash система).
- **Event Shield (2026):** Динамическая корректировка риск-множителей на основе календаря событий CS2/Rust (Мажоры, Сейлы, Вайпы).
- **Asset Whitelisting:** Концентрация ресурсов на высоколиквидных предметах (CS2 и Rust), исключая Dota 2 и TF2.

### 3. ⚡ High-Frequency Readiness
- **Batch Operations:** Поддержка пакетного создания (`batchCreate`) и удаления таргетов для минимизации задержек.
- **Async Execution:** Полностью асинхронный клиент на `aiohttp` с поддержкой Ed25519 (NACL) подписи.
- **Telegram Interface:** Управление и мониторинг через защищенного Telegram-бота.

---

## 🏗 Технический Стек

| Компонент | Технология |
| :--- | :--- |
| **Logic Core** | Python 3.11+, NumPy |
| **Database** | SQLite 3 (Persistent History) |
| **API Client** | Async REST + Ed25519 Signing |
| **Interface** | Aiogram 3.x (Telegram) |

---

## 🛠 Установка и Запуск

### Быстрый старт
1. Клонировать репозиторий:
   ```bash
   git clone https://github.com/Dykij/Dmarket_bot.git
   ```
2. Установить зависимости:
   ```bash
   pip install -r requirements.txt
   ```
3. Настроить конфигурацию в `.env` (см. `.env.example`).
4. Инициализировать базу данных:
   ```bash
   python scripts/init_db.py
   ```
5. Запустить двигатель:
   ```bash
   python src/main.py
   ```

---

## 📊 Стратегия "Pure Snap"
Бот использует стратегию **Target Sniping**, выставляя лимитные ордера на покупку ниже рыночной цены. 
Алгоритм выбирает цели на основе:
1. Текущей глубины стакана.
2. Истории продаж за последние 7 дней (из SQLite DB).
3. Валидации через CSFloat Oracle.

---

*Phase 7: Pure Quantitative Awakening - Release 2026.*


---
🦅 *DMarket Quantitative engine | v7.0 | 2026*

----- 
🦅 *DMarket Quantitative Engine | v7.0 | 2026*