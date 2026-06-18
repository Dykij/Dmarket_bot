# 🚀 Быстрый старт: DMarket Quantitative Engine (v14.4)

**Дата**: Июнь 2026 г.
**Версия**: 14.4.0
**Концепция**: Balance-Aware Quantitative Trading Engine

---

## ⚠️ РЕЖИМ БЕЗОПАСНОСТИ: DRY_RUN

По умолчанию бот запускается в режиме **DRY_RUN=true**.
- ✅ **Симуляция**: Бот находит сделки, но не отправляет их на биржу.
- ✅ **Ваш баланс защищен**.
- 🔴 **LIVE**: Для реальной торговли установите `DRY_RUN=false` в файле `.env` только после 48 часов успешных тестов.

---

## 📋 Предварительные требования

- ✅ Docker 20.10+ **или** Python 3.13+ + Rust toolchain
- ✅ Telegram Bot Token ([@BotFather](https://t.me/BotFather))
- ✅ DMarket API Keys ([DMarket Profile](https://dmarket.com/profile/api))
- ✅ CS2Cap API Key (Starter $19/mo: [cs2cap.com](https://cs2cap.com))
- ✅ Мини-ПК или Raspberry Pi 4/5 с Linux

---

## 🛠 Быстрый старт (Docker — рекомендовано)

```bash
git clone https://github.com/Dykij/Dmarket_bot.git
cd Dmarket_bot
cp .env.example .env
# Заполните ключи в .env:
#   DMARKET_PUBLIC_KEY, DMARKET_SECRET_KEY, CS2CAP_API_KEY, TELEGRAM_BOT_TOKEN

docker compose up -d          # запуск торгового бота
docker compose logs -f        # смотреть логи
docker compose --profile telegram up -d   # + Telegram admin (опционально)
```

---

## 🛠 Быстрый старт (без Docker)

```bash
# 1. Клонирование
git clone https://github.com/Dykij/Dmarket_bot.git
cd Dmarket_bot

# 2. Виртуальное окружение
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Rust модуль (опционально — есть Python fallback)
cd src/rust_core
maturin develop --release
cd ../..

# 4. Конфигурация
cp .env.example .env
# Заполните ключи

# 5. Запуск
python -m src
```

---

## 🔑 Конфигурация (.env)

Минимальный `.env` для запуска:

```env
# КЛЮЧИ (обязательно)
DMARKET_PUBLIC_KEY=your_key
DMARKET_SECRET_KEY=your_secret
CS2CAP_API_KEY=your_cs2cap_key
TELEGRAM_BOT_TOKEN=your_bot_token
ENCRYPTION_KEY=your_fernet_key

# РЕЖИМ
DRY_RUN=true
```

Полный список — в `.env.example`.

---

## 🧬 v14.4 Новые возможности

### Balance-Aware Trading
- **Dynamic Max Price**: `max($5.00, balance × 10%)`. При $43 → $5, при $500 → $50
- **Reserve Buffer**: $10 всегда неприкосновенны
- **Half Kelly**: Келли (50%) для размера позиции
- **Drawdown Freeze**: При просадке >15% — стоп покупок
- **Capital Velocity**: Минимум 0.5× оборота/неделю

### Docker
- Multi-stage build для x86_64 + ARM64 (Raspberry Pi, Celeron)
- Health check `/healthz`, memory limits, persistent volumes

### Архитектура
- Модули разбиты: cs2cap_oracle (5 файлов), microstructure (4), target_sniping (16+)
- Telegram: 16 кнопок, все исправлены и протестированы
- Тесты: 289 (unit + bottleneck + sandbox)

---

## 📡 Основные команды Telegram (16 кнопок)

| Кнопка | Действие |
|---|---|
| STATUS | Текущий статус + баланс |
| INVENTORY | Просмотр инвентаря |
| BALANCE | Баланс и динамика |
| SELL-TOP | Продажа топ-предмета |
| ANALYZE | Анализ сделок |
| TEST | Тестовый цикл |
| PRICES | Цены на предметы |
| CLOCK | Синхронизация времени |
| REFRESH | Обновление данных |
| PANIC | Отмена всех ордеров |
| STOP/START | Стоп/пуск торговли |
| HELP | Справка по командам |
| LOGOUT | Выход из админ-панели |
| DONATE | Ссылка на донат |
| CANCEL | Отмена операции |


🦅 *DMarket Quantitative Engine | v14.4 | June 2026*
