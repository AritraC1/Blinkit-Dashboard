"""Template tags: number formatting for the dashboard.

The data does not state a currency, so no symbol is ever added.
"""

from __future__ import annotations

from django import template

register = template.Library()


def _as_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@register.filter
def thousands(value) -> str:
    """1_234_567.8 -> "1,234,568" (thousands separators, no decimals)."""
    return f"{_as_float(value):,.0f}"


@register.filter
def compact(value) -> str:
    """Compact display: 1_234 -> "1.2K", 5_600_000 -> "5.6M"."""
    number = _as_float(value)
    abs_number = abs(number)
    if abs_number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    if abs_number >= 1_000:
        return f"{number / 1_000:.1f}K"
    return f"{number:,.0f}"


@register.filter
def one_decimal(value) -> str:
    """3.966 -> "4.0" (one decimal place)."""
    return f"{_as_float(value):.1f}"
