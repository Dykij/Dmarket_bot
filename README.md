# 🦅 DMarket Quantitative Arbitrage Engine (v7.5)

**High-Performance Deterministic Trading & Target Sniping for CS2 and Rust.**

Автономная торговая система, работающая на строгих математических алгоритмах и количественном анализе рынка. Полностью очищена от legacy-кода и экспериментальных ИИ-моделей в пользу максимальной предсказуемости и профита.

---

## 🚀 Основные Возможности

### 1. 📈 Pure Quantitative Core
- **Deterministic Math:** Все решения о покупке принимаются на основе жесткой формулы прибыли (Net Margin >= 5%) с учетом всех комиссий платформы.
- **Rust Hybrid Extension:** Критические узлы парсинга переписаны на Rust (PyO3) для минимизации задержек и нагрузки на GIL.
- **Balance-Aware Selection:** Динамическая калибровка размера позиций на основе реального баланса аккаунта в реальном времени.

### 2. 🛡️ Protection Layer (The Shield)
- **Trend Guard:** Автоматическая блокировка покупок при обнаружении устойчивого нисходящего тренда (Anti-Crash система).
- **Event Shield (2026):** Динамическая корректировка риск-множителей на основе календаря событий CS2/Rust (Мажоры, Сейлы, Вайпы).
- **HashiCorp Vault Integration:** Безопасное хранение API-ключей в изолированном хранилище.

### 3. ⚡ High-Frequency Readiness
- **Zero-Copy Parsing:** Внедрена высокоскоростная десериализация JSON через Rust-экстеншн.
- **Batch Operations:** Поддержка пакетного создания (`batchCreate`) и удаления таргетов.
- **Telegram Interface:** Управление и мониторинг через защищенного Telegram-бота.

---

## 🏗 Технический Стек

| Компонент | Технология |
| :--- | :--- |
| **Logic Core** | Python 3.14+, Rust (PyO3) |
| **Parsing Engine** | Serde (Rust) / Pydantic (Python) |
| **Database** | SQLite 3 (Persistent History) |
| **Security** | HashiCorp Vault / NACL Ed25519 |
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
3. Скомпилировать Rust-модуль:
   ```bash
   cd src/rust_core
   maturin develop
   ```
4. Настроить конфигурацию в `.env` или через Vault.
5. Запустить двигатель:
   ```bash
   python -m src
   ```

---

## 📊 Стратегия "Pure Snap"
Бот использует стратегию **Target Sniping**, выставляя лимитные ордера на покупку ниже рыночной цены. 
Алгоритм выбирает цели на основе текущей глубины стакана, истории продаж и валидации через **CSFloat Oracle**.

---

*Phase 7: Pure Quantitative Awakening - Release 2026.*

---
🦅 *DMarket Quantitative Engine | v7.5 | 2026*