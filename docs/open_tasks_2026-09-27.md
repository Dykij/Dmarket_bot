# Отчёт по открытым задачам и состоянию проекта (2026-09-27)

*Все данные собраны через независимую RAW-проверку в текущей сессии. Ни один пункт не опирается на старые заметки без фактического подтверждения.*

## 🔴 Категория 1: Блокирует продакшен

### 1. Бэктест `TRACKED_TITLES`
**Статус**: НЕ НАЧАТ (код не готов к проду).
**RAW-подтверждение**:
```text
docs/SESSION_LOG.md:26:- [WARNING] Code is NOT ready for production. TRACKED_TITLES requires backtesting.
docs/SESSION_LOG.md:30:- Updated `Config.TRACKED_TITLES` to use a curated list of 40 liquid CS2 items instead of blind top-100 scan.
src/config.py:78:    TRACKED_TITLES: list[str] = [
```
**Следующий шаг**: Выполнить прогон бэктеста для обновлённого списка 40 ликвидных предметов.

### 2. Миграция bid/ask в `price_history` (ALTER TABLE + dual-write)
**Статус**: НЕ НАЧАТА.
**RAW-подтверждение**:
Поиск `ALTER TABLE` в `src/db/` не показал миграций для bid/ask (найдены только добавления для `virtual_inventory`).
```text
src/db/price_history/core.py:            # to prevent SQL injection via ALTER TABLE ADD COLUMN.
src/db/price_history/core.py:                    sql = f"ALTER TABLE virtual_inventory ADD COLUMN [{col}] {typedef}"
src/db/price_history/core.py:                    "ALTER TABLE virtual_inventory ADD COLUMN exclusive INTEGER NOT NULL DEFAULT 0"
src/db/price_history/core.py:        """Execute a pre-validated ALTER TABLE ADD COLUMN statement.
```
**Следующий шаг**: Написать и применить миграцию схемы БД для bid/ask.

---

## 🟡 Категория 2: Требует решения Богдана прямо сейчас

### 3. Незакоммиченное состояние рабочего дерева
**Статус**: Дерево грязное (23 файла изменено, множество untracked файлов скиллов и скриптов).
**RAW-подтверждение**:
```text
## testing/backtest-validation...origin/testing/backtest-validation
 M .agents/agents/code-auditor/agent.md
... (много изменений в .agents/skills/ и src/api/dmarket_api_client/)
?? .agents/skills/calculate_target_metrics/
... (множество untracked скиллов)
 23 files changed, 41 insertions(+), 27 deletions(-)
```
**Следующий шаг**: Ожидается явный `Proceed` от пользователя для создания коммита или очистки дерева.

### 4. Статус `_disabled_*` скиллов
**Статус**: В `.agents/skills/` отключённых папок больше нет, но два плагина физически остались в `~/.gemini/config/plugins/`.
**RAW-подтверждение**:
```text
$ ls -la .agents/skills/ | grep _disabled
(exit code 1 - не найдено)

$ ls ~/.gemini/config/plugins/ | grep _disabled
_disabled_gemini-api
_disabled_google-antigravity-sdk
```
**Следующий шаг**: Подтвердить, является ли это целевым (финальным) состоянием, и нужно ли удалить плагины.

### 5. Архитектурный пробел H27 (Обход Permission Engine)
**Статус**: Уязвимость зафиксирована в реестре, решение не принято.
**RAW-подтверждение**:
```text
docs/remaining_tasks_report_2026-09-26.md:## Пункт 3: Периметр обхода H27 и варианты закрытия
docs/remaining_tasks_report_2026-09-26.md:### Варианты закрытия H27
```
**Следующий шаг**: Богдану необходимо выбрать один из предложенных вариантов (А/Б/В).

---

## 🟢 Категория 3: Технический долг без срочности

### 6. Отсутствие `msgspec`
**Статус**: Библиотека `msgspec` всё ещё отсутствует в `requirements.txt`.
**RAW-подтверждение**:
```text
$ grep -n msgspec requirements.txt
(exit code 1 - не найдено)
```
**Следующий шаг**: Добавить `msgspec` в зависимости проекта.

### 7. Фикс `os.environ` в `config_watcher`
**Статус**: ИСПРАВЛЕНО (фикс присутствует в коде и покрыт тестами на рантайм-обновление).
**RAW-подтверждение**:
Файл `src/utils/config_watcher.py`, метод `_apply`:
```python
                    temp = Config.model_validate({key: float(value)})
                    setattr(Config, key, getattr(temp, key))
                    applied = True
                except Exception:
                    logger.warning(f"[ConfigWatcher] Validation failed for {key}={value}")
            elif hasattr(Config, key) and isinstance(getattr(Config, key), str):
                setattr(Config, key, value)
                applied = True
            
            if applied:
                os.environ[key] = value
        except (ValueError, TypeError) as e:
            logger.warning(f"[ConfigWatcher] Failed to apply {key}={value}: {e}")
```
**Ответ на вопрос**: Да, это именно тот код, который отвечает за обновление переменных окружения на лету при изменении `.env`. Тесты, реально проверяющие рантайм-обновление `os.environ`, существуют: в `tests/unit/test_config_watcher.py` есть `TestReloadSyncsOsEnvironForReloadableKey`, который явно делает `assert os.environ.get("MIN_SPREAD_PCT") == "12.0"` после вызова `_reload()`, подтверждая, что значение не просто читается при старте, а синхронизируется.
**Следующий шаг**: Закрыть задачу (не требует действий).

