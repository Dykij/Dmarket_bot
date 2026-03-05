# 🦅 DMarket HFT Predator (v3.0)

**High-Frequency Trading Bot for CS2 skins.**
Автономная торговая система, работающая по стратегии "Spread Capture" с элементами умного управления инвентарем.

---

## 🚀 Основные Возможности

### 1. ⚡ HFT Core (Ядро)
- **Скорость:** Сканирует 100+ предметов за 2-3 секунды (SACS-2026 Optimized).
- **Стратегия:** Ищет предметы, где разница между покупкой (Bid) и продажей (Ask) превышает динамический спред.
- **Resilience:** Circuit Breaker (пауза при ошибках API) + Token Bucket Rate Limiter (5 RPS).

### 2. 🧠 Smart Logic (Интеллект)
- **📊 ML Price Prediction:** Интегрированная регрессия (`scikit-learn`) для предсказания тренда и адаптивного порога прибыли.
- **🧱 Wall Breaker:** Бот анализирует "стакан" цен. Если разрыв между 1-м и 2-м продавцом большой (>2%), бот не демпингует, а встает по высокой цене (под 2-го продавца), увеличивая маржу.
- **⏳ Inventory Decay:** Если предмет завис в инвентаре (>24ч), бот автоматически снижает цену на 1% каждые 24 часа.
- **🎯 Smart Targeting:** Фильтр по Float Value с использованием Pydantic-валидации всех ответов DMarket.

### 3. 📱 Telegram & Monitoring
- **📢 Real-time Alerts:** Мгновенные уведомления о каждой ставке и продаже.
- **📈 SQLite Tracker:** Все сделки сохраняются в локальную БД для анализа доходности.
- **💬 Telegram Control Center:** `/start`, `/stop`, `/panic`, `/balance`, `/status`.

---

## 🛠 Установка и Запуск

### Требования
- Python 3.11+
- Аккаунт DMarket (Public/Secret Keys)
- Telegram Bot Token (от @BotFather)

### Настройка
1. Клонировать репозиторий.
2. Создать файл `.env`:
   ```env
   DMARKET_PUBLIC_KEY=your_public_key
   DMARKET_SECRET_KEY=your_secret_key
   TELEGRAM_BOT_TOKEN=your_tg_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```
3. Установить зависимости:
   ```bash
   pip install -r requirements.txt
   ```

### Запуск
```bash
# Запуск Telegram-интерфейса (рекомендуется)
python src/telegram_bot.py

# Или запуск ядра напрямую в консоли
python src/bot/main.py
```

---

## ⚙️ Конфигурация (`src/config.py`)

| Параметр | Описание | Дефолт |
| :--- | :--- | :--- |
| `DRY_RUN` | Режим симуляции (без траты денег) | `True` |
| `MIN_SPREAD_PCT` | Минимальная прибыль для входа | `7.0%` |
| `MAX_PRICE_USD` | Максимальная цена предмета | `$20.00` |
| `WALL_BREAKER_PCT` | Порог для стратегии "Пробой Стены" | `2.0%` |

---

## 🏗 Архитектура
Проект очищен от легаси-кода.
- `src/bot/scanner.py` — Глаза (Поиск спредов).
- `src/bot/trader.py` — Руки (Покупка, Таргеты).
- `src/bot/sales.py` — Продажи (Wall Breaker, Decay).
- `src/telegram_bot.py` — Мозг (Управление).

---

*DevOp Branch. Stable Build v3.0.*
