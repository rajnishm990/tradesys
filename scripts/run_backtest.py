import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tradesys.data.sample_loader import generate_synthetic_bars
from tradesys.strategy.grid import GridStrategy, GridConfig
from tradesys.adapters.backtest import BacktestAdapter
from tradesys.oms.store import OrderStore
from tradesys.observability.blotter import Blotter
from tradesys.observability import logging_setup
from tradesys.engine.runner import run

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "artifacts")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    logging_setup.configure(os.path.join(OUT_DIR, "backtest.log"))

    bars = generate_synthetic_bars(n_bars=250, start_price=100.0, seed=7, vol=0.012)
    strategy = GridStrategy("grid-demo", GridConfig())
    adapter = BacktestAdapter(bars, slippage_bps=5, commission_per_order=1.0)
    blotter = Blotter()
    run(strategy, adapter, bars, OrderStore(), blotter)

    blotter.to_csv(os.path.join(OUT_DIR, "backtest_blotter.csv"))
    with open(os.path.join(OUT_DIR, "backtest_equity_curve.csv"), "w") as f:
        f.write("bar_index,close,lots,unrealized_pnl\n")
        for row in blotter.equity_curve:
            f.write(",".join(str(x) for x in row) + "\n")

    print("- - -  BACKTEST SUMMARY - - - ")
    print(f"bars processed : {len(bars)}")
    print(f"trades         : {len(blotter.rows)}")
    print(f"realized pnl   : {blotter.realized_pnl():.2f}")
    print(f"final lots     : {strategy.lots}")
    print(f"halted (kill)  : {strategy.halted}")
    print(f"blotter -> {OUT_DIR}/backtest_blotter.csv")


if __name__ == "__main__":
    main()
