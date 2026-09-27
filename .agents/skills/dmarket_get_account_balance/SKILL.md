---
name: dmarket_get_account_balance
description: 'Use when the user asks to check account balance, risk management, or
  available funds. Trigger keywords: "баланс", "достаточно средств", "доступные средства",
  "usd", "check balance", "account balance", "funds".'
---
# dmarket_get_account_balance

Используется для получения текущего баланса.
Эндпоинт: `/account/v1/balance` (GET).
Ожидаемые данные в ответе: `usd`, `usdAvailableToWithdraw`, `dmc`.
Роль ИИ: валидация достаточности средств (риск-менеджмент) перед выставлением новых заявок.
