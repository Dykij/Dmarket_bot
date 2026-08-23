---
name: Dmarket_bot Guardrails
description: Project specific rules and constraints for Dmarket_bot
trigger: always_on
---

# Project Guardrails

1. **NO Trading Logic Changes**: Do not change the core trading logic unless explicitly authorized.
2. **200 OK ≠ correct data**: Always verify the actual content of API responses, a 200 status code is not enough.
3. **RAW Requirements**: Always use RAW output from commands when investigating (e.g. raw git commands, ps, etc.) instead of relying on memory or summaries.
4. **NO Main Branch Merges**: Do not merge into the `main` branch outside of the infra-perimeter without explicit approval.
5. **No Virtual Inventory Seeding**: Do not seed virtual inventory.
6. **No Raw Git Push**: `git push` is restricted and requires manual review. Do not run destructive git commands without asking.

7. **RAW-Output Mandate**: Ни один вывод отчёта не может содержать утверждение о результате команды без вставленного RAW-вывода этой команды в том же сообщении. Если команда не выполнялась — так и написать.
8. **Checklist Discipline**: При выполнении checklist-задачи каждый пункт закрывается только после вставки RAW-вывода соответствующей команды непосредственно под этим пунктом, а не общим текстом в конце.
9. **OS-level Protection**: OS-level защита (rm/git/docker wrappers + pre-push hook) обеспечивает 2-шаговое подтверждение, не hard-enforcement. Дальнейшее усиление (SELinux/контейнер) не в скоупе текущего проекта — принято как остаточный риск.
