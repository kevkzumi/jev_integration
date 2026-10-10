"""Simple statistics over sequences of numbers."""


def mean(values):
    """Arithmetic mean. Raises ValueError on an empty sequence."""
    values = list(values)
    if not values:
        raise ValueError("mean of empty sequence")
    return sum(values) / len(values)


def median(values):
    """Median value. Raises ValueError on an empty sequence."""
    values = sorted(values)
    if not values:
        raise ValueError("median of empty sequence")
    n = len(values)
    mid = n // 2
    if n % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2
