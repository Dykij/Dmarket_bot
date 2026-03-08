"""Configuration data for the Telegram bot."""

ARBITRAGE_MODES = {
    "boost_low": {
        "name": "разгон баланса (низкая прибыль, быстрый оборот)",
        "min_price": 1.0,
        "max_price": 50.0,
        "min_profit_percent": 5.0,
        "min_profit_amount": 0.5,
        "trade_strategy": "fast_turnover",
    },
    "mid_medium": {
        "name": "средний трейдер (средняя прибыль, сбалансированный риск)",
        "min_price": 10.0,
        "max_price": 200.0,
        "min_profit_percent": 10.0,
        "min_profit_amount": 2.0,
        "trade_strategy": "balanced",
    },
    "pro_high": {
        "name": "Trade Pro (высокая прибыль, высокий риск)",
        "min_price": 50.0,
        "max_price": 1000.0,
        "min_profit_percent": 15.0,
        "min_profit_amount": 5.0,
        "trade_strategy": "high_profit",
    },
}
