# 🚀 Deployment Guide (v14.9)

**Версия**: 14.9.0
**Последнее обновление**: Июнь 2026

---

## 📋 Обзор

Руководство по развертыванию DMarket Quantitative Engine. Поддерживаемые платформы:
- **Docker** (рекомендовано) — x86_64 + ARM64 (Raspberry Pi 4/5, mini-PC, сервер)
- **Bare metal** — Python 3.13+ напрямую на Linux
- **Совместимость**: Intel Celeron, Raspberry Pi 4/5, Steam Deck, любой Linux x86_64/aarch64

---

## 🐳 Docker (Рекомендовано)

### Требования к хосту

| Параметр | Минимум | Рекомендовано |
|---|---|---|
| **CPU** | 1 ядро (x86_64 или ARM64) | 2+ ядра |
| **RAM** | 512 MB | 1+ GB |
| **Диск** | 2 GB свободно | 10+ GB (логи + БД) |
| **ОС** | Linux с Docker 20.10+ | Debian 12, Ubuntu 22.04, Raspberry Pi OS |
| **Docker** | docker + docker compose | docker compose v2 |

### Быстрый запуск

```bash
git clone https://github.com/Dykij/Dmarket_bot.git
cd Dmarket_bot
cp .env.example .env
# Отредактировать .env — заполнить ключи

# Запустить основной бот
docker compose up -d

# Смотреть логи
docker compose logs -f

# Опционально — Telegram admin
docker compose --profile telegram up -d
```

### docker-compose.yml (v14.9)

```yaml
services:
  dmarket_bot:
    build:
      context: .
      dockerfile: Dockerfile
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/app/data       # SQLite persistence
      - ./logs:/app/logs       # Log persistence
    healthcheck:
      test: curl -sf http://127.0.0.1:9091/healthz
    deploy:
      resources:
        limits:
          memory: 512M

  telegram_bot:  # (optional — profile: telegram)
    command: python -m src.telegram.control_bot
    memory: 256M
```

### Команды Docker

```bash
docker compose build              # сборка
docker compose up -d              # запуск
docker compose logs -f            # логи
docker compose down               # остановка
docker compose --profile telegram up -d   # + Telegram
```

---

## 🍓 Raspberry Pi Deployment

### Совместимость

| Модель | Архитектура | RAM | Docker | Вердикт |
|---|---|---|---|---|
| **Pi 5 (4+ GB)** | ARM64 | 4-8 GB | ✅ | ⭐ Лучший |
| **Pi 4 (2+ GB)** | ARM64 | 2-8 GB | ✅ | ⭐ Отлично |
| Pi 400 (4 GB) | ARM64 | 4 GB | ✅ | ✅ Хорошо |
| Pi 3 B+ (1 GB) | ARM64 | 1 GB | ✅ | ⚠️ Тесно |
| Pi Zero 2 W | ARM64 | 512 MB | ⚠️ | ❌ Мало RAM |
| Pi Zero W | ARMv6 | 512 MB | ❌ | ❌ Нет ARM64 |

### Настройка Pi

```bash
# 1. Raspberry Pi OS Lite 64-bit (Bookworm)
# 2. Установка Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 3. Клонирование и запуск
git clone https://github.com/Dykij/Dmarket_bot.git
cd Dmarket_bot
cp .env.example .env
# Заполнить ключи
docker compose up -d
```

**Важно**: Dockerfile автоматически компилирует Rust-модуль под ARM64. 
Python wheels с ARM64-поддержкой есть для всех зависимостей (через piwheels).

---

## 💻 Мини-ПК / Intel Celeron

Подходит любой x86_64 Linux мини-ПК:
- Intel Celeron J4125/N5105/N100 (4 ядра, 4+ GB RAM)
- Intel NUC / ASUS PN-series
- HP EliteDesk / Dell OptiPlex mini
- Lenovo ThinkCentre Tiny

Установка идентична Raspberry Pi: `docker compose up -d`.

---

## 🔧 Manual Deployment (без Docker)

### Требования

- Python 3.13+ (или 3.11+)
- Rust toolchain (только для `maturin`)
- Linux (Debian/Ubuntu recommended)

### Установка

```bash
# Системные зависимости (Debian/Ubuntu)
sudo apt install build-essential curl pkg-config libssl-dev

# Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Проект
git clone https://github.com/Dykij/Dmarket_bot.git
cd Dmarket_bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd src/rust_core && maturin develop --release && cd ../..

# Конфигурация
cp .env.example .env
nano .env

# Запуск
python -m src
```

### Systemd Service

```ini
# /etc/systemd/system/dmarket-bot.service
[Unit]
Description=DMarket Quantitative Engine
After=network.target

[Service]
User=bot
WorkingDirectory=/home/bot/Dmarket_bot
Environment="PATH=/home/bot/Dmarket_bot/.venv/bin"
EnvironmentFile=/home/bot/Dmarket_bot/.env
ExecStart=/home/bot/Dmarket_bot/.venv/bin/python -m src
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable dmarket-bot
sudo systemctl start dmarket-bot
```

---

## 🏭 Production Checklist

- [ ] **DRY_RUN=true** первые 48 часов
- [ ] `.env` permissions: `chmod 600 .env`
- [ ] `data/` и `logs/` в `.gitignore` (уже есть)
- [ ] Memory limits в docker-compose.yml (512M)
- [ ] Health check настроен (HTTP :9091/healthz)
- [ ] Баланс DMarket ≥ $20 (минимум для работы balance-аware)
- [ ] Oracle rate limits configured
- [ ] Telegram bot token жив и без конфликтов
- [ ] Lock file механизм активен (bot.lock)

---

## 📊 Мониторинг

### Health Server (встроенный)
- `http://127.0.0.1:9091/healthz` — основные проверки
- `http://127.0.0.1:9091/readyz` — готовность к работе
- `http://127.0.0.1:9190/metrics` — Prometheus метрики

### Docker healthcheck
```yaml
healthcheck:
  test: ["CMD", "curl", "-sf", "http://127.0.0.1:9091/healthz"]
  interval: 30s
  timeout: 10s
  retries: 3
```

### Telegram Admin
16 кнопок управления: статус, баланс, инвентарь, тест, цены и др.


**Подробнее**: [ARCHITECTURE.md](ARCHITECTURE.md), [QUICK_START.md](QUICK_START.md)


🦅 *DMarket Quantitative Engine | v14.9 | June 2026*
