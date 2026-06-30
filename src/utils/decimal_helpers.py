from decimal import Decimal, ROUND_HALF_UP

D = Decimal

def quantize(value: D, places: int = 2) -> D:
    c = D('1') if places == 0 else D(f'1e-{places}')
    return value.quantize(c, rounding=ROUND_HALF_UP)
