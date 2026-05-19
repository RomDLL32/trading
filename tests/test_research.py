import numpy as np
import pandas as pd

from alpaca_trader.research import analyse


def _frame(closes: list[float], volumes: list[float] | None = None) -> pd.DataFrame:
    data = {"close": closes}
    if volumes is not None:
        data["volume"] = volumes
    return pd.DataFrame(data)


def test_handles_no_bars() -> None:
    r = analyse("XYZ", pd.DataFrame())
    assert r.bars_used == 0
    assert "no bars available" in r.notes


def test_steady_uptrend_metrics() -> None:
    closes = list(np.linspace(100.0, 200.0, 260))
    r = analyse("XYZ", _frame(closes))
    assert r.bars_used == 260
    assert r.last_close == 200.0
    # In a monotone uptrend, today is the 52w high.
    assert r.pct_from_52w_high == 0.0
    assert r.pct_from_52w_low is not None and r.pct_from_52w_low > 90.0
    # All SMAs should be below the last close.
    assert r.sma_50 is not None and r.sma_50 < r.last_close
    assert r.sma_200 is not None and r.sma_200 < r.last_close
    assert r.pct_above_sma200 is not None and r.pct_above_sma200 > 0


def test_downtrend_flags_below_sma200() -> None:
    closes = list(np.linspace(200.0, 100.0, 260))
    r = analyse("XYZ", _frame(closes))
    assert r.pct_above_sma200 is not None and r.pct_above_sma200 < 0
    assert any("below 200-day SMA" in n for n in r.notes)
    assert any("off 52w high" in n for n in r.notes)


def test_rsi_extremes() -> None:
    # All up days → RSI should be near 100.
    rsi_up = analyse("UP", _frame(list(np.linspace(100.0, 130.0, 30)))).rsi_14
    assert rsi_up is not None and rsi_up > 70

    # All down days → RSI should be near 0.
    rsi_down = analyse("DN", _frame(list(np.linspace(130.0, 100.0, 30)))).rsi_14
    assert rsi_down is not None and rsi_down < 30


def test_volume_spike_note() -> None:
    closes = [100.0] * 30
    volumes = [1_000_000.0] * 29 + [3_000_000.0]
    r = analyse("XYZ", _frame(closes, volumes))
    assert r.volume_ratio_20d is not None and r.volume_ratio_20d >= 2.5
    assert any("volume" in n for n in r.notes)


def test_short_history_returns_partial_metrics() -> None:
    # 15 bars — enough for 10-SMA + RSI, not enough for 30/50/200/vol.
    closes = list(np.linspace(100.0, 110.0, 15))
    r = analyse("XYZ", _frame(closes))
    assert r.sma_10 is not None
    assert r.sma_30 is None
    assert r.sma_200 is None
    assert r.realized_vol_20d_ann_pct is None
