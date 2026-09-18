from tradesys.data.bars import Bar, BarSeries
from tradesys.data.sample_loader import generate_synthetic_bars
from tradesys.strategy.grid import GridStrategy, GridConfig
from tradesys.adapters.backtest import BacktestAdapter
from tradesys.oms.store import OrderStore
from tradesys.observability.blotter import Blotter
from tradesys.engine.runner import run

# Golden master, captured from an actual run on seed=1 and pinned here.
# Any change to ATR, the grid trigger logic, or fill timing that alters
# this sequence must be a deliberate, reviewed strategy change.
# Re-pinned when the grid became bidirectional (stop-and-reverse): from
# bar 27 onward the flat strategy opens SHORT on a down-close, so the
# sequence below mixes long and short round trips.
EXPECTED_TRADES = [
    (13, "BUY", "ENTRY", 104.018),
    (14, "BUY", "ADD", 101.7664),
    (20, "SELL", "TAKE_PROFIT", 106.8611),
    (21, "BUY", "ENTRY", 108.255),
    (26, "SELL", "TAKE_PROFIT", 113.4822),
    (27, "SELL", "ENTRY", 110.4572),
    (30, "SELL", "ADD", 114.0696),
    (33, "BUY", "TAKE_PROFIT", 107.4983),
    (34, "SELL", "ENTRY", 105.3676),
    (36, "SELL", "ADD", 108.0005),
    (37, "SELL", "ADD", 110.8813),
    (39, "BUY", "TAKE_PROFIT", 103.5893),
    (40, "BUY", "ENTRY", 103.9212),
    (42, "BUY", "ADD", 99.7278),
    (54, "BUY", "ADD", 96.1269),
]
# two long + two short round trips: 7.9378 + 5.2272 + 9.5302 + 13.4815
EXPECTED_PNL = 36.1766


def test_golden_master_trade_sequence_seed_1():
    bars = generate_synthetic_bars(n_bars=60, seed=1, vol=0.02)
    strategy = GridStrategy("regr", GridConfig())
    blotter = Blotter()
    run(strategy, BacktestAdapter(bars, slippage_bps=0, commission_per_order=0), bars, OrderStore(), blotter)

    actual = [(r.bar_index, r.side, r.reason, round(r.price, 4)) for r in blotter.rows]
    assert actual == EXPECTED_TRADES
    assert round(blotter.realized_pnl(), 4) == EXPECTED_PNL
    # open tail: long 3 lots (entry at 40 plus two adds), never halted
    assert strategy.lots == 3
    assert strategy.halted is False


def test_position_cap_stops_adds_at_max_lots():
    """A steady decline keeps triggering long ADDs one ATR apart. Once
    abs(lots) reaches max_lots no further ADD may be issued, however far
    price keeps falling, until a SAR flip or kill switch changes the position."""
    # 13 flat bars, then an up-tick on the first bar with an ATR (bar 13) so the
    # flat strategy opens LONG, then a steady fall that triggers ADD after ADD
    closes = [100.0] * 13 + [101.0] + [101.0 - 3.0 * k for k in range(1, 26)]
    bars = BarSeries([Bar(ts=i, open=c, high=c + 1.0, low=c - 1.0, close=c) for i, c in enumerate(closes)])
    cfg = GridConfig()
    strategy = GridStrategy("cap", cfg)
    blotter = Blotter()
    run(strategy, BacktestAdapter(bars, 0, 0), bars, OrderStore(), blotter)

    adds_before_flip = 0
    for r in blotter.rows:
        if r.reason in ("SAR_FLIP", "KILL_SWITCH"):
            break
        if r.reason == "ADD":
            adds_before_flip += 1
    assert adds_before_flip == cfg.max_lots - 1          # 1 ENTRY + 4 ADDs = max_lots
    assert max(abs(lots) for _, _, lots, _ in blotter.equity_curve) == cfg.max_lots
