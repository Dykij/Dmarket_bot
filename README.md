# 🦅 DMarket HFT Predator (v3.1)

**High-Frequency Trading Bot for CS2 skins.**
Автономная торговая система, работающая по гибридной схеме: **Rigid Math (Markov) + Fluid AI (LLM) + Agentic Sandbox.**

---

## 🚀 Основные Возможности

### 1. ⚡ Hardware Acceleration (Phase 14)

- **CUDA Support (`CuPy`):** Марковский предиктор (`markov_model.py`) использует тензорные ядра для мгновенной классификации 10,000+ предметов в одном GPU-пакете.
- **LLM Engine (`GGUF`):** Инференс Arkady 27B через `llama-cpp-python` с полным оффлоудом на VRAM (RTX 5060 Ti) и поддержкой **Flash Attention 2**.

### 2. 🛡️ Security Hardening (Phase 13)

- **V1-V4 Protection:** Заморозка констант модуля, хранение TLS-отпечатков в **OS Keyring**, HMAC-подпись Git-чекпоинтов.
- **Price Validator:** Жесткий фильтр цен ($0.10–$50,000) до вызова ИИ, защита от Data Poisoning и некорректных форматов (напр. `"1e5"`).
- **Agentic Sandbox:** ИИ не имеет прямого доступа к API. Решение проходит через **Pydantic Gate**, проверяющий лимиты и уверенность (Confidence).

### 3. 🧠 Hybrid Architecture

- **📊 Markov Chain Predictor:** 3-уровневая классификация рынка (STABLE / VOLATILE / ANOMALOUS). Блокирует аномальные всплески до LLM-анализа.
- **🎯 Smart Logic:** Обработка стаканов, Wall Breaker и автоматическое управление инвентарем.

---

## 🏗 Технический Стек

| Компонент | Технология |
| :--- | :--- |
| **Quant Math** | `cupy` (CUDA 12.x) / `numpy` |
| **LLM Inference** | `llama-cpp-python` (GGUF Q4_K_M) |
| **Validation** | `pydantic` v2 |
| **Security** | `keyring`, `hashlib` (HMAC-SHA256) |
| **API Client** | Async REST + Ed25519 Signing |

---

## 🛠 Установка и Запуск

### Настройка GPU (WSL2 / Windows)

1. Установить CUDA 12.x.
2. Установить зависимости:

   ```bash
   pip install cupy-cuda12x pydantic keyring llama-cpp-python
   ```

3. Добавить TLS fingerprint в хранилище:

   ```bash
   python -c "import keyring; keyring.set_password('dmarket_bot', 'cert_fp', '<sha256_hex>')"
   ```

### Запуск

```bash
# Режим сканнера с Марковской фильтрацией и GGUF-анализом
python src/autonomous_scanner.py
```

---

## ⚙️ Безопасность (`src/trade_gate.py`)

Бот использует **TradeExecutionGate**, который блокирует сделки если:

- `Confidence` модели < 70%.
- Сумма сделки > $50.00 (настраиваемый лимит).
- Цена не прошла повторную валидацию после ответа ИИ.

---

*Phase 14: CUDA Acceleration & Agentic Sandbox Build.*