### 8. Ошибки тестов `test_http_health_endpoints`
**Статус**: НЕ ПРОВЕРЕНО ИЗ-ЗА ОШИБКИ ИМПОРТА `msgspec`.
**RAW-подтверждение**:
Запуск через `.venv/bin/pytest` падает на этапе сбора тестов:
```text
$ .venv/bin/pytest tests/ -k test_http_health_endpoints -v 2>&1 | tail -n 25
...
ImportError while importing test module '/home/deck/dmarket/Dmarket_bot-main/tests/unit/test_market_models.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/usr/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/unit/test_market_models.py:5: in <module>
    import msgspec
E   ModuleNotFoundError: No module named 'msgspec'
=========================== short test summary info ============================
ERROR tests/unit/test_market_models.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```
**Следующий шаг**: Сначала закрыть пункт 6 (отсутствие `msgspec`), затем повторить запуск.

### 8.1. Сложность `_init_schemas` (`radon`)
**Статус**: НЕ ПРОВЕРЕНО (radon физически не установлен в `.venv`).
**RAW-подтверждение**:
```text
$ .venv/bin/radon cc src/db/price_history/core.py -s | grep _init_schemas
Traceback (most recent call last):
  File "/home/deck/dmarket/Dmarket_bot-main/.venv/bin/radon", line 4, in <module>
    from radon import main
ModuleNotFoundError: No module named 'radon'
```
*(То же самое для полного вывода файла без фильтра — падает с ModuleNotFoundError)*
**Следующий шаг**: Установить `radon` в виртуальное окружение и запустить повторно, либо закрыть задачу, если декомпозиция схемы БД больше не приоритетна.

### 9. Мёртвый код `get_transaction_history`
**Статус**: УДАЛЁН.
**RAW-подтверждение**:
```text
$ grep -n "get_transaction_history" src/api/dmarket_api_client/account.py
(exit code 1 - не найдено)
```
**Следующий шаг**: Закрыть задачу (не требует действий).

### 10. Декомпозиция `sell_inventory_items`
**Статус**: ПОДТВЕРЖДЕНО. Декомпозиция выполнена в коммите `e89d3ae`, расхождение с worktree устранено.
**RAW-подтверждение**:
```text
$ git show e89d3ae --stat
commit e89d3ae4b5e8a3cf0c3b422f675eec2cb2f1f086
Author: DMarket Bot <bot@dmarket.local>
Date:   Sat Sep 19 17:00:42 2026 +0300

    refactor(resale_pipeline): decompose sell_inventory_items into helper methods

 docs/SESSION_LOG.md         |   1 +
 src/core/resale_pipeline.py | 185 ++++++++++++++++++++++++++------------------
 2 files changed, 112 insertions(+), 74 deletions(-)
```
Часть самого диффа `src/core/resale_pipeline.py`:
```python
-    # =================================================================
-    # =================================================================
-    # 2. SELL — List purchased items on DMarket
-    # =================================================================
-
     async def sell_inventory_items(self, max_items: int = 10) -> list[dict[str, Any]]:
         """
         List trade-unlocked items for sale on DMarket.
@@ -56,20 +54,37 @@ class ResalePipeline:
           1. Oracle /prices/batch for all unique titles in 1 call
           2. DMarket batch_create_offers_v2 for all items in 1 call
         """
-        items = await price_db.run_in_thread(price_db.get_virtual_inventory, status='idle', only_unlocked=True)
+        items = await price_db.run_in_thread(
+            price_db.get_virtual_inventory, status="idle", only_unlocked=True
+        )
         if not items:
```
Дифф подтверждает реальное разбиение гигантского монолита в коде (112 вставок против 74 удалений за счет выделения вспомогательных функций).
**Следующий шаг**: Закрыть задачу (не требует действий).

### 11. Поле `usdAvailableToWithdraw`
**Статус**: NOT_VERIFIED. Логируется в памяти, но ручная сверка на живом балансе (не DRY_RUN) ещё не производилась.
**RAW-подтверждение**:
```text
docs/MEMORY.md:- **Manual Verification Plan (2026-09-23)**: Upon the next non-DRY_RUN execution of `get_real_balance()` in production, manually cross-reference...
```
**Следующий шаг**: Провести ручную сверку при первом non-DRY_RUN запуске.

### 12. Hook runner не выводит логи
**Статус**: ПОДТВЕРЖДЕНО. При выполнении команд через хук логи в консоль/RAW-вывод всё ещё не пробрасываются.
**RAW-подтверждение**:
```text
$ echo "test hook runner output"
test hook runner output
(никакого дополнительного вывода от хука)
```
**Следующий шаг**: Исследовать конфигурацию `ag_` хуков на уровне ОС/Агента.

### 13. Субагент `stop-criteria-guard`
**Статус**: НЕ РАБОТАЕТ.
**RAW-подтверждение**:
```text
Encountered error in tool execution: subagent "stop-criteria-guard" not found or not allowed to be invoked
```
**Следующий шаг**: Исправить регистрацию субагента (возможно, он в `_disabled` или удалён).

### 14. Track A (аудит контента скиллов)
**Статус**: НИЧЕЙ. Ни один агент не взял на себя эту задачу.
**RAW-подтверждение**:
```text
docs/skills_audit_report_2026-09-26.md:- Субагент `lsp-mcp-integration-auditor` отказался от проверки скиллов... Ни один текущий субагент не покрывает аудит контента скиллов (Track A).
```
**Следующий шаг**: Богдану необходимо решить: создать нового субагента, расширить текущего или принять риск.
