"""Core arithmetic."""


def add(a, b):
    """Return a + b."""
    return a + b


def subtract(a, b):
    """Return a - b."""
    return a - b


def multiply(a, b):
    """Return a * b."""
    return a * b


def divide(a, b):
    """Return a / b. Raises ZeroDivisionError with a clear message when b is 0."""
    if b == 0:
        raise ZeroDivisionError("Cannot devide by zero")
    return a / b
