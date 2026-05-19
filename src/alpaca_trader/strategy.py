"""Signal generation. Pure functions over price history — no I/O."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd


class Signal(str, Enum):
    LONG = "long"
    FLAT = "flat"


@dataclass(frozen=True)
class StrategyDecision:
    symbol: str
    signal: Signal
    fast: float
    slow: float
    last_close: float


class SmaCrossoverStrategy:
    """Long when fast SMA > slow SMA, flat otherwise.

    Daily bars in, one decision per symbol out. The strategy is stateless;
    the broker holds position state.
    """

    def __init__(self, fast: int, slow: int) -> None:
        if fast >= slow:
            raise ValueError("fast window must be smaller than slow window")
        if fast < 1:
            raise ValueError("fast window must be positive")
        self.fast = fast
        self.slow = slow

    @property
    def min_bars(self) -> int:
        return self.slow + 1

    def decide(self, symbol: str, bars: pd.DataFrame) -> StrategyDecision:
        if "close" not in bars.columns:
            raise ValueError(f"bars for {symbol} missing 'close' column")
        if len(bars) < self.min_bars:
            raise ValueError(
                f"need at least {self.min_bars} bars for {symbol}, got {len(bars)}"
            )

        closes = bars["close"].astype(float)
        fast_sma = closes.rolling(self.fast).mean().iloc[-1]
        slow_sma = closes.rolling(self.slow).mean().iloc[-1]
        last_close = closes.iloc[-1]

        signal = Signal.LONG if fast_sma > slow_sma else Signal.FLAT
        return StrategyDecision(
            symbol=symbol,
            signal=signal,
            fast=float(fast_sma),
            slow=float(slow_sma),
            last_close=float(last_close),
        )
