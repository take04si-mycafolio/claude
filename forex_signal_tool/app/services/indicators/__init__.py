from .oscillators import calculate_oscillators
from .trend import calculate_trend
from .lines import calculate_lines
from .volatility import calculate_volatility
from .patterns import calculate_patterns

__all__ = [
    "calculate_oscillators",
    "calculate_trend",
    "calculate_lines",
    "calculate_volatility",
    "calculate_patterns",
]


def calculate_all(df):
    """全テクニカル指標を計算してまとめたdictを返す"""
    results = {}
    results.update(calculate_oscillators(df))
    results.update(calculate_trend(df))
    results.update(calculate_lines(df))
    results.update(calculate_volatility(df))
    results.update(calculate_patterns(df))
    return results
