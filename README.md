# 🦅 DMarket Target Sniper (v3.2)

**Statistical Arbitrage & Limit Market Making Bot for CS2 and Rust skins.**
Автономная торговая система, работающая чисто на математических скриптах и целевом снайпинге (Target Sniping).

---

## 🚀 Основные Возможности

### 1. ⚡ Hardware Acceleration (Phase 14)

- **CUDA Support (`CuPy`):** Марковский предиктор (`markov_model.py`) использует тензорные ядра для мгновенной классификации 10,000+ предметов в одном GPU-пакете.

### 2. 🛡️ Security Hardening (Phase 13)

- **V1-V4 Protection:** Заморозка констант модуля, хранение TLS-отпечатков в **OS Keyring**, HMAC-подпись Git-чекпоинтов.
- **Price Validator:** Жесткий фильтр цен ($0.10–$50,000) для защиты от Data Poisoning и некорректных форматов (напр. `"1e5"`).
- **Trade Gate:** Решение проходит через **Pydantic Gate**, проверяющий лимиты и математические критерии прибыльности (мин 5% маржа).

### 3. 🧠 Smart Math Architecture

- **📊 Markov Chain Predictor:** 3-уровневая классификация рынка (STABLE / VOLATILE / ANOMALOUS). Блокирует аномальные всплески.
- **🎯 Target Sniping:** Обработка стаканов цен, оценка флоатов и стикеров с автоматическим размещением лимитных ордеров (Batch Create).

---

## 🏗 Технический Стек

| Компонент | Технология |
| :--- | :--- |
| **Quant Math** | `cupy` (CUDA 12.x) / `numpy` |
| **Validation** | `pydantic` v2 |
| **Security** | `keyring`, `hashlib` (HMAC-SHA256) |
| **API Client** | Async REST + Ed25519 Signing |

---

## 🛠 Установка и Запуск

### Настройка GPU (WSL2 / Windows)

1. Установить CUDA 12.x.
2. Установить зависимости:

   ```bash
   pip install cupy-cuda12x pydantic keyring
   ```

3. Добавить TLS fingerprint в хранилище:

   ```bash
   python -c "import keyring; keyring.set_password('dmarket_bot', 'cert_fp', '<sha256_hex>')"
   ```

### Запуск

```bash
# Режим сканнера с Марковской фильтрацией и Target Sniping
python src/autonomous_scanner.py
```

---

## ⚙️ Безопасность (`src/trade_gate.py`)

Бот использует **TradeExecutionGate**, который блокирует сделки если:

- Сумма сделки > $50.00 (настраиваемый лимит).
- Цена не прошла повторную валидацию.
- Маржа сделки с учетом комиссии составляет менее 5%.

---

*Phase 14: CUDA Acceleration & Scripting Pipeline Build.*
