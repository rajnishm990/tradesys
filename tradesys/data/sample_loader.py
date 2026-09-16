import random
from .bars import Bar, BarSeries


def generate_synthetic_bars(n_bars=250, start_price=100.0, seed=42, drift=0.0, vol=0.012) -> BarSeries:
    """Random-walk OHLC. Seeded, so runs are reproducible , this required for
    regression tests to pin an exact expected output."""
    rng = random.Random(seed)
    bars = []
    price = start_price
    for i in range(n_bars):
        change = rng.gauss(drift, vol) * price
        open_ = price
        close = max(0.5, price + change)
        wick = abs(rng.gauss(0, vol * price * 0.3))
        high = max(open_, close) + wick
        low = max(0.1, min(open_, close) - wick)
        bars.append(Bar(ts=i, open=open_, high=high, low=low, close=close))
        price = close
    return BarSeries(bars)
