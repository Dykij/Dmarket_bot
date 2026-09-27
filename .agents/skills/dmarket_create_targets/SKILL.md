---
name: dmarket_create_targets
description: 'Use when the user asks to create, place, or execute new buy orders (targets)
  on DMarket. Trigger keywords: "создай таргет", "выстави заявку", "создать ордер
  на покупку", "create target", "buy order", "place order".'
---
# dmarket_create_targets

Используйте этот скилл для создания таргетов.
Эндпоинт: `/marketplace-api/v1/user-targets/create` (POST).
Ожидаемые параметры: `GameID` (для CS:GO это `a8db`), и массив `Targets` (включает `Amount`, `Price`, `Title`).
Роль ИИ: формирование корректного JSON-пейлоада, соблюдение лимитов на количество таргетов и реализация retry-логики при HTTP 400/429.
