# Makefile for DMarket Bot project management
# Использует современные инструменты: Ruff, MyPy, pytest
# Best practices: переменные, .PHONY targets, справка

# ============================================================================
# SHELL CONFIGURATION
# ============================================================================

.ONESHELL:  # Все команды цели выполняются в одной shell-сессии

# ============================================================================
# ПЕРЕМЕННЫЕ (Variables for flexibility)
# ============================================================================

PYTHON ?= python
PIP := $(PYTHON) -m pip
VENV := .venv

# Определение ОС для правильных путей
ifeq ($(OS),Windows_NT)
    VENV_BIN := $(VENV)\Scripts
    # Используем backslash для Windows
    VENV_PYTHON := $(VENV)\Scripts\python.exe
    VENV_PIP_CMD := $(VENV)\Scripts\python.exe -m pip
    VENV_ACTIVATE := $(VENV_BIN)\activate
    # Windows cmd.exe команды
    RM_DIR = if exist $(1) rmdir /s /q $(1)
    RM_FILE = if exist $(1) del /q $(1)
    MKDIR = if not exist $(1) mkdir $(1)
    SEP := &&
else
    VENV_BIN := $(VENV)/bin
    VENV_PYTHON := $(VENV_BIN)/python
    VENV_PIP_CMD := $(VENV_PYTHON) -m pip
    VENV_ACTIVATE := $(VENV_BIN)/activate
    RM_DIR = rm -rf $(1)
    RM_FILE = rm -f $(1)
    MKDIR = mkdir -p $(1)
    SEP := ;
endif

VENV_PIP := $(VENV_PIP_CMD)
PROJECT_NAME := dmarket-telegram-bot

# Опции инструментов (настраиваемые)
RUFF_OPTS ?= --fix --exit-non-zero-on-fix
RUFF_FORMAT_OPTS ?=
MYPY_OPTS ?= --config-file=pyproject.toml --show-error-codes --pretty
PYTEST_OPTS ?= -v --tb=short
PYTEST_COV_OPTS ?= --cov=src --cov-report=html --cov-report=term-missing --cov-report=xml

# Цвета для вывода (опционально)
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m  # No Color

# ============================================================================
# PHONY TARGETS (предотвращает конфликты с файлами)
# ============================================================================

.PHONY: help install dev clean lint format test test-cov coverage docs run \
        check-types qa docker-build docker-run docker-stop pre-commit setup \
        all fix check check-format test-fast docker-logs pre-push update-deps \
        security-check bandit safety debug-fast lint-fast types-fast test-core debug-full \
        test-property test-contracts vulture interrogate test-all-tools

# ============================================================================
# ОСНОВНЫЕ КОМАНДЫ
# ============================================================================

# Справка по командам
help:
	@echo ============================================================================
	@echo   DMarket Bot - Makefile команды
	@echo ============================================================================
	@cmd /c echo.
	@echo Установка и настройка:
	@echo   setup          - Полная настройка окружения разработки
	@echo   install        - Установить зависимости проекта
	@echo   dev            - Установить зависимости для разработки
	@cmd /c echo.
	@echo Проверка качества кода:
	@echo   lint           - Проверка кода линтером (Ruff)
	@echo   format         - Форматирование кода (Ruff format)
	@echo   check-types    - Проверка типов (MyPy)
	@echo   fix            - Автоисправление + форматирование
	@echo   check          - Полная проверка (lint + types + format)
	@echo   qa             - Quality Assurance (все проверки + тесты)
	@echo   bandit         - Проверка безопасности кода
	@echo   safety         - Проверка уязвимостей зависимостей
	@echo   security-check - Полная проверка безопасности
	@cmd /c echo.
	@echo Тестирование:
	@echo   test           - Запуск тестов
	@echo   test-cov       - Тесты с покрытием кода
	@echo   test-parallel  - Параллельные тесты (быстрее)
	@echo   test-module    - Тесты конкретного модуля (MODULE=имя)
	@echo   coverage       - Детальный отчет о покрытии
	@cmd /c echo.
	@echo Разработка:
	@echo   run            - Запустить бота
	@echo   clean          - Очистить временные файлы
	@echo   docs           - Сгенерировать документацию
	@echo   pre-commit     - Установить pre-commit хуки
	@echo   update-deps    - Обновить зависимости
	@cmd /c echo.
	@echo Docker:
	@echo   docker-build   - Собрать Docker образ
	@echo   docker-run     - Запустить в Docker
	@echo   docker-stop    - Остановить Docker контейнеры
	@cmd /c echo.
	@echo Комбинированные:
	@echo   all            - Полная проверка + сборка
	@cmd /c echo.
	@echo Оптимизированные (для GitHub Copilot / IDE):
	@echo   debug-fast     - Быстрая отладка (lint + types + tests) - НЕ ЗАВИСАЕТ
	@echo   lint-fast      - Только линтинг (самая быстрая проверка)
	@echo   types-fast     - Только типы с агрессивным кэшем
	@echo   test-core      - Только core тесты (5 сек таймаут)
	@echo   debug-full     - Полная отладка с лимитами вывода
	@cmd /c echo.
	@echo ============================================================================

