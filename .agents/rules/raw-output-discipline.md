---
name: RAW Output Discipline
description: Enforces strict inclusion of RAW command outputs, forbids summarization, and specifies how to handle large outputs.
trigger: always_on
---

# RAW-Output Discipline

1. **RAW-Output Mandate**: Ни один вывод отчёта не может содержать утверждение о результате команды без вставленного RAW-вывода этой команды в том же сообщении. Если команда не выполнялась — так и написать. (Always use RAW output from commands when investigating instead of relying on memory or summaries).
2. **No Truncation Rule**: Never omit, summarize, or hide RAW command output for length or brevity reasons. If output is genuinely long, split it across multiple messages in full.
3. **Large Output Handling**: Любая команда, вывод которой потенциально большой (grep по всему дереву, полный дамп файла, вывод тестов, JSON-конфиги) — перенаправляется в файл (`> /tmp/output.txt` или в рабочую scratch-директорию), затем `wc -l` для получения точного размера, затем чтение через `view_file` постранично (`StartLine`/`EndLine`) до полного покрытия. Формулировки вроде "вывод обрезан для читаемости" или показ только начала/конца длинного вывода без явного указания диапазона запрещены.
4. **Message Regeneration Integrity**: Если хук/система блокирует отправку сообщения, НЕЛЬЗЯ отбрасывать или пересказывать своими словами уже подготовленный RAW-контент этого сообщения. Нужно закрыть ТОЛЬКО конкретную причину блокировки (например, дозаполнить task.md) и отправить ИСХОДНЫЙ контент как есть, добавив при необходимости краткое объяснение блокировки — не вместо данных, а вместе с ними. Если исходный текст сообщения физически недоступен для восстановления — ОБЯЗАН заново выполнить команды, а не извиняться и продолжать без данных. Для RAW-вывода команд, если есть риск потери при пересборке сообщения — цитировать из .agents/logs/RAW_OUTPUT.log (туда пишет raw-output-logger автоматически), а не восстанавливать по памяти.
