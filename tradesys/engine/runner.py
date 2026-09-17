import hashlib
import logging
from ..data.bars import BarSeries
from ..ta.atr import atr_series
from ..strategy.grid import GridStrategy
from ..oms.store import OrderStore
from ..observability.blotter import Blotter

log = logging.getLogger("tradesys.engine")


def make_client_order_id(strategy_id: str, seq: int) -> str:
    return hashlib.sha256(f"{strategy_id}:{seq}".encode()).hexdigest()[:16]


def run(strategy: GridStrategy, adapter, bars: BarSeries, store: OrderStore,blotter: Blotter, start_index: int = 0) -> None:
    """The one loop both the backtest and the live path run through.
    Every order is durably recorded before it is submitted, so replaying
    already-processed bars after a restart is a no-operation, not a duplicate."""
    all_bars = [bars.bar_at(i) for i in range(len(bars))]
    atrs = atr_series(all_bars, period=strategy.config.atr_period)

    for i in range(start_index, len(bars)):
        window = bars.window(i)
        for order in strategy.decide(window, atrs[i]):
            coid = make_client_order_id(strategy.strategy_id, order.seq)
            if not store.record_intent(coid, order, bar_index=i):
                log.info("DUPLICATE_SUPPRESSED", extra={"client_order_id": coid})
                continue
            fill = adapter.submit(order, coid, i)
            strategy.on_fill(order, fill.price)
            store.record_fill(coid, fill)
            blotter.record(i, order, fill)
            log.info("FILL", extra={
                "bar_index": i, "client_order_id": coid, "side": order.side.value,
                "reason": order.reason.value, "qty": order.qty, "price": fill.price,
            })
        blotter.mark(i, bars.bar_at(i).close, strategy.lots, strategy.avg_entry)