# ============================================================================
# УСТАНОВКА И НАСТРОЙКА
# ============================================================================

# Создание виртуального окружения
$(VENV):
	$(PYTHON) -m venv $(VENV)

# Установка зависимостей проекта
install: $(VENV)
	@echo Установка зависимостей...
	@$(VENV_PIP) install --upgrade pip setuptools wheel
	@$(VENV_PIP) install -r requirements.txt

# Установка зависимостей для разработки
dev: $(VENV)
	@echo Установка dev зависимостей...
	@$(VENV_PIP) install --upgrade pip setuptools wheel
	@$(VENV_PIP) install -e ".[dev]"
	@echo Dev окружение готово!

# Полная настройка окружения разработки
setup: $(VENV) install dev pre-commit
	@echo Окружение разработки полностью настроено!

# Установка pre-commit хуков
pre-commit: $(VENV)
	@echo Установка pre-commit хуков...
	@$(VENV_PYTHON) -m pre_commit install

# ============================================================================
# ПРОВЕРКА КАЧЕСТВА КОДА
# ============================================================================

# Линтинг кода с Ruff
lint: $(VENV)
	@echo Проверка кода линтером...
	@$(VENV_PYTHON) -m ruff check $(RUFF_OPTS) .

# Форматирование кода
format: $(VENV)
	@echo Форматирование кода...
	@$(VENV_PYTHON) -m ruff format $(RUFF_FORMAT_OPTS) .

# Проверка типов с MyPy
check-types: $(VENV)
	@echo Проверка типов...
	@$(VENV_PYTHON) -m mypy $(MYPY_OPTS) src/

# Автоматическое исправление + форматирование
fix: $(VENV)
	@echo Автоисправление и форматирование...
	@$(VENV_PYTHON) -m ruff check --fix .
	@$(VENV_PYTHON) -m ruff format .
	@echo Код исправлен и отформатирован!

# Проверка форматирования (без изменений)
check-format: $(VENV)
	@echo Проверка форматирования...
	@$(VENV_PYTHON) -m ruff format --check .

# Полная проверка (lint + types + format check)
check: $(VENV)
	@echo Полная проверка кода...
	@cmd /c echo.
	@echo 1. Линтинг...
	@$(VENV_PYTHON) -m ruff check .
	@cmd /c echo.
	@echo 2. Проверка форматирования...
	@$(VENV_PYTHON) -m ruff format --check .
	@cmd /c echo.
	@echo 3. Проверка типов...
	@$(VENV_PYTHON) -m mypy $(MYPY_OPTS) src/
	@cmd /c echo.
	@echo Все проверки пройдены!

# Проверка безопасности с Bandit
bandit: $(VENV)
	@echo Проверка безопасности (Bandit)...
	@$(VENV_PYTHON) -m bandit -r src/ -c pyproject.toml

# Проверка уязвимостей зависимостей
safety: $(VENV)
	@echo Проверка уязвимостей зависимостей...
	@$(VENV_PYTHON) -m safety check --json

# Полная проверка безопасности
security-check: bandit safety
	@echo Проверка безопасности завершена!

