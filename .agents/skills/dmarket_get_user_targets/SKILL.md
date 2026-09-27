---
name: dmarket_get_user_targets
description: 'Use when the user asks to check the status of their active buy orders
  or targets. Trigger keywords: "мои ордера", "статус таргетов", "активные заявки",
  "my targets", "active orders", "user targets".'
---
# dmarket_get_user_targets

Инструкция для чтения собственных выставленных ордеров (targets).
Эндпоинт: `/marketplace-api/v1/user-targets` (GET).
Входные параметры: `gameId` (обязательно), `title`, `treeFilters`, `limit`, `cursor`.
Ожидаемые данные: `targetId`, `status`, `priceCents` (из поля `Amount` в структуре `Price`), `amount`, `attributes`.
Роль ИИ: сличение цены с лучшими ценами конкурентов, сигнал, если ордер перебит.
