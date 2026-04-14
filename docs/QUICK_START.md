# 🚀 Быстрый старт: DMarket Quantitative Engine (v7.0)

**Дата**: 14 апреля 2026 г.
**Версия**: 7.0.0
**Концепция**: Чистая математическая торговля (HFT Readiness).

---

## ⚠️ РЕЖИМ БЕЗОПАСНОСТИ: DRY_RUN

По умолчанию бот запускается в режиме **DRY_RUN=true**.
- ✅ **Симуляция**: Бот находит сделки, но не отправляет их на биржу.
- ✅ **Безопасность**: Ваш баланс защищен.
- 🔴 **LIVE**: Для реальной торговли установите `DRY_RUN=false` в файле `.env` только после 48 часов успешных тестов.

---

## 📋 Предварительные требования

- ✅ Python 3.11 или выше
- ✅ Telegram Bot Token ([@BotFather](https://t.me/BotFather))
- ✅ DMarket API Keys ([DMarket Profile](https://dmarket.com/profile/api))
- ✅ SQLite 3 (встроено в Python)

---

## 🛠 Установка

### 1. Клонирование и окружение
```bash
git clone https://github.com/Dykij/Dmarket_bot.git
cd Dmarket_bot
python -m venv .venv
source .venv/bin/activate  # Или .venv\Scripts\activate на Windows
pip install -r requirements.txt
```

### 2. Конфигурация (.env)
Создайте файл `.env`:
```env
TELEGRAM_BOT_TOKEN=your_token
DMARKET_PUBLIC_KEY=your_key
DMARKET_SECRET_KEY=your_secret
DRY_RUN=true
DATABASE_URL=sqlite:///dmarket_trading.db
```

### 3. Инициализация и Запуск
```bash
# Создать таблицы базы данных
python scripts/init_db.py

# Запустить движок
python src/main.py
```

---

## 🧬 Новые функции Phase 7

### 📉 Trend Guard
Бот автоматически блокирует покупки, если цена предмета в SQLite истории показывает негативный тренд (более 3 последовательных падений).

### 🛡 Event Shield
Интеграция с `data/cs2_events.json`. В периоды крупных турниров или распродаж Steam бот автоматически увеличивает целевую маржу для защиты от волатильности.

### 🎯 Target Sniper
Движок ищет предметы с потенциальной прибылью >5% после всех комиссий, используя внешние оракулы цен (CSFloat) для верификации.

---

## 📡 Основные команды Telegram
- `/start` — Главное меню и статус.
- `/balance` — Проверка баланса (DMarket + SQLite stats).
- `/inventory` — Просмотр ваших скинов на площадке.
- `/test_trade` — Тестовая проверка цепочки (DMarket -> Oracle -> Profit).
- `/panic` — Немедленная отмена всех активных таргетов.

---

*Phase 7: Pure Quantitative Awakening.*


---
🦅 *DMarket Quantitative engine | v7.0 | 2026*