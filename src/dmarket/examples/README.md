# Algo Arbitrage Predictor - Examples

Рабочие примеры использования Algo-Powered Arbitrage Prediction skill.

## 📁 Структура

```
examples/
├── README.md           # Этот файл
├── basic/              # Базовые примеры
│   ├── simple_scan.py
│   └── multi_game.py
├── advanced/           # Продвинутые примеры
│   ├── portfolio.py
│   ├── auto_trade.py
│   └── risk_management.py
└── benchmarks/         # Performance тесты
    ├── performance_test.py
    └── results.md
```

## 🚀 Быстрый старт

### 1. Базовый пример - Простое сканирование

```bash
cd examples/basic
python simple_scan.py
```

**Что делает**: Получает топ-10 арбитражных возможностей для CS:GO

### 2. Мультиигровой анализ

```bash
python multi_game.py
```

**Что делает**: Сканирует все 4 игры (CS:GO, Dota 2, TF2, Rust) и находит лучшую возможность

### 3. Управление портфелем (Advanced)

```bash
cd ../advanced
python portfolio.py
```

**Что делает**: Диверсифицированный портфель с распределением по играм и уровням риска

### 4. Performance тест

```bash
cd ../benchmarks
python performance_test.py
```

**Что делает**: Бенчмарк на 1000 items, измеряет latency

## ⚙️ НастSwarmка

Все примеры требуют `.env` файл с API ключами:

```bash
# .env
DMARKET_PUBLIC_KEY=your_public_key
DMARKET_SECRET_KEY=your_secret_key
```

## 📊 Ожидаемые результаты

- **simple_scan.py**: Топ-10 возможностей за ~2 секунды
- **multi_game.py**: Лучшая возможность из 4 игр за ~5 секунд
- **portfolio.py**: Диверсифицированный портфель за ~10 секунд
- **performance_test.py**: 1000 items обрабатываются за <500ms

## 🐛 Troubleshooting

**Проблема**: "DMARKET_PUBLIC_KEY not found"  
**Решение**: Создайте `.env` файл с API ключами

**Проблема**: "Module not found"  
**Решение**: Установите зависимости: `pip install -r requirements.txt`

**Проблема**: "API rate limit exceeded"  
**Решение**: Используйте меньший batch size или увеличьте задержку

## 📚 Дополнительные ресурсы

- [API Documentation](../../docs/api_reference.md)
- [ML Model DetAlgols](../../docs/ML_Algo_GUIDE.md)
- [Testing Guide](../../docs/testing_guide.md)
