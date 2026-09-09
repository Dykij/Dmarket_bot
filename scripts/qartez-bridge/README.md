# qartez-bridge

Нативная MCP-интеграция qartez-mcp с Antigravity не работает из-за протокольной
несовместимости (Antigravity отправляет server/discover перед initialize,
rmcp-реализация qartez обрывает соединение). Апстрим-фикса нет. Используй этот
скрипт как ручной мост к 43 инструментам qartez.

Использование: python3 query.py <tool_name> [path]
Пример: python3 query.py qartez_impact src/core/target_sniping/ranking.py
