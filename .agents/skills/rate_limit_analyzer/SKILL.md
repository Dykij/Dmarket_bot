---
name: rate_limit_analyzer
description: 'Use when the user asks to analyze API rate limits, backoff strategies,
  or request frequency limits. Trigger keywords: "лимиты", "rate limits", "429", "rps",
  "backoff".'
---
# rate_limit_analyzer

Инструкция по rate-лимитам DMarket.
Анализирует частоту запросов к стакану и эндпоинтам создания/удаления таргетов.
Роль ИИ: использовать эти знания для проектирования асинхронных воркеров с экспоненциальной задержкой (exponential backoff) и недопущения HTTP 429.
