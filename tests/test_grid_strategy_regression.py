from tradesys.data.sample_loader import generate_synthetic_bars
from tradesys.strategy.grid import GridStrategy, GridConfig
from tradesys.adapters.backtest import BacktestAdapter
from tradesys.oms.store import OrderStore
from tradesys.observability.blotter import Blotter
from tradesys.engine.runner import run

# Golden master, captured from an actual run on seed=1 and pinned here.
# Any change to ATR, the grid trigger logic, or fill timing that alters
# this sequence must be a deliberate, reviewed strategy change -- that is
# what "every strategy change ships with a regression test" means in practice.
EXPECTED_TRADES = [
    (13, "BUY", "ENTRY", 104.018),
    (14, "BUY", "ADD", 101.7664),
    (20, "SELL", "TAKE_PROFIT", 106.8611),
    (21, "BUY", "ENTRY", 108.255),
    (26, "SELL", "TAKE_PROFIT", 113.4822),
    (27, "BUY", "ENTRY", 110.4572),
    (33, "BUY", "ADD", 107.4983),
    (35, "BUY", "ADD", 104.8523),
    (42, "BUY", "ADD", 99.7278),
    (54, "BUY", "ADD", 96.1269),
]
EXPECTED_PNL = 13.1649


def test_golden_master_trade_sequence_seed_1():
    bars = generate_synthetic_bars(n_bars=60, seed=1, vol=0.02)
    strategy = GridStrategy("regr", GridConfig())
    blotter = Blotter()
    run(strategy, BacktestAdapter(bars, slippage_bps=0, commission_per_order=0), bars, OrderStore(), blotter)

    actual = [(r.bar_index, r.side, r.reason, round(r.price, 4)) for r in blotter.rows]
    assert actual == EXPECTED_TRADES
    assert round(blotter.realized_pnl(), 4) == EXPECTED_PNL
    # this scenario is specifically chosen because it exercises the position
    # cap: 5 ADDs land it exactly at max_lots with no 6th add ever attempted
    assert strategy.lots == GridConfig().max_lots
