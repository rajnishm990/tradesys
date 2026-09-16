from tradesys.data.tick_codec import Tick
from tradesys.data.validation import TickValidator


def test_rejects_non_positive_price():
    v = TickValidator()
    assert v.validate(Tick(1, 0.0, "ltp")) == "non_positive_price"

def test_rejects_extreme_jump_but_accepts_normal_moves():
    v = TickValidator(max_jump_pct=0.2)
    assert v.validate(Tick(1, 100.0, "ltp")) is None
    assert v.validate(Tick(1, 101.0, "ltp")) is None       # +1%, fine
    assert v.validate(Tick(1, 500.0, "ltp")) is not None   # +395%, rejected
