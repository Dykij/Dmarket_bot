---
name: validate_target_payload
description: 'Use when the user asks to validate a target JSON payload before sending
  it to the API. Trigger keywords: "валидация", "payload", "проверь поля", "float_min",
  "validate target".'
---
# validate_target_payload

Инструкция для валидации пейлоадов перед отправкой в DMarket.
Обязательные проверки: присутствие полей `Amount`, `Price`, `Title`.
Дополнительно: проверка корректности форматирования расширенных фильтров, таких как `float_min` и `float_max`.
