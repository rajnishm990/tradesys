from typing import Optional 


class TickValidator:
    """ per intstrument sanity check for incoming tick data .. note that it needs previous price to calcualte jump """

    def __init__(self, max_jump_pct: float=0.2):
        self.max_jump_pct = max_jump_pct 
        self.last_price = {} 

    def validate(self , tick) -> Optional[str]:
        if tick.last_price <= 0:
            return "non_positive_price"
        prev = self._last_price.get(tick.instrument_token)
        if prev and abs(tick.last_price - prev) / prev > self.max_jump_pct:
            return f"price_jump_{tick.last_price}_vs_{prev}"
        self._last_price[tick.instrument_token] = tick.last_price
        return None