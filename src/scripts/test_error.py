def calculate_profit(buy_price, sell_price, fee_percentage):
    # Intentional ZeroDivisionError logic for testing
    # If fee is 0, we divide by it (simulating a bug in fee calculation logic)
    profit = (sell_price - buy_price) / fee_percentage
    return profit

if __name__ == "__main__":
    calculate_profit(10, 20, 0)
