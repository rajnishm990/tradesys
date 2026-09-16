from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Bar:
    ts: int
    open: float
    high: float
    low: float
    close: float


class BarSeries:
    """Holds the full bar history but only ever hands out a prefix.
    A strategy fed 'window(i)' physically cannot see bar i+1 onward """

    def __init__(self, bars: Sequence[Bar]):
        self._bars = list(bars)

    def __len__(self) -> int:
        return len(self._bars)

    def window(self, upto_index: int) -> Sequence[Bar]:
        return self._bars[: upto_index + 1]

    def bar_at(self, index: int) -> Bar:
        return self._bars[index]

    def next_open(self, index: int) -> float:
        if index + 1 < len(self._bars):
            return self._bars[index + 1].open
        return self._bars[index].close
