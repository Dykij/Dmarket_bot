---
name: dmarket_remove_targets
description: 'Use when the user asks to remove, cancel, or delete targets (buy orders),
  or for repricing targets. Trigger keywords: "сними ордера", "удали таргеты", "репрайсинг",
  "remove targets", "cancel orders", "reprice".'
---
# dmarket_remove_targets

Используется для снятия таргетов.
Эндпоинт: `/marketplace-api/v1/user-targets/delete` (POST).
Роль ИИ: реализация логики репрайсинга через цикл удаления старого ордера и создания нового с минимальной сетевой задержкой.
