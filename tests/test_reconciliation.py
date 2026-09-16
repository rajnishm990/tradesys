from tradesys.data.sample_loader import generate_synthetic_bars
from tradesys.strategy.grid import GridStrategy, GridConfig
from tradesys.adapters.backtest import BacktestAdapter
from tradesys.adapters.live_stub import LiveStubAdapter
from tradesys.oms.store import OrderStore
from tradesys.observability.blotter import Blotter, compute_realized_pnl
from tradesys.engine.runner import run


def test_zero_cost_backtest_and_live_stub_produce_identical_fills():
    """The core architectural claim: strategy decisions and fills depend
    only on the shared engine + strategy, never on which adapter drives
    them. With the cost model zeroed out there is nothing left to explain
    a difference, so the two runs must match fill-for-fill."""
    bars = generate_synthetic_bars(n_bars=200, seed=11, vol=0.015)

    bt_blotter = Blotter()
    run(GridStrategy("s", GridConfig()), BacktestAdapter(bars, slippage_bps=0, commission_per_order=0),
        bars, OrderStore(), bt_blotter)

    live_blotter = Blotter()
    run(GridStrategy("s", GridConfig()), LiveStubAdapter(bars), bars, OrderStore(), live_blotter)

    bt_trades = [(r.bar_index, r.side, r.reason, round(r.price, 6)) for r in bt_blotter.rows]
    live_trades = [(r.bar_index, r.side, r.reason, round(r.price, 6)) for r in live_blotter.rows]
    assert bt_trades == live_trades
    assert len(bt_trades) > 0

def test_realistic_cost_run_is_worse_than_zero_cost_by_exactly_the_modelled_cost():
    """With costs turned on, the backtest must underperform the zero-cost
    run by precisely the cost paid -- if it doesn't, some cost is being
    applied (or double-applied) somewhere the model doesn't account for."""
    bars = generate_synthetic_bars(n_bars=80, seed=5, vol=0.01)

    cheap = Blotter()
    run(GridStrategy("s", GridConfig()), BacktestAdapter(bars, slippage_bps=0, commission_per_order=0),
        bars, OrderStore(), cheap)

    costed = Blotter()
    run(GridStrategy("s", GridConfig()), BacktestAdapter(bars, slippage_bps=5, commission_per_order=1.0),
        bars, OrderStore(), costed)

    # Same trade count/reasons expected at this cost level (small slippage,
    # short series) -- if this assert ever fails it means cost drift pushed
    # a trigger onto a different bar, which is a real and useful thing to know.
    assert [(r.bar_index, r.reason) for r in cheap.rows] == [(r.bar_index, r.reason) for r in costed.rows]

    # Only compare over CLOSED round trips: an open tail position carries
    # unrealized slippage that hasn't hit P&L yet on either side, so it must
    # be excluded from both the cost sum and the pnl comparison equally.
    closed_upto = max(i for i, r in enumerate(cheap.rows) if r.reason in ("TAKE_PROFIT", "KILL_SWITCH")) + 1
    cheap_closed, costed_closed = cheap.rows[:closed_upto], costed.rows[:closed_upto]

    total_cost = sum(abs(c.price - h.price) * c.qty + c.cost for c, h in zip(costed_closed, cheap_closed))
    pnl_gap = compute_realized_pnl(cheap_closed) - compute_realized_pnl(costed_closed)
    assert round(pnl_gap, 6) == round(total_cost, 6)
