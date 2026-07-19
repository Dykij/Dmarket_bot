# Как создать Pull Request на GitHub — Пошаговое руководство

## Способ 1: Через веб-интерфейс GitHub (самый простой)

### Шаг 1: Зайти на GitHub
1. Открой браузер
2. Зайди на **github.com**
3. Войди в свой аккаунт

### Шаг 2: Найти свой репозиторий
1. Нажми на свой аватар (справа вверху)
2. Выбери **"Your repositories"**
3. Найди **Dmarket_bot-main**
4. Нажми на него

### Шаг 3: Создать новую ветку
1. Нажми на выпадающий список веток (сверху слева, показывает "main")
2. Введи имя новой ветки, например: `code-review-improvements`
3. Нажми **"Create branch"**

### Шаг 4: Внести изменения
1. Найди файл, который хочешь изменить
2. Нажми на него
3. Нажми на иконку карандаша ✏️ (справа вверху)
4. Внеси изменения
5. Прокрути вниз
6. Введи коммит сообщение, например: "Add Code Review improvements"
7. Нажми **"Commit changes"**

### Шаг 5: Создать Pull Request
1. Нажми на вкладку **"Pull requests"** (сверху)
2. Нажми **"New pull request"**
3. Выбери:
   - **base:** `main` (основная ветка)
   - **compare:** `code-review-improvements` (твоя ветка)
4. Нажми **"Create pull request"**
5. Введи заголовок, например: "feat: Add Code Review system with MiMo V2.5 Pro"
6. Введи описание:
   ```
   ## Что добавлено
   - 12 агентов для Code Review
   - Дедупликация находок
   - Verification агент
   - Feedback loop система
   
   ## Как протестировать
   - Создать PR из этой ветки в main
   - Дождаться завершения workflow
   - Проверить PR comment с результатами
   ```
7. Нажми **"Create pull request"**

### Шаг 6: Проверить результат
1. После создания PR, GitHub Actions автоматически запустит Code Review
2. Подожди 2-5 минут
3. Обнови страницу PR
4. Найди PR comment с результатами Code Review

---

## Способ 2: Через терминал (Git CLI)

### Шаг 1: Установить Git (если не установлен)
```bash
# Linux
sudo apt-get install git

# macOS
brew install git

# Windows
# Скачай с https://git-scm.com/
```

### Шаг 2: Клонировать репозиторий
```bash
git clone https://github.com/ТВОЙ_АККАУНТ/Dmarket_bot-main.git
cd Dmarket_bot-main
```

### Шаг 3: Создать новую ветку
```bash
git checkout -b code-review-improvements
```

### Шаг 4: Внести изменения
```bash
# Отредактируй файлы
nano .opencode/agents/run_agent.py

# Добавить изменения
git add .

# Создать коммит
git commit -m "feat: Add Code Review system with MiMo V2.5 Pro"
```

### Шаг 5: Отправить изменения
```bash
git push origin code-review-improvements
```

### Шаг 6: Создать Pull Request
1. Зайди на GitHub
2. Нажми **"Compare & pull request"** (появится автоматически)
3. Введи заголовок и описание
4. Нажми **"Create pull request"**

---

## Способ 3: Через GitHub CLI (gh)

### Шаг 1: Установить GitHub CLI
```bash
# Linux
sudo apt-get install gh

# macOS
brew install gh

# Windows
winget install GitHub.cli
```

### Шаг 2: Авторизоваться
```bash
gh auth login
```

### Шаг 3: Создать PR
```bash
# Из директории проекта
cd Dmarket_bot-main

# Создать ветку
git checkout -b code-review-improvements

# Внести изменения и закоммитить
git add .
git commit -m "feat: Add Code Review system"

# Отправить
git push origin code-review-improvements

# Создать PR
gh pr create --title "feat: Add Code Review system" --body "Описание PR"
```

---

## Как проверить, что Code Review запустился

### Шаг 1: Зайти в Actions
1. Зайди на GitHub в свой репозиторий
2. Нажми вкладку **"Actions"** (сверху)
3. Ты увидишь список workflow runs

### Шаг 2: Проверить статус
1. Найди последний workflow run
2. Нажми на него
3. Ты увидишь:
   - 🟢 Зелёный — успешно
   - 🟡 Жёлтый — в процессе
   - 🔴 Красный — ошибка

### Шаг 3: Посмотреть результат
1. Если успешно — зайди в Pull Request
2. Прокрути вниз до комментариев
3. Найди комментарий от **github-actions[bot]**
4. Это и есть результат Code Review

---

## Частые проблемы и решения

### Проблема 1: Workflow не запускается
**Причина:** Неправильный триггер в workflow файле
**Решение:** Проверь, что в `.github/workflows/code-review.yml` есть:
```yaml
on:
  pull_request:
    types: [opened, synchronize]
```

### Проблема 2: Ошибка "MIMO_API_KEY not set"
**Причина:** Секрет не добавлен в GitHub
**Решение:** 
1. Зайди в Settings → Secrets and variables → Actions
2. Проверь, что `MIMO_API_KEY` и `MIMO_BASE_URL` добавлены

### Проблема 3: Ошибка "self-hosted runner not found"
**Причина:** Runner не запущен на твоём сервере
**Решение:**
1. Зайди на свой сервер
2. Запусти runner: `./run.sh`
3. Проверь, что runner показывает "Listening for Jobs"

### Проблема 4: Ошибка "openai not installed"
**Причина:** Библиотека openai не установлена на runner
**Решение:** Добавь в workflow:
```yaml
- name: Setup Python
  run: |
    pip3 install openai
```

---

## Как добавить Code Review в существующий PR

Если ты уже создал PR и хочешь добавить Code Review:

### Способ 1: Перезапустить workflow
1. Зайди в Actions
2. Найди последний workflow run
3. Нажми **"Re-run all jobs"**

### Способ 2: Добавить новый коммит
1. Внеси любое изменение в PR
2. Закоммитируй
3. Workflow запустится автоматически

---

## Как отключить Code Review для определённых PR

Если ты не хочешь запускать Code Review для某些 PR:

### Способ 1: Добавить метку
1. Создай метку `skip-review`
2. Добавь её в PR
3. Измени workflow:
```yaml
on:
  pull_request:
    types: [opened, synchronize]
    labels:
      - '!skip-review'
```

### Способ 2: Изменить триггер
```yaml
on:
  pull_request:
    types: [opened, synchronize]
    paths:
      - 'src/**'  # Только для изменений в src/
```

---

## Полезные ссылки

- [GitHub Docs: Creating a pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request)
- [GitHub Docs: GitHub Actions](https://docs.github.com/en/actions)
- [GitHub CLI Manual](https://cli.github.com/manual/)
