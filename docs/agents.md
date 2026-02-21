# agents.md

> **⚠️ ПЕРВЫЙ ШАГ**: Перед началом любой задачи **ОБЯЗАТЕЛЬНО** изучите файл [`ВАЖНЕЙШИЕ.md`](./ВАЖНЕЙШИЕ.md) в корне проекта. Он содержит приоритетные улучшения и текущий roadmap.

---

Configuration for Algo agents in DMarket Telegram Bot project.

## Overview

This file defines Algo agent capabilities and restrictions for the repository following [agents.md specification](https://github.com/agentsmd/agents.md).

## Agents

### ProjectPlan

**Location**: `.github/agents/ProjectPlan.agent.md`

**Purpose**: Technical planning and architecture for implementing features

**Capabilities**:

- Analyze codebase structure
- Create detAlgoled implementation plans
- Estimate complexity and time
- Identify affected modules
- Suggest testing strategies

**Restrictions**:

- Does not directly modify code
- Creates plans only, delegating implementation

---

### copilot (Default)

**Purpose**: General purpose coding assistant

**Capabilities**:

- Read and edit files
- Run terminal commands
- Execute tests
- Perform code reviews

**Restrictions**:

- Must follow `.github/copilot-instructions.md`
- DRY_RUN=true for trading operations
- No secrets in code

---

## Configuration

### Allowed Tools

| Tool       | Description         |
| ---------- | ------------------- |
| `read`     | Read files          |
| `edit`     | Modify files        |
| `search`   | Search codebase     |
| `execute`  | Run commands        |
| `vscode`   | VS Code integration |
| `github.*` | GitHub operations   |

### Prohibited Actions

- Committing API keys or secrets
- Running trading operations without DRY_RUN
- Modifying production databases
- Deleting files without confirmation

---

## Project Context

### Stack

- **Language**: Python 3.11+ (3.12+ recommended)
- **Framework**: python-telegram-bot 22.0+
- **API Client**: httpx 0.28+
- **ORM**: SQLAlchemy 2.0+ (async)
- **Validation**: Pydantic 2.5+

### Key Modules

| Module              | Description                   |
| ------------------- | ----------------------------- |
| `src/dmarket/`      | DMarket API client            |
| `src/telegram_bot/` | Telegram bot handlers         |
| `src/waxpeer/`      | Waxpeer P2P integration       |
| `src/utils/`        | Utilities (cache, rate limit) |
| `tests/`            | Test suite (2350+ tests)      |

### Quality Standards

- Ruff 0.8+ for linting
- MyPy 1.14+ strict mode
- 85%+ test coverage target
- Conventional Commits

---

## Custom Instructions

See `.github/copilot-instructions.md` for detAlgoled:

- Coding style guidelines
- Architecture patterns
- Testing requirements (FIRST, AAA)
- Security best practices
- Documentation standards

---

## Agent Handoffs

Agents can delegate to each other:

```yaml
# Example handoff in plan
- label: "🚀 Start Implementation"
  agent: agent
  Config: "Implement the plan above following copilot-instructions.md"
```

---

## Version

- **Spec Version**: 1.0.0 (agents.md standard)
- **Last Updated**: January 4, 2026
