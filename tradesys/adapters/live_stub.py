import logging
from ..data.bars import BarSeries
from ..strategy.grid import Order
from .base import Fill

log = logging.getLogger("tradesys.live_stub")


class LiveStubAdapter:
    """dummy for a real KiteAdapter. Same submit() signature, same
    next-bar-open fill-timing convention as BacktestAdapter, but zero cost
    and no network call , it logs the order it WOULD have sent. Swapping
    this for a real Kite client later means writing one new adapter class,
    not touching the strategy or the engine loop."""

    def __init__(self, bars: BarSeries):
        self.bars = bars

    def submit(self, order: Order, client_order_id: str, bar_index: int) -> Fill:
        price = self.bars.next_open(bar_index)
        log.info("ORDER_SENT", extra={
            "client_order_id": client_order_id, "side": order.side.value,
            "qty": order.qty, "reason": order.reason.value, "ref_price": price,
        })
        return Fill(client_order_id, price, order.qty, 0.0, bar_index + 1)
