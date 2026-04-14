---
name: "Algo-Powered Automated Backtesting"
description: "Бэктестирование торговых стратегий с ML на исторических данных DMarket"
version: "1.0.0"
author: "DMarket Bot Team"
license: "MIT"
category: "Business"
subcategories: ["Research", "Data & Algo", "Finance", "Testing"]
tags: ["backtesting", "simulation", "trading-strategies", "ml", "analytics"]
status: "approved"
team: "@trading-team"
approver: "Dykij"
approval_date: "2026-01-25"
review_required: true
last_review: "2026-01-25"
python_version: ">=3.11"
main_module: "Algo_backtester.py"
dependencies:
  - "pandas>=2.0"
  - "numpy>=1.24"
  - "matplotlib>=3.7"
optional_dependencies:
  - "plotly"
performance:
  latency_ms: 100
  throughput_per_sec: 10
Algo_compatible: true
allowed_tools:
  - "github-copilot"
  - "claude-code"
  - "chatgpt"
---

# Skill: Algo-Powered Automated Backtesting

## Описание

Модуль автоматизированного бэктестирования торговых стратегий с использованием машинного обучения. Симулирует исторические сделки и оценивает эффективность стратегий на реальных данных DMarket.

## Категория

- **Primary**: Research, Data & Algo
- **Secondary**: Finance, Testing
- **Tags**: `backtesting`, `simulation`, `trading-strategies`, `ml`, `analytics`

## Возможности

- ✅ Симуляция торговых стратегий на исторических данных
- ✅ ML-прогнозирование для улучшения результатов
- ✅ Multi-game бэктестинг (CS:GO, CS2, Rust)
- ✅ Расчет ключевых метрик (ROI, Sharpe Ratio, Max Drawdown)
- ✅ Визуализация результатов (графики прибыли, риска)
- ✅ Сравнение стратегий
- ✅ Оптимизация параметров стратегии
- ✅ Monte Carlo симуляции

## Архитектура

```
┌─────────────────────────────────────────────────────┐
│              AlgoBacktester                           │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Historical Data                                    │
│        │                                            │
│        ▼                                            │
│  ┌─────────────────────┐                           │
│  │ Data Loader         │                           │
│  │ - Price history     │                           │
│  │ - Volume            │                           │
│  │ - Market events     │                           │
│  └─────────────────────┘                           │
│        │                                            │
│        ▼                                            │
│  ┌─────────────────────┐                           │
│  │ Strategy Executor   │                           │
│  │ - Buy/Sell signals  │                           │
│  │ - Position sizing   │                           │
│  └─────────────────────┘                           │
│        │                                            │
│        ▼                                            │
│  ┌─────────────────────┐                           │
│  │ ML Enhancer         │                           │
│  │ (Price Predictor)   │                           │
│  └─────────────────────┘                           │
│        │                                            │
│        ▼                                            │
│  ┌─────────────────────┐                           │
│  │ Performance         │                           │
│  │ Calculator          │                           │
│  └─────────────────────┘                           │
│        │                                            │
│        ▼                                            │
│  Results + Visualization                            │
└─────────────────────────────────────────────────────┘
```

## Требования

### Обязательные зависимости
- Python 3.11+
- pandas 2.0+
- numpy 1.24+
- scikit-learn 1.3+
- matplotlib 3.7+

### Опциональные зависимости
- seaborn 0.12+ (для продвинутых графиков)
- plotly 5.17+ (для интерактивных графиков)

## Установка

```bash
pip install -e src/analytics/
```

## Использование

### Базовое использование

```python
from src.analytics.Algo_backtester import AlgoBacktester
from datetime import datetime, timedelta

# Инициализация
backtester = AlgoBacktester()

# Период тестирования
end_date = datetime.now()
start_date = end_date - timedelta(days=30)

# Запуск бэктеста
results = await backtester.run_backtest(
    strategy="arbitrage_5_percent",
    game="csgo",
    start_date=start_date.isoformat(),
    end_date=end_date.isoformat(),
    initial_balance=100.0
)

# Вывод результатов
print(f"Total Profit: ${results['total_profit']:.2f}")
print(f"ROI: {results['roi_percent']:.1f}%")
print(f"Win Rate: {results['win_rate']:.1%}")
print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {results['max_drawdown']:.1%}")
print(f"Total Trades: {results['trades_count']}")
print(f"ML Accuracy: {results['ml_accuracy']:.1%}")
```