# Quality Assurance - все проверки + тесты
qa: check test-cov
	@cmd /c echo.
	@echo Quality Assurance пройден успешно!

# ============================================================================
# ТЕСТИРОВАНИЕ
# ============================================================================

# Запуск тестов (через poetry для правильного окружения)
test: $(VENV)
	@echo Запуск тестов...
	@poetry run pytest $(PYTEST_OPTS)

# Тесты с покрытием кода
test-cov: $(VENV)
	@echo Запуск тестов с измерением покрытия...
	@poetry run pytest $(PYTEST_COV_OPTS)

# Детальный отчет о покрытии
coverage: test-cov
	@echo Открыть HTML отчет: htmlcov/index.html

# Быстрые тесты (без покрытия, с таймаутом 10 сек)
test-fast: $(VENV)
	@echo Быстрые тесты (без coverage, timeout=10s)...
	@poetry run pytest -c config/pytest-fast.ini tests/ -q --timeout=10 --no-cov -x

# E2E тесты
test-e2e: $(VENV)
	@echo E2E тесты...
	@poetry run pytest tests/e2e/ -v -m e2e

# Только юнит-тесты
test-unit: $(VENV)
	@echo Юнит-тесты...
	@poetry run pytest tests/unit/ -v

# Параллельные тесты (быстрее)
test-parallel: $(VENV)
	@echo Параллельные тесты...
	@poetry run pytest -n auto $(PYTEST_OPTS)

# Тесты для конкретного модуля
test-module: $(VENV)
	@echo Тесты модуля: $(MODULE)
	@poetry run pytest tests/test_$(MODULE).py -v

# ============================================================================
# РАЗРАБОТКА
# ============================================================================

# Запуск бота
run: $(VENV)
	@echo Запуск бота...
	@$(VENV_PYTHON) -m src.main

# Генерация документации
docs: $(VENV)
	@echo Генерация документации...
	@$(VENV_PYTHON) -m sphinx -b html docs/source docs/build/html

# Обновление зависимостей
update-deps: $(VENV)
	@echo Обновление зависимостей...
	@$(VENV_PIP) install --upgrade pip setuptools wheel
	@$(VENV_PIP) install --upgrade -r requirements.txt
	@echo Зависимости обновлены!

# Генерация ключа шифрования для Fernet
generate-encryption-key: $(VENV)
	@echo Генерация ключа шифрования (Fernet)...
	@$(VENV_PYTHON) -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
	@echo ""
	@echo "Скопируйте ключ выше в ENCRYPTION_KEY в .env файле"
	@echo "ВНИМАНИЕ: Без этого ключа при DRY_RUN=false бот не запустится!"

# Очистка временных файлов
clean:
	@echo Очистка временных файлов...
ifeq ($(OS),Windows_NT)
	-@if exist build rmdir /s /q build 2>nul
	-@if exist dist rmdir /s /q dist 2>nul
	-@if exist htmlcov rmdir /s /q htmlcov 2>nul
	-@if exist .pytest_cache rmdir /s /q .pytest_cache 2>nul
	-@if exist .ruff_cache rmdir /s /q .ruff_cache 2>nul
	-@if exist .mypy_cache rmdir /s /q .mypy_cache 2>nul
	-@if exist coverage.xml del /q coverage.xml 2>nul
	-@if exist coverage.json del /q coverage.json 2>nul
	-@if exist .coverage del /q .coverage 2>nul
	-@for /d /r %%i in (__pycache__) do @if exist "%%i" rmdir /s /q "%%i" 2>nul
	-@for /d /r %%i in (*.egg-info) do @if exist "%%i" rmdir /s /q "%%i" 2>nul
else
	-@rm -rf build dist htmlcov .pytest_cache .ruff_cache .mypy_cache 2>/dev/null
	-@rm -f coverage.xml coverage.json .coverage 2>/dev/null
	-@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
	-@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null
endif
	@echo Очистка завершена!

# ============================================================================
# DOCKER
# ============================================================================

# Сборка Docker образа
docker-build:
	@echo Сборка Docker образа...
	docker-compose build

