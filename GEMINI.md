@AGENTS.md

# Engineering Rigor Protocol
- **RAW-дисциплина:** Ни один вывод отчёта не может содержать утверждение о результате команды без вставленного RAW-вывода этой команды в том же сообщении.
- **Разделение pre-existing/introduced:** При падении тестов всегда явно проверять и указывать, было ли это падение до изменений, или оно внесено текущими правками.
- **Статистическая честность:** При отчётах с числами/метриками указывать размер выборки (sample size), погрешность и проверять однородность.
- **Деструктивные команды:** Все деструктивные команды (rm, git push --force и т.д.) требуют явного подтверждения пользователя.
- **Scope discipline:** Не изменять файлы и участки кода, не относящиеся к текущей задаче. Строго следить за изменениями.
  - **Тесты — уточнение:** Обновление СУЩЕСТВУЮЩИХ тестов, проверяющих старое (исправленное) поведение — обязательная часть фикса, отдельное разрешение не требуется. Добавление НОВЫХ тестов на код, который раньше не был покрыт — отдельная работа, требует явного разрешения как расширение скоупа.
- **Subsystem AGENTS.md:** При завершении работы над подсистемой в `src/api/` или `src/core/target_sniping/` — обновить соответствующий вложенный `AGENTS.md` новыми находками ПЕРЕД финальным отчётом (обязательный пункт чек-листа, аналогично scope-auditor).

# Subagent Delegation
Триггеры для делегирования задач субагентам:
- Перед `git commit` в `src/core/target_sniping/` или `src/api/` → делегировать в `code-auditor`
- При падении теста после правки → делегировать в `regression-isolator`
- Перед финальным отчётом с числовыми результатами (калибровка, метрики) → делегировать в `stats-skeptic`
- Перед отправкой итогового отчёта пользователю → делегировать в `raw-evidence-auditor`
- При завершении любой multi-file задачи → делегировать в `scope-auditor`
- Вердикт делегированного субагента должен быть либо устранён конкретным исправлением с повторной проверкой, либо явно процитирован как неразрешённое замечание в финальном отчёте — никогда не игнорироваться при выставлении итогового статуса

# Section 2a. Investigation Completeness (Pipeline Context Before Severity)

A finding based on an isolated snippet is provisional, not final. Before
assigning severity (Critical/High/Medium/Low) to any bug:

- Trace the code path both upstream (who calls this function, what
  happens before this line executes) and downstream (what consumes
  this function's output) — not just the isolated block you first
  spotted. A control-flow claim ("X happens after Y", "check is
  missing", "value is never used") requires having actually looked at
  the surrounding pipeline, not just the function where you noticed it.
- Before writing "missing" or "never called" — grep for the function/
  check across the whole relevant subsystem (not just the file open in
  front of you). A check can legitimately live in a different file
  earlier in the pipeline.
- When quoting code as evidence, quote enough surrounding lines to show
  the full conditional/control-flow block (the whole if/else, the whole
  function signature to return), not an arbitrary line range picked to
  fit a message. A reader should be able to verify your claim from the
  quote alone, without re-running the command.
- If a first-pass finding turns out to be incomplete once the pipeline
  is traced (as happened with the execution.py risk-manager finding in
  this session — first read as "risk check skipped in PROD", full trace
  showed it runs twice in PROD as a binary gate, and the actually-buggy
  code was DRY_RUN-only dead code) — report the corrected version
  explicitly, don't quietly patch the earlier claim without flagging
  that the severity/nature of the finding changed.

# Section 6. Mandatory reporting structure
## 🛠️ Actions & Changes
When citing code as evidence for a finding, include the full relevant
block (complete function or complete conditional branch), not a
minimal snippet — enough that severity and control-flow claims can be
verified from the quote alone.
