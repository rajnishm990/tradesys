from typing import List, Optional, Sequence
from ..data.bars import Bar


def true_range(bar: Bar, prev_close: Optional[float]) -> float:
    if prev_close is None:
        return bar.high - bar.low
    return max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close))


def atr_series(bars: Sequence[Bar], period: int = 14) -> List[Optional[float]]:
    """Wilder's smoothed ATR. Index i only ever depends on bars[0..i] --
    the one indicator implementation the whole system imports."""
    trs = []
    prev_close = None
    for bar in bars:
        trs.append(true_range(bar, prev_close))
        prev_close = bar.close

    out: List[Optional[float]] = [None] * len(bars)
    if len(bars) < period:
        return out

    prev_atr = sum(trs[:period]) / period
    out[period - 1] = prev_atr
    for i in range(period, len(bars)):
        prev_atr = (prev_atr * (period - 1) + trs[i]) / period
        out[i] = prev_atr
    return out
