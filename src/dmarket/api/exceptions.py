class DMarketAPIError(Exception):
    pass

class InsufficientFundsError(DMarketAPIError):
    def __init__(self, required: float, available: float):
        self.required = required
        self.available = available
        super().__init__(f'Insufficient funds: required , available ')
