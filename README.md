# tradesys


## Run

```
pip install pytest  # only dependency
python -m pytest tests/ -v            
python scripts/run_backtest.py        # backtest over 250 synthetic bars
python scripts/run_live_stub.py       # live-stub run + reconciliation + crash/restart + alert demo
```

Outputs land in `artifacts/`: `backtest_blotter.csv`, `backtest_equity_curve.csv`,
`backtest.log`, `live_stub.log` (all JSON-lines).

## NOTE 

`engine/runner.py`'s `run()` function is used, unmodified, by both
`run_backtest.py` and `run_live_stub.py`. The only thing that differs
between a backtest and a "live" run is which adapter object gets passed in.
That's the whole point: strategy decisions cannot depend on which mode
we're in, because there is no branch in the code that knows which mode
it's in.

## stubbed, and what swapping it for real means

`adapters/live_stub.py` has the exact same method signature as
`adapters/backtest.py`. A real `KiteAdapter` implementing `submit()` against
Kite Connect's order API is a new file in `adapters/`, not a change to
`strategy/`, `engine/`, or `oms/`. Same for a real tick feed: it needs to
produce `Bar` objects (or a streaming equivalent) to feed a `BarSeries`;
nothing downstream needs to know it isn't synthetic data.

`data/sample_loader.py` generates a random walk. Swapping it for Kite
historical data or a tick-vendor file is a data-layer change only.


