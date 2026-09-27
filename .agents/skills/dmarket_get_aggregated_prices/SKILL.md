---
name: dmarket_get_aggregated_prices
description: 'Use when the user asks to get aggregated prices, order book depth, or
  market spread. Trigger keywords: "срез стакана", "агрегированные цены", "лучшие
  цены", "спрос и предложение", "aggregated prices", "order book".'
---
# dmarket_get_aggregated_prices

Этот скилл предоставляет инструкции для получения агрегированных цен (Market Depth). Используйте эндпоинт `/price-aggregator/v1/aggregated-prices`.
Входные параметры запроса: `limit`, `cursor`, `filter.game` (`a8db` для CS2), `filter.titles[]`.
Ответ должен содержать массив `aggregatedPrices` с полями `orderBestPrice`, `orderCount`, `offerBestPrice`, `offerCount`.
Роль ИИ: использовать эти данные для построения стен ликвидности и оценки спреда.
