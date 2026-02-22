import json
import os


class Backtester:
    def __init__(self, data_path):
        self.data_path = data_path
        self.balance = 1000.0  # Initial capital
        self.initial_balance = 1000.0
        self.holdings = 0.0
        self.history = []
        self.trades = []
        self.buy_price = 0.0

    def load_data(self):
        with open(self.data_path, 'r') as f:
            self.history = json.load(f)

    def run(self):
        prices = [entry['price'] for entry in self.history]

        for i, entry in enumerate(self.history):
            current_price = entry['price']

            # Need at least a few data points for average
            if i < 1:
                continue

            # Calculate average of all known prices up to this point
            known_prices = prices[:i+1]
            avg_price = sum(known_prices) / len(known_prices)

            # Logic: Buy if price < avg * 0.8
            if self.balance > 0 and current_price < (avg_price * 0.8):
                # Buy as much as possible
                amount = self.balance / current_price
                self.holdings = amount
                self.balance = 0
                self.buy_price = current_price
                self.trades.append(f"BUY at {current_price}")

            # Logic: Sell if price > buy_price * 1.1
            elif self.holdings > 0 and current_price > (self.buy_price * 1.1):
                # Sell all
                self.balance = self.holdings * current_price
                self.holdings = 0
                self.trades.append(f"SELL at {current_price}")

    def calculate_roi(self):
        # Final valuation: balance + value of current holdings
        current_val = self.balance
        if self.holdings > 0:
            # Use last known price for valuation
            last_price = self.history[-1]['price']
            current_val += self.holdings * last_price

        roi = ((current_val - self.initial_balance) / self.initial_balance) * 100
        return roi


if __name__ == "__main__":
    import argparse

    # Allow running from root or src/trading
    data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'tests/data/price_history.json')

    backtester = Backtester(data_path)
    backtester.load_data()
    backtester.run()
    roi = backtester.calculate_roi()

    print(f"Trades: {backtester.trades}")
    print(f"ROI: {roi:.2f}%")
