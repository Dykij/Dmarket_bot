---
name: RAW Output Discipline
description: Enforces pagination (redirect to file, wc -l, view_file by line range) for potentially large command outputs instead of truncating or summarizing them.
trigger: always_on
---
Любая команда, вывод которой потенциально большой (grep по всему дереву, полный дамп файла, вывод тестов, JSON-конфиги) — перенаправляется в файл (`> /tmp/output.txt` или в рабочую scratch-директорию), затем `wc -l` для получения точного размера, затем чтение через `view_file` постранично (`StartLine`/`EndLine`) до полного покрытия. Формулировки вроде "вывод обрезан для читаемости" или показ только начала/конца длинного вывода без явного указания диапазона запрещены — вместо этого либо показывается весь диапазон постранично, либо явно указывается "показаны строки X-Y из Z, остальное доступно по запросу".
