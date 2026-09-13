---
name: tgrep-fast-search
description: Use when you need to perform fast textual searches across large directories using a prebuilt index instead of plain grep.
---

# tgrep Fast Search

Этот инструмент (skill) предписывает агентам использовать `tgrep` вместо голого `grep` для быстрого текстового поиска по большим кодовым базам (когда есть актуальный индекс).

## Правила
1. Для быстрого текстового поиска по большим директориям — использовать `tgrep`.
2. Голый `grep` допускается только точечно (например, для проверки одной конкретной строки в одном или нескольких заранее известных файлах).
