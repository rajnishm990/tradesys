from tradesys.data.bars import Bar
from tradesys.ta.atr import true_range, atr_series


def test_true_range_first_bar_has_no_prev_close():
    bar = Bar(0, open=10, high=12, low=9, close=11)
    assert true_range(bar, None) == 3

def test_true_range_uses_prev_close_when_it_widens_range():
    bar = Bar(1, open=11, high=12, low=11.5, close=11.8)
    assert true_range(bar, prev_close=9) == 3  # |12-9| beats high-low of 0.5

def test_atr_series_hand_computed_reference():
    # 4 bars, period=3: TRs are 2, 3, 1, 4 -> first ATR = mean(2,3,1)=2.0
    # then Wilder step: (2.0*2 + 4)/3 = 2.6667
    bars = [
        Bar(0, 10, 12, 10, 11),   # TR=2 (no prev close)
        Bar(1, 11, 13, 10, 12),   # TR=max(3, |13-11|, |10-11|)=3
        Bar(2, 12, 12.5, 11.5, 12), # TR=max(1, |12.5-12|,|11.5-12|)=1
        Bar(3, 12, 15, 11, 13),   # TR=max(4, |15-12|, |11-12|)=4
    ]
    out = atr_series(bars, period=3)
    assert out[0] is None and out[1] is None
    assert round(out[2], 4) == 2.0
    assert round(out[3], 4) == 2.6667

def test_atr_series_too_short_returns_all_none():
    bars = [Bar(0, 1, 2, 1, 1.5), Bar(1, 1.5, 2, 1, 1.8)]
    assert atr_series(bars, period=5) == [None, None]
