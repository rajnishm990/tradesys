from tradesys.data.sample_loader import generate_synthetic_bars
from tradesys.data.bars import BarSeries
from tradesys.strategy.grid import GridStrategy, GridConfig
from tradesys.adapters.backtest import BacktestAdapter
from tradesys.oms.store import OrderStore
from tradesys.observability.blotter import Blotter
from tradesys.engine.runner import run


def _run(bars, n_bars):
    truncated = BarSeries([bars.bar_at(i) for i in range(n_bars)])
    strategy = GridStrategy("s", GridConfig())
    blotter = Blotter()
    run(strategy, BacktestAdapter(truncated), truncated, OrderStore(), blotter)
    return [(r.bar_index, r.side, r.reason) for r in blotter.rows]

def test_truncated_and_extended_runs_agree_on_the_shared_prefix():
    full_bars = generate_synthetic_bars(n_bars=120, seed=3)
    short_trades = _run(full_bars, 60)
    long_trades = _run(full_bars, 120)

    # Trades decided within the first 60 bars must be identical whether or
    # not bars 60..119 exist at all. If a future refactor lets the engine
    # peek ahead (e.g. computing ATR or a rolling stat over the whole
    # series instead of a prefix), this test starts failing.
    long_trades_in_prefix = [t for t in long_trades if t[0] < 60]
    assert short_trades == long_trades_in_prefix
    assert len(short_trades) > 0  # sanity: the scenario actually traded
