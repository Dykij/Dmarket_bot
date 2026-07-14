# Типы анализа кодовой базы — DMarket Bot

## 1. Статический анализ кода (Lint Analysis)

### Что делает
Проверяет исходный код без выполнения. Находит синтаксические ошибки, неиспользуемые импорты, нарушения стиля, потенциальные баги.

### Инструменты
- **Ruff** — быстрый линтер (E/F/UP/B/SIM/I правила)
- **Pyright/ty** — type checker для Python
- **mypy** — дополнительная проверка типов

### Что проверяет
| Код правила | Описание | Критичность |
|-------------|----------|-------------|
| F401 | Неиспользуемые импорты | WARNING |
| F811 | Переопределённые импорты | ERROR |
| E501 | Строка >100 символов | INFO |
| E402 | Неправильный порядок импортов | WARNING |
| B006 | Mutable default arguments | ERROR |
| SIM108 | Тернарный оператор вместо if/else | INFO |
| UP007 | Union syntax (X \| Y вместо Union[X, Y]) | INFO |

### Методология исправления
1. Запустить `ruff check src/ --select=F,E,UP,B,SIM`
2. Исправить ERROR первыми (F-коды)
3. Затем WARNING (E-коды)
4. INFO — опционально

---

## 2. Анализ безопасности (Security Analysis)

### Что делает
Ищет уязвимости: инъекции, утечки секретов, небезопасные API, path traversal.

### Инструменты
- **Semgrep** — SAST сканер с авто-правилами
- **detect-secrets** — поиск захардкоженных ключей

### Что проверяет
| Тип уязвимости | Пример | Критичность |
|----------------|--------|-------------|
| SQL injection | f"SELECT * FROM t WHERE id={x}" | CRITICAL |
| Hardcoded secrets | `API_KEY = "sk-123..."` | CRITICAL |
| Path traversal | `open(user_input)` | HIGH |
| Unsafe deserialization | `pickle.loads(data)` | HIGH |
| Command injection | `os.system(cmd)` | CRITICAL |
| XSS | `innerHTML = user_data` | MEDIUM |

### Методология
1. `semgrep scan --config auto src/`
2. Исправить CRITICAL немедленно
3. HIGH — в течение дня
4. MEDIUM — в плановом порядке

---

## 3. Анализ архитектуры (Architecture Analysis)

### Что делает
Оценивает структуру проекта: модульность, циклические зависимости, сложность, глубину вызовов.

### Инструменты
- **Archy** — архитектурный анализатор (modularity, acyclicity, depth, equality, complexity)

### Метрики
| Метрика | Описание | Порог |
|---------|----------|-------|
| Modularity | Насколько модули изолированы | >0.7 = healthy |
| Acyclicity | Отсутствие циклических зависимостей | 1.0 = ideal |
| Depth | Максимальная глубина импортов | <5 = ok |
| Equality | Равномерность распределения рёбер | >0.3 = ok |
| Complexity | Средняя цикломатическая сложность | <10 = ok |

### Методология
1. `archy score src/` — общая оценка
2. `archy cycles src/` — циклические зависимости
3. `archy what_to_refactor_next` — приоритеты рефакторинга

---

## 4. Анализ типов (Type Safety Analysis)

### Что делает
Проверяет корректность типов: mismatch, отсутствие аннотаций, небезопасный None.

### Инструменты
- **ty check src/** — быстрый type checker
- **pyright** — альтернативный type checker

### Что проверяет
| Проблема | Пример | Критичность |
|----------|--------|-------------|
| Missing annotations | `def foo(x):` | WARNING |
| Type mismatch | `x: int = "str"` | ERROR |
| None safety | `x: str \| None; x.lower()` | ERROR |
| Protocol compliance | Несоответствие интерфейсу | ERROR |

---

## 5. Анализ сложности (Complexity Analysis)

### Что делает
Находит слишком сложные функции, которые нужно разбить.

### Метрики
| Метрика | Описание | Порог |
|---------|----------|-------|
| Cyclomatic complexity | Количество ветвлений | >10 = high |
| Cognitive complexity | Читаемая сложность | >15 = high |
| Function length | Количество строк | >50 = long |
| Nesting depth | Глубина вложенности | >4 = deep |

### Методология
1. `archy what_to_refactor_next` — hotspots
2. Разбить функции >50 строк
3. Извлечь вложенные if/for в отдельные функции

---

## 6. Анализ asyncio (Async Safety Analysis)

### Что делает
Находит ошибки в асинхронном коде: блокирующие вызовы, отсутствие await, race conditions.

### Что проверяет
| Проблема | Пример | Критичность |
|----------|--------|-------------|
| Blocking in async | `time.sleep(1)` вместо `await asyncio.sleep(1)` | CRITICAL |
| Missing await | `result = async_func()` без await | CRITICAL |
| Race condition | Общий mutable state без Lock | HIGH |
| Task leak | `asyncio.create_task()` без сохранения ссылки | MEDIUM |
| Sync in executor | `await loop.run_in_executor(None, blocking_io)` | OK |

---

## 7. Анализ базы данных (Database Analysis)

### Что делает
Проверяет SQL запросы, индексы, блокировки, миграции.

### Что проверяет
| Проблема | Пример | Критичность |
|----------|--------|-------------|
| SQL injection | f-string в SQL | CRITICAL |
| Missing index | SELECT без индекса по WHERE | HIGH |
| N+1 query | Цикл с SELECT внутри | HIGH |
| Missing WAL | journal_mode=DELETE | MEDIUM |
| Lock contention | Concurrent writes без retry | HIGH |
| Missing migration | ALTER TABLE без версионирования | MEDIUM |

---

## 8. Анализ торговой логики (Trading Logic Analysis)

### Что делает
Проверяет корректность расчётов прибыли, баланса, Kelly criterion, drawdown.

### Что проверяет
| Проверка | Описание | Критичность |
|----------|----------|-------------|
| Balance validation | Баланс >= суммы сделки | CRITICAL |
| Fee calculation | Комиссия правильно вычитается | CRITICAL |
| Drawdown freeze | Торговля останавливается при >15% просадке | CRITICAL |
| Kelly sizing | Позиция = half Kelly (50%) | HIGH |
| Profit margin | net_margin > min_spread | HIGH |
| Idempotency | Уникальный order_id для каждой сделки | HIGH |

---

## 9. Анализ зависимостей (Dependency Analysis)

### Что делает
Проверяет известные уязвимости в пакетах, устаревшие версии.

### Инструменты
- `pip audit` — CVE сканер
- `safety check` — альтернативный сканер

---

## 10. Анализ Docker (Containerization Analysis)

### Что делает
Проверяет Dockerfile, health checks, volume mounts, multi-stage build.

### Что проверяет
| Проверка | Описание |
|----------|----------|
| Multi-stage build | Отдельный build и runtime этапы |
| Health check | HEALTHCHECK инструкция |
| Non-root user | Не root пользователь |
| Secrets handling | Не COPY .env в образ |
| ARM64 compat | Мульти-архитектурная сборка |
