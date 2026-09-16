from ..data.bars import BarSeries
from ..strategy.grid import Order, OrderSide
from .base import Fill


class BacktestAdapter:
    """Fills at the NEXT bar's open , an order decided using bar i's close
    cannot execute inside bar i, it wasn't over yet when the decision was
    made. Slippage and commission are modelled explicitly here, nowhere else."""

    def __init__(self, bars: BarSeries, slippage_bps: float = 0.0, commission_per_order: float = 0.0):
        self.bars = bars
        self.slippage_bps = slippage_bps
        self.commission_per_order = commission_per_order

    def submit(self, order: Order, client_order_id: str, bar_index: int) -> Fill:
        ref_price = self.bars.next_open(bar_index)
        slip = ref_price * self.slippage_bps / 10_000
        fill_price = ref_price + slip if order.side == OrderSide.BUY else ref_price - slip
        return Fill(client_order_id, fill_price, order.qty, self.commission_per_order, bar_index + 1)