# Запуск в Docker
docker-run:
	@echo Запуск в Docker...
	docker-compose up -d

# Остановка Docker контейнеров
docker-stop:
	@echo Остановка Docker...
	docker-compose down

# Логи Docker
docker-logs:
	docker-compose logs -f

# ============================================================================
# КОМБИНИРОВАННЫЕ КОМАНДЫ
# ============================================================================

# Полная проверка + сборка
all: clean qa docs docker-build
	@cmd /c echo.
	@echo Все задачи выполнены успешно!

# Подготовка к коммиту
pre-push: fix check test-cov
	@cmd /c echo.
	@echo Готово к push!

# ============================================================================
# ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ (из рекомендаций senior dev)
# ============================================================================

# Composite check - форматирование + линтинг + типы (без тестов)
fast-check: $(VENV)
	@echo === Быстрая проверка кода ===
	@echo.
	@echo [1/3] Форматирование...
	@$(VENV_PYTHON) -m ruff format --check .
	@echo.
	@echo [2/3] Линтинг...
	@$(VENV_PYTHON) -m ruff check . --output-format=concise
	@echo.
	@echo [3/3] Типы...
	@$(VENV_PYTHON) -m mypy src/ --cache-dir .mypy_cache --no-error-summary
	@echo.
	@echo ✅ Быстрая проверка завершена!

# ============================================================================
# ОПТИМИЗИРОВАННЫЕ КОМАНДЫ ДЛЯ GITHUB COPILOT / IDE
# ============================================================================

# Быстрая полная отладка для GitHub Copilot (не зависает)
debug-fast: $(VENV)
	@echo === ⚡ Быстрая отладка (GitHub Copilot / IDE) ===
	@echo [1/3] Ruff lint (быстрый)...
	@$(VENV_PYTHON) -m ruff check src/ --output-format=concise --exit-zero 2>&1 | head -50 || true
	@echo.
	@echo [2/3] MyPy (минимальный, с кэшем)...
	@$(VENV_PYTHON) -m mypy src/ --config-file=config/mypy-fast.ini --cache-dir=.mypy_cache 2>&1 | head -30 || true
	@echo.
	@echo [3/3] Тесты (быстрые, 10 сек таймаут)...
	@poetry run pytest tests/core/ tests/unit/ -c config/pytest-fast.ini -q --timeout=5 --no-cov -x 2>&1 | head -50 || true
	@echo.
	@echo ✅ Быстрая отладка завершена!

# Только линтинг (самая быстрая проверка)
lint-fast: $(VENV)
	@echo === Быстрый линтинг ===
	@$(VENV_PYTHON) -m ruff check src/ --output-format=concise --exit-zero 2>&1 | head -100

# Только типы с агрессивным кэшированием
types-fast: $(VENV)
	@echo === Быстрая проверка типов ===
	@$(VENV_PYTHON) -m mypy src/ --config-file=config/mypy-fast.ini --cache-dir=.mypy_cache 2>&1 | head -50

# Только core тесты (быстрее всего)
test-core: $(VENV)
	@echo === Core тесты (быстрые) ===
	@poetry run pytest tests/core/ -c config/pytest-fast.ini -q --timeout=5 --no-cov

# Полная отладка с ограничениями вывода (для IDE)
debug-full: $(VENV)
	@echo === 🔍 Полная отладка с лимитами вывода ===
	@echo.
	@echo [1/4] Форматирование...
	@$(VENV_PYTHON) -m ruff format --check src/ 2>&1 | head -20 || true
	@echo.
	@echo [2/4] Линтинг...
	@$(VENV_PYTHON) -m ruff check src/ --output-format=concise 2>&1 | head -50 || true
	@echo.
	@echo [3/4] Типы...
	@$(VENV_PYTHON) -m mypy src/ --config-file=config/mypy-fast.ini 2>&1 | head -50 || true
	@echo.
	@echo [4/4] Тесты (unit + core)...
	@poetry run pytest tests/core/ tests/unit/ -c config/pytest-fast.ini -q --timeout=10 --no-cov 2>&1 | tail -30 || true
	@echo.
	@echo ✅ Полная отладка завершена!

