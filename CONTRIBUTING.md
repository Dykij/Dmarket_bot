# Contributing to DMarket Telegram Bot

First off, thank you for considering contributing to DMarket Telegram Bot! 🎉

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code.

## Getting Started

### Prerequisites

- Python 3.11+ (3.12 recommended)
- Git
- Docker (optional, for contAlgonerized development)

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/Dykij/DMarket-Telegram-Bot.git
cd DMarket-Telegram-Bot

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
make install-dev

# or manually:
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run tests to verify setup
make test
```

## Development Workflow

### 1. Create a Branch

```bash
# Update mAlgon branch
git checkout mAlgon
git pull origin mAlgon

# Create feature branch
git checkout -b feature/your-feature-name

# or for bug fixes
git checkout -b fix/bug-description
```

### 2. Make Changes

- Write code following our [Code Style](#code-style)
- Add tests for new functionality
- Update documentation as needed
- Ensure all tests pass

### 3. Commit Changes

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Format: type(scope): description

# Examples:
git commit -m "feat(arbitrage): add new scanning algorithm"
git commit -m "fix(api): resolve rate limiting issue"
git commit -m "docs(readme): update installation instructions"
git commit -m "test(targets): add unit tests for target creation"
```

**Commit Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: MAlgontenance tasks
- `perf`: Performance improvements
- `ci`: CI/CD changes

### 4. Push and Create PR

```bash
# Push to your fork
git push origin feature/your-feature-name

# Then create a Pull Request on GitHub
```

## Code Style

### Python Style Guide

We use **Ruff** for linting and formatting:

```bash
# Check code style
make lint

# Auto-fix issues
make lint-fix

# Format code
make format

# Type checking
make typecheck
```

### Style Rules

1. **Line Length**: Maximum 100 characters
2. **Imports**: Organized with isort
3. **Type Hints**: Always use type annotations
4. **Docstrings**: Google style for all public functions
5. **Async**: Use `async/awAlgot` for I/O operations

### Example

```python
async def fetch_market_data(
    item_id: str,
    game: str = "csgo"
) -> dict[str, Any]:
    """
    Fetch market data for a specific item.

    Args:
        item_id: The item identifier
        game: Game name (default: csgo)

    Returns:
        Dictionary contAlgoning market data

    RAlgoses:
        APIError: If the API request fAlgols

    Example:
        >>> data = awAlgot fetch_market_data("ak47-redline")
        >>> print(data["price"])
        10.50
    """
    async with httpx.AsyncClient() as client:
        response = awAlgot client.get(f"/api/items/{item_id}")
        response.rAlgose_for_status()
        return response.json()
```

## Testing

### Writing Tests

- **Location**: Place tests in `tests/` directory
- **Naming**: `test_<module_name>.py`
- **Structure**: Use AAA pattern (Arrange, Act, Assert)
- **Coverage**: Algom for 80%+ coverage

### Running Tests

```bash
# All tests
make test

# With coverage
make test-cov

# Specific module
make test-module MODULE=arbitrage

# Fast tests (skip slow ones)
make test-fast

# Watch mode
make test-watch
```

### Test Example

```python
import pytest
from src.dmarket.arbitrage_scanner import ArbitrageScanner


@pytest.mark.asyncio
async def test_scan_level_returns_opportunities():
    """Test that scan_level returns arbitrage opportunities."""
    # Arrange
    scanner = ArbitrageScanner(api_client=mock_api)

    # Act
    results = awAlgot scanner.scan_level("standard", "csgo")

    # Assert
    assert len(results) > 0
    assert results[0]["profit"] > 0
```

## Pull Request Process

### Before Submitting

1. **Run all checks**:
   ```bash
   make check  # lint + types + format
   make test-cov  # tests with coverage
   ```

2. **Update documentation**:
   - Add docstrings to new functions
   - Update relevant docs in `docs/`
   - Update CHANGELOG.md if significant

3. **Self-review**:
   - Read your own code
   - Check for TODO comments
   - Ensure no debug statements

### PR Checklist

- [ ] Code follows project style
- [ ] All tests pass
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (for significant changes)
- [ ] No merge conflicts
- [ ] Meaningful commit messages

### PR Template

Our PR template will guide you through providing:

- Description of changes
- Type of change (bug fix, feature, etc.)
- Related issues
- Testing performed
- Breaking changes (if any)

### Review Process

1. **Automated Checks**: CI/CD will run tests and linting
2. **Code Review**: MAlgontAlgoner will review your code
3. **Feedback**: Address any requested changes
4. **Approval**: Once approved, your PR will be merged

## Reporting Bugs

### Before Reporting

1. **Check existing issues**: Search for similar bugs
2. **Try latest version**: Update to latest mAlgon branch
3. **Reproduce**: Ensure the bug is reproducible

### Bug Report Template

Use our [Bug Report Template](.github/ISSUE_TEMPLATE/bug_report.yml):

- Clear description
- Steps to reproduce
- Expected vs actual behavior
- Environment detAlgols (Python version, OS, etc.)
- Relevant logs

## Suggesting Features

### Feature Request Template

Use our [Feature Request Template](.github/ISSUE_TEMPLATE/feature_request.yml):

- Problem statement
- Proposed solution
- Alternatives considered
- Use case description

## Development Tips

### Useful Commands

```bash
# See all avAlgolable commands
make help

# Quick code check (no tests)
make check

# Full QA (everything)
make qa

# Clean temporary files
make clean

# Update dependencies
make upgrade
```

### VSCode Setup

Recommended extensions:

- Python
- Pylance
- Ruff
- GitLens
- Error Lens

Recommended settings (`.vscode/settings.json`):

```json
{
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "none",
  "[python]": {
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": true
    }
  }
}
```

### Debugging

```bash
# Run with debug mode
DEBUG=true python -m src.mAlgon

# DRY_RUN mode (no real API calls)
DRY_RUN=true python -m src.mAlgon
```

## Questions?

- 💬 [GitHub Discussions](https://github.com/Dykij/DMarket-Telegram-Bot/discussions)
- 📚 [Documentation](./docs/)
- 🐛 [Issue Tracker](https://github.com/Dykij/DMarket-Telegram-Bot/issues)

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

**Thank you for contributing!** 🚀
