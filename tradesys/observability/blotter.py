import csv
from dataclasses import dataclass


@dataclass
class BlotterRow:
    bar_index: int
    side: str
    qty: int
    reason: str
    price: float
    cost: float


class Blotter:
    """trade ledger  plus a mark-to-market series for an equity curve."""

    def __init__(self):
        self.rows = []
        self.equity_curve = []

    def record(self, bar_index, order, fill) -> None:
        self.rows.append(BlotterRow(bar_index, order.side.value, order.qty, order.reason.value, fill.price, fill.cost))

    def mark(self, bar_index, close, lots, avg_entry) -> None:
        pnl = (close - avg_entry) * lots if (lots and avg_entry) else 0.0
        self.equity_curve.append((bar_index, close, lots, pnl))

    def to_csv(self, path: str) -> None:
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["bar_index", "side", "qty", "reason", "price", "cost"])
            for r in self.rows:
                w.writerow([r.bar_index, r.side, r.qty, r.reason, r.price, r.cost])

    def realized_pnl(self) -> float:
        return compute_realized_pnl(self.rows)


def compute_realized_pnl(rows) -> float:
    """ P&L accumulator , Blotter.realized_pnl and any test or
    report that needs realized P&L over a subset of rows both call this,
    so there is exactly one place the round-trip math can be wrong."""
    pnl, running_qty, running_cost = 0.0, 0, 0.0
    for r in rows:
        if r.side == "BUY":
            running_cost += r.price * r.qty
            running_qty += r.qty
        else:
            avg = running_cost / running_qty if running_qty else 0.0
            pnl += (r.price - avg) * r.qty
            running_qty, running_cost = 0, 0.0
        pnl -= r.cost
    return pnl
