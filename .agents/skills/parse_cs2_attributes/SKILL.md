---
name: parse_cs2_attributes
description: 'Use when the user asks to parse CS2 specific item attributes like float,
  paint index, or stickers from raw JSON. Trigger keywords: "флоат", "паттерн", "float
  value", "paint index", "parse attributes", "cs2 attributes", "извлеки".'
---
# parse_cs2_attributes

Инструкция по локальному парсингу атрибутов CS2.
Скилл не делает сетевых запросов. Он разбирает сырой JSON-объект DMarket и извлекает: float value, paint index/seed, стикеры, статус Souvenir или StatTrak.
Цель: извлечение реальной ценности предмета для стратегий торговли.