### Пример вывода

```
Total Profit: $245.50
ROI: 145.5%
Win Rate: 73.0%
Sharpe Ratio: 1.85
Max Drawdown: 15.3%
Total Trades: 342
ML Accuracy: 78.5%
```

## API Reference

### `class AlgoBacktester`

#### `async run_backtest(strategy, game, start_date, end_date, initial_balance=100.0)`

Запускает симуляцию торговой стратегии.

**Parameters:**
- `strategy` (str): Название стратегии
- `game` (str): Игра для тестирования
- `start_date` (str): Дата начала (ISO format)
- `end_date` (str): Дата окончания (ISO format)
- `initial_balance` (float): Начальный баланс

**Returns:**
```python
{
    "total_profit": float,      # Общая прибыль
    "roi_percent": float,       # ROI в процентах
    "win_rate": float,          # Процент прибыльных сделок
    "sharpe_ratio": float,      # Коэффициент Шарпа
    "max_drawdown": float,      # Максимальная просадка
    "trades_count": int,        # Количество сделок
    "ml_accuracy": float,       # Точность ML прогнозов
    "equity_curve": list,       # История баланса
    "trades": list              # Детали сделок
}
```

## Поддерживаемые стратегии

| Стратегия | Описание | Risk Level |
|-----------|----------|------------|
| `arbitrage_5_percent` | Арбитраж с минимум 5% маржой | Low |
| `arbitrage_10_percent` | Арбитраж с минимум 10% маржой | Medium |
| `ml_enhanced` | ML-оптимизированный арбитраж | Medium |
| `aggressive_scalping` | Частые сделки с малой маржой | High |

## Производительность

| Метрика | Значение |
|---------|----------|
| **Скорость симуляции** | ~1000 trades/second |
| **Точность ML** | 75-80% |
| **Период тестирования** | До 1 года данных |

## Примеры использования

### Пример 1: Сравнение стратегий

```python
strategies = ["arbitrage_5_percent", "arbitrage_10_percent", "ml_enhanced"]
results_comparison = {}

for strategy in strategies:
    results = await backtester.run_backtest(
        strategy=strategy,
        game="csgo",
        start_date="2025-12-01",
        end_date="2026-01-01",
        initial_balance=100.0
    )
    results_comparison[strategy] = results

# Найти лучшую стратегию
best_strategy = max(
    results_comparison.items(),
    key=lambda x: x[1]["sharpe_ratio"]
)
print(f"Best strategy: {best_strategy[0]}")
```

### Пример 2: Multi-game бэктестинг

```python
games = ["csgo", "dota2", "tf2", "rust"]
multi_game_results = {}

for game in games:
    results = await backtester.run_backtest(
        strategy="ml_enhanced",
        game=game,
        start_date="2025-12-01",
        end_date="2026-01-01",
        initial_balance=100.0
    )
    multi_game_results[game] = results

# Общая прибыль по всем играм
total_profit = sum(r["total_profit"] for r in multi_game_results.values())
print(f"Total profit across all games: ${total_profit:.2f}")
```

## Визуализация

```python
# Генерация графиков
await backtester.generate_charts(results, output_dir="./charts/")

# Создаются следующие графики:
# - equity_curve.png - кривая прибыли
# - drawdown.png - график просадок
# - trade_distribution.png - распределение прибылей/убытков
# - monthly_returns.png - месячная доходность
```

## Зависимости

### Внутренние модули
- `src/ml/enhanced_predictor.py` - ML модели
- `src/dmarket/dmarket_api.py` - DMarket API
- `src/analytics/performance_metrics.py` - Метрики

## Лицензия

MIT License

## Changelog

### v1.0.0 (2026-01-19)
- ✅ Первый релиз
- ✅ Multi-game бэктестинг
- ✅ ML-интеграция
- ✅ Визуализация результатов

---

**Last Updated**: 2026-01-19  
**Status**: ✅ Production Ready  
**Skill Type**: Research, Data & Algo


---
🦅 *DMarket Quantitative engine | v7.0 | 2026*

----- 
🦅 *DMarket Quantitative Engine | v7.0 | 2026*