# Incremental MyPy с кэшем (для CI)
typecheck-ci: $(VENV)
	@echo Проверка типов (incremental mode)...
	@$(VENV_PYTHON) -m mypy src/ --cache-dir .mypy_cache --incremental

# Оптимизированные тесты (только измененные файлы)
test-lf: $(VENV)
	@echo Тесты последних неудачных...
	@$(VENV_PYTHON) -m pytest --lf $(PYTEST_OPTS)

# Полная проверка для CI (без интерактива)
ci-check: $(VENV)
	@echo === CI: Полная проверка ===
	@$(VENV_PYTHON) -m ruff format --check .
	@$(VENV_PYTHON) -m ruff check . --output-format=github
	@$(VENV_PYTHON) -m mypy src/ --cache-dir .mypy_cache --incremental
	@$(VENV_PYTHON) -m pytest $(PYTEST_COV_OPTS) --junitxml=build/test-results/pytest.xml
	@echo ✅ CI проверка завершена!



# ============================================================================
# ДОПОЛНИТЕЛЬНЫЕ ИНСТРУМЕНТЫ ТЕСТИРОВАНИЯ
# ============================================================================

# Property-based тесты (Hypothesis)
test-property: $(VENV)
@echo === 🎲 Property-based тесты (Hypothesis) ===
@$(VENV_PYTHON) -m pytest tests/property_based/ -v --timeout=30 --no-cov

# Контрактные тесты (Pact)
test-contracts: $(VENV)
@echo === 📜 Контрактные тесты (Pact) ===
@$(VENV_PYTHON) -m pytest tests/contracts/ -v --timeout=30 --no-cov

# Поиск мёртвого кода (Vulture)
vulture: $(VENV)
@echo === 🦅 Поиск мёртвого кода (Vulture) ===
@$(VENV_PYTHON) -m vulture src/ --min-confidence 90 2>&1 | head -50 || true
@echo.
@echo Примечание: Некоторые ложные срабатывания для параметров функций нормальны

# Проверка docstrings (Interrogate)
interrogate: $(VENV)
@echo === 📚 Проверка docstrings (Interrogate) ===
@$(VENV_PYTHON) -m interrogate src/ --quiet --fail-under=0 || true

# Проверка безопасности (Bandit)
bandit-check: $(VENV)
@echo === 🔒 Проверка безопасности (Bandit) ===
@$(VENV_PYTHON) -m bandit -r src/ -c pyproject.toml -f txt 2>&1 | head -80 || true

# Запуск ВСЕХ дополнительных инструментов тестирования
test-all-tools: $(VENV)
@echo.
@echo ============================================================================
@echo "   🧰 ЗАПУСК ВСЕХ ИНСТРУМЕНТОВ ТЕСТИРОВАНИЯ"
@echo ============================================================================
@echo.
@echo [1/6] Линтинг (Ruff)...
@$(VENV_PYTHON) -m ruff check src/ --output-format=concise --exit-zero 2>&1 | head -20
@echo.
@echo [2/6] Проверка типов (MyPy)...
@$(VENV_PYTHON) -m mypy src/ --config-file=config/mypy-fast.ini 2>&1 | head -20 || true
@echo.
@echo [3/6] Property-based тесты (Hypothesis)...
@$(VENV_PYTHON) -m pytest tests/property_based/ -q --timeout=30 --no-cov 2>&1 | tail -10
@echo.
@echo [4/6] Поиск мёртвого кода (Vulture)...
@$(VENV_PYTHON) -m vulture src/ --min-confidence 95 2>&1 | head -10 || true
@echo.
@echo [5/6] Проверка docstrings (Interrogate)...
@$(VENV_PYTHON) -m interrogate src/ --quiet --fail-under=0 2>&1 | tail -5 || true
@echo.
@echo [6/6] Проверка безопасности (Bandit)...
@$(VENV_PYTHON) -m bandit -r src/ -c pyproject.toml -q 2>&1 | tail -10 || true
@echo.
@echo ============================================================================
@echo "   ✅ ВСЕ ИНСТРУМЕНТЫ ЗАВЕРШЕНЫ"
@echo ============================================================================
