import numpy as np
import pandas as pd
import pytest

from alpaca_trader.strategy import Signal, SmaCrossoverStrategy


def _frame(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"close": closes})


def test_long_signal_when_fast_above_slow() -> None:
    # Rising prices -> fast SMA > slow SMA.
    closes = list(np.linspace(100.0, 200.0, 40))
    strat = SmaCrossoverStrategy(fast=5, slow=20)
    decision = strat.decide("XYZ", _frame(closes))
    assert decision.signal is Signal.LONG
    assert decision.fast > decision.slow


def test_flat_signal_when_fast_below_slow() -> None:
    closes = list(np.linspace(200.0, 100.0, 40))
    strat = SmaCrossoverStrategy(fast=5, slow=20)
    decision = strat.decide("XYZ", _frame(closes))
    assert decision.signal is Signal.FLAT
    assert decision.fast < decision.slow


def test_rejects_insufficient_bars() -> None:
    strat = SmaCrossoverStrategy(fast=5, slow=20)
    with pytest.raises(ValueError, match="need at least"):
        strat.decide("XYZ", _frame([100.0] * 10))


def test_rejects_bad_windows() -> None:
    with pytest.raises(ValueError):
        SmaCrossoverStrategy(fast=20, slow=5)
    with pytest.raises(ValueError):
        SmaCrossoverStrategy(fast=0, slow=5)


def test_missing_close_column() -> None:
    strat = SmaCrossoverStrategy(fast=2, slow=4)
    with pytest.raises(ValueError, match="close"):
        strat.decide("XYZ", pd.DataFrame({"price": [1, 2, 3, 4, 5]}))
