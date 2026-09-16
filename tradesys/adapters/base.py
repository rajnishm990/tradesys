from dataclasses import dataclass


@dataclass(frozen=True)
class Fill:
    client_order_id: str
    price: float
    qty: int
    cost: float
    ts: int
