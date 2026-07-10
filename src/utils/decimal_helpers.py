from decimal import ROUND_HALF_UP, Decimal

D = Decimal

def quantize(value: D, places: int = 2) -> D:
    c = D('1') if places == 0 else D(f'1e-{places}')
    return value.quantize(c, rounding=ROUND_HALF_UP)
