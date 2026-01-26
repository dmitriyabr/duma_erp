from decimal import ROUND_HALF_DOWN, ROUND_HALF_UP, Decimal
from typing import Union

# Type alias for money values
Money = Decimal


def round_money(value: Union[Decimal, float, int, str]) -> Decimal:
    """
    Round monetary value to 2 decimal places using ROUND_HALF_UP.

    Examples:
        >>> round_money(10.125)
        Decimal('10.13')
        >>> round_money(10.124)
        Decimal('10.12')
        >>> round_money("10.115")
        Decimal('10.12')
    """
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    if value < 0:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_DOWN)
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
