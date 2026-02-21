# README для MkDocs документации

## Быстрый старт

### Установка

```bash
cd docs-site
pip install -r requirements.txt
```

### Локальный предпросмотр

```bash
mkdocs serve
```

ОткSwarmте http://127.0.0.1:8000 в браузере

### Сборка

```bash
mkdocs build
```

Результат в `site/`

### Деплой на GitHub Pages

```bash
mkdocs gh-deploy
```

## Структура

```
docs-site/
├── mkdocs.yml          # Конфигурация MkDocs
├── requirements.txt    # Зависимости Python
├── docs/
│   ├── index.md       # Главная страница
│   ├── guides/        # Руководства пользователя
│   ├── telegram-ui/   # Документация Telegram UI
│   ├── api/           # API Reference
│   └── development/   # Документация для разработчиков
└── site/              # Собранный сайт (генерируется)
```

## Редактирование

Все документы в формате Markdown в папке `docs/`.

После изменений запустите `mkdocs serve` для предпросмотра.
