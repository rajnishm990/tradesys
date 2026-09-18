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
    so there is exactly one place the round-trip math can be wrong.

    Position is signed (BUY +qty, SELL -qty). A fill in the direction of
    the open position adds at a new average cost; a fill against it realizes
    P&L on the units closed. A stop-and-reverse closes everything and opens
    the surplus at the fill price."""
    pnl, pos, avg = 0.0, 0, 0.0
    for r in rows:
        signed = r.qty if r.side == "BUY" else -r.qty
        if pos == 0 or (pos > 0) == (signed > 0):
            avg = (avg * abs(pos) + r.price * abs(signed)) / (abs(pos) + abs(signed))
            pos += signed
        else:
            closed = min(abs(pos), abs(signed))
            pnl += (r.price - avg) * closed * (1 if pos > 0 else -1)
            new_pos = pos + signed
            if new_pos == 0:
                avg = 0.0
            elif (new_pos > 0) != (pos > 0):
                avg = r.price
            pos = new_pos
        pnl -= r.cost
    return pnl
