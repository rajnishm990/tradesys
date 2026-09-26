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
    SAR_FLIP = "SAR_FLIP" 
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
    sar_flip_atr_mult: float = 3.0 # Trigger for reversing position
    kill_switch_atr_mult: float = 5.0
    max_lots: int = 5
    lot_size: int = 1


def apply_fill(lots: int, avg_entry: Optional[float], last_entry_price: Optional[float],
               side: OrderSide, fill_lots: int, fill_price: float):
    """Position arithmetic for one fill, shared by GridStrategy.on_fill and
    OrderStore.reconciled_position so a restart rebuilds exactly the state the
    live process had. Positive lots = long, negative = short.

    Returns (lots, avg_entry, last_entry_price)."""
    signed = fill_lots if side == OrderSide.BUY else -fill_lots
    closing = (lots > 0 and signed < 0 and -signed >= lots) or \
              (lots < 0 and signed > 0 and signed >= -lots)
    if closing:
        new_lots = lots + signed
        if new_lots == 0:
            return 0, None, None
        # Stop-and-reverse: the surplus opens a fresh position at the fill price
        return new_lots, fill_price, fill_price
    total_cost = (avg_entry or 0.0) * abs(lots) + fill_price * abs(signed)
    new_lots = lots + signed
    return new_lots, total_cost / abs(new_lots), fill_price


class GridStrategy:
    """
    Bidirectional ATR-spaced grid with Stop-and-Reverse (SAR).
    Positive self.lots = Long, Negative self.lots = Short.
    """
    def __init__(self, strategy_id: str, config: GridConfig = None):
        self.strategy_id = strategy_id
        self.config = config or GridConfig()
        self.lots = 0  # < 0 means short, > 0 means long
        self.avg_entry: Optional[float] = None
        self.last_entry_price: Optional[float] = None
        self.halted = False
        self._seq = 0

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def seed_sequence(self, count: int) -> None:
        self._seq = count

    def seed_position(self, lots: int, avg_entry: Optional[float], last_entry_price: Optional[float]) -> None:
        self.lots, self.avg_entry, self.last_entry_price = lots, avg_entry, last_entry_price

    def decide(self, window: Sequence[Bar], atr: Optional[float]) -> List[Order]:
        if self.halted or atr is None:
            return []

        price = window[-1].close
        cfg = self.config

        # Flat state: Enter long if market is ticking up, Short if down (Simplified Entry)
        if self.lots == 0:
            side = OrderSide.BUY if window[-1].close > window[-2].close else OrderSide.SELL
            return [Order(side, cfg.lot_size, OrderReason.ENTRY, self._next_seq())]

        # LONG POSITION LOGIC
        if self.lots > 0:
            # Kill Switch (Disaster)
            if price <= self.last_entry_price - cfg.kill_switch_atr_mult * atr:
                self.halted = True
                return [Order(OrderSide.SELL, abs(self.lots) * cfg.lot_size, OrderReason.KILL_SWITCH, self._next_seq())]
            
            # Stop-and-Reverse (SAR): Trend changed violently downwards
            if price <= self.last_entry_price - cfg.sar_flip_atr_mult * atr:
                # Sell current position + open 1 short lot
                qty_to_flip = (abs(self.lots) * cfg.lot_size) + cfg.lot_size
                return [Order(OrderSide.SELL, qty_to_flip, OrderReason.SAR_FLIP, self._next_seq())]

            # Take Profit
            if price >= self.avg_entry + cfg.take_profit_atr_mult * atr:
                return [Order(OrderSide.SELL, abs(self.lots) * cfg.lot_size, OrderReason.TAKE_PROFIT, self._next_seq())]

            # Pyramid: Add to losing long position within grid limits
            if self.lots < cfg.max_lots and price <= self.last_entry_price - cfg.entry_step_atr_mult * atr:
                return [Order(OrderSide.BUY, cfg.lot_size, OrderReason.ADD, self._next_seq())]

        # SHORT POSITION LOGIC
        if self.lots < 0:
            # (Inverted logic for shorts: stop loss on price going UP, profit on price DOWN)
            if price >= self.last_entry_price + cfg.kill_switch_atr_mult * atr:
                self.halted = True
                return [Order(OrderSide.BUY, abs(self.lots) * cfg.lot_size, OrderReason.KILL_SWITCH, self._next_seq())]
            
            if price >= self.last_entry_price + cfg.sar_flip_atr_mult * atr:
                qty_to_flip = (abs(self.lots) * cfg.lot_size) + cfg.lot_size
                return [Order(OrderSide.BUY, qty_to_flip, OrderReason.SAR_FLIP, self._next_seq())]

            if price <= self.avg_entry - cfg.take_profit_atr_mult * atr:
                return [Order(OrderSide.BUY, abs(self.lots) * cfg.lot_size, OrderReason.TAKE_PROFIT, self._next_seq())]

            if abs(self.lots) < cfg.max_lots and price >= self.last_entry_price + cfg.entry_step_atr_mult * atr:
                return [Order(OrderSide.SELL, cfg.lot_size, OrderReason.ADD, self._next_seq())]

        return []

    def on_fill(self, order: Order, fill_price: float) -> None:
        fill_lots = order.qty // self.config.lot_size
        self.lots, self.avg_entry, self.last_entry_price = apply_fill(
            self.lots, self.avg_entry, self.last_entry_price, order.side, fill_lots, fill_price)
