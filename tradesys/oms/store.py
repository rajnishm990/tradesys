import sqlite3
from ..strategy.grid import Order, OrderSide, apply_fill


class OrderStore:
    """Order INtent is written here before being sent to adapter . This helps us in idempotency .. Our Engine first checks OMS to see if order Id existws or not."""

    def __init__(self, path: str = ":memory:"):
        self.conn = sqlite3.connect(path)
        self.conn.execute("""CREATE TABLE IF NOT EXISTS orders (
            client_order_id TEXT PRIMARY KEY, bar_index INTEGER,
            side TEXT, qty INTEGER, reason TEXT, status TEXT
        )""")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS fills (
            client_order_id TEXT PRIMARY KEY, price REAL, qty INTEGER, cost REAL, ts INTEGER
        )""")
        self.conn.commit()

    def record_intent(self, client_order_id: str, order: Order, bar_index: int) -> bool:
        try:
            self.conn.execute(
                "INSERT INTO orders VALUES (?, ?, ?, ?, ?, 'SUBMITTED')",
                (client_order_id, bar_index, order.side.value, order.qty, order.reason.value),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def record_fill(self, client_order_id: str, fill) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO fills VALUES (?, ?, ?, ?, ?)",
            (client_order_id, fill.price, fill.qty, fill.cost, fill.ts),
        )
        self.conn.execute("UPDATE orders SET status='FILLED' WHERE client_order_id=?", (client_order_id,))
        self.conn.commit()

    def count_orders(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]

    def reconciled_position(self, lot_size: int = 1):
        """Rebuilds lots / avg entry / last entry purely from durable fills.
        Used on restart instead of trusting whatever was in memory when
        the process died -- this is 'position and P&L truth'.

        Replays every fill through the same apply_fill() the strategy uses,
        so longs, shorts and stop-and-reverse flips all reconcile."""
        rows = self.conn.execute(
            "SELECT o.side, f.qty, f.price FROM orders o JOIN fills f "
            "ON o.client_order_id = f.client_order_id ORDER BY f.ts, o.bar_index, o.rowid"
        ).fetchall()
        lots, avg_entry, last_entry = 0, None, None
        for side, qty, price in rows:
            lots, avg_entry, last_entry = apply_fill(
                lots, avg_entry, last_entry, OrderSide(side), qty // lot_size, price)
        return lots, avg_entry, last_entry
