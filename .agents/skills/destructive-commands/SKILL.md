---
name: destructive-commands
description: Rules for executing destructive or irreversible commands.
---

# Destructive Commands

## User Confirmation Required
Все деструктивные команды требуют явного подтверждения пользователя перед выполнением.

К ним относятся:
- `rm` или `rm -rf` для любых файлов, кроме временных (`/tmp/` или `scratch/`).
- `git push --force` или любые `git push` без PR-ревью (raw push is forbidden).
- Удаление таблиц в базе данных (`DROP TABLE`, `DELETE FROM` без `WHERE`).
- Удаление или изменение конфигурационных файлов на проде.

Если вам нужно выполнить такую команду, остановитесь, запросите подтверждение (STOP AND WAIT), и только после 'Да' от пользователя продолжайте выполнение.
