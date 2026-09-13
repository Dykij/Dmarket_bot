---
name: difftastic-semantic-diff
description: Use when you need to compare two files or revisions to ensure the diff is semantically meaningful and not just formatting changes. Required before committing any modification.
---

# Difftastic Semantic Diff

Этот инструмент (skill) предписывает проверять коммиты перед их фиксацией на предмет семантически пустых изменений (когда поменялось только форматирование, отступы или пробелы, но не реальный код).

## Правила
1. Перед коммитом любой правки обязательно проверять её через `difftastic` (или аналогичный семантический diff).
2. Если дифф семантически пустой — коммит делать нельзя.
3. Команда проверки: `difft <файл>` (или сравнение веток `difft branch1 branch2`).
