from decimal import Decimal


def to_float(value: Decimal | int | float | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def calculate_cost(hours: Decimal | int | float | None, bill_rate: Decimal | int | float | None) -> float:
    return round(to_float(hours) * to_float(bill_rate), 2)


def round_hours(value: Decimal | int | float | None) -> float:
    return round(to_float(value), 2)
