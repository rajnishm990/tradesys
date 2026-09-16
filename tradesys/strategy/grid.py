from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Sequence
from ..data.bars import Bar


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderReason(Enum):
    ENTRY = "ENTRY"
    ADD = "ADD"
    TAKE_PROFIT = "TAKE_PROFIT"
    KILL_SWITCH = "KILL_SWITCH"


@dataclass(frozen=True)
class Order:
    side: OrderSide
    qty: int
    reason: OrderReason
    seq: int


@dataclass
class GridConfig:
    atr_period: int = 14
    entry_step_atr_mult: float = 1.0
    take_profit_atr_mult: float = 1.5
    kill_switch_atr_mult: float = 4.0
    max_lots: int = 5
    lot_size: int = 1


class GridStrategy:
    """ATR-spaced long-only grid: pyramids on adverse ATR-sized moves,
    capped by max_lots, flattens on take-profit, force-flattens and
    halts on a kill-switch move. This object never touches an adapter --
    it is the piece the backtest and live paths must share byte-for-byte."""

    def __init__(self, strategy_id: str, config: GridConfig = None):
        self.strategy_id = strategy_id
        self.config = config or GridConfig()
        self.lots = 0
        self.avg_entry: Optional[float] = None
        self.last_entry_price: Optional[float] = None
        self.halted = False
        self._seq = 0

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def seed_sequence(self, count: int) -> None:
        """Restore the sequence counter after a restart so resumed order
        ids never collide with ones already durably recorded."""
        self._seq = count

    def seed_position(self, lots: int, avg_entry: Optional[float], last_entry_price: Optional[float]) -> None:
        self.lots, self.avg_entry, self.last_entry_price = lots, avg_entry, last_entry_price

    def decide(self, window: Sequence[Bar], atr: Optional[float]) -> List[Order]:
        if self.halted or atr is None:
            return []

        price = window[-1].close
        cfg = self.config

        if self.lots == 0:
            return [Order(OrderSide.BUY, cfg.lot_size, OrderReason.ENTRY, self._next_seq())]

        if self.last_entry_price is not None and price <= self.last_entry_price - cfg.kill_switch_atr_mult * atr:
            self.halted = True
            return [Order(OrderSide.SELL, self.lots * cfg.lot_size, OrderReason.KILL_SWITCH, self._next_seq())]

        if self.avg_entry is not None and price >= self.avg_entry + cfg.take_profit_atr_mult * atr:
            return [Order(OrderSide.SELL, self.lots * cfg.lot_size, OrderReason.TAKE_PROFIT, self._next_seq())]

        if (self.lots < cfg.max_lots and self.last_entry_price is not None
                and price <= self.last_entry_price - cfg.entry_step_atr_mult * atr):
            return [Order(OrderSide.BUY, cfg.lot_size, OrderReason.ADD, self._next_seq())]

        return []

    def on_fill(self, order: Order, fill_price: float) -> None:
        if order.side == OrderSide.BUY:
            added_lots = order.qty // self.config.lot_size
            total_cost = (self.avg_entry or 0.0) * self.lots + fill_price * added_lots
            self.lots += added_lots
            self.avg_entry = total_cost / self.lots
            self.last_entry_price = fill_price
        else:
            self.lots = 0
            self.avg_entry = None
            self.last_entry_price = None
