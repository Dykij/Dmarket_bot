---
name: full-test-suite
description: "Use ONLY when the user asks to run all tests, the full test suite, or verify the bot works. Trigger keywords: \"run tests\", \"run all tests\", \"test suite\", \"прогони тесты\", \"проверь всё\", \"full test\", \"все тесты\". Runs pytest unit tests + sandbox full cycle + strategy simulation."
---

# Full Test Suite

Run the complete test suite: `pytest` over `tests/`.

## Prerequisites

- `.env` with DMarket API keys
- Python venv at `.venv/` with all dependencies
- For production-like sandbox: `ENCRYPTION_KEY` env var

## Run Steps

```bash
source .venv/bin/activate

# Full test suite
python -m pytest tests/ -q --tb=short
```

## Expected Results

- **Full suite**: `pytest` завершается кодом 0; число тестов не фиксируется, брать из RAW-вывода.

## What Gets Tested

Все тесты в `tests/`: `api`, `core`, `db`, `e2e`, `integration`, `risk`, `trading`, `unit` и файлы верхнего уровня `tests/test_*.py`.

## Related Files

- `tests/risk/` — тесты управления рисками
- `tests/test_logging_config.py` — фикстуры и проверки логирования
