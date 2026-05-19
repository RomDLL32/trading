"""Compute per-symbol signal context for pre-trade research.

Pure functions over a price DataFrame — no I/O. The CLI fetches bars and
hands them to ``analyse``; tests can call it with synthetic frames.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ResearchReport:
    symbol: str
    bars_used: int
    last_close: float
    return_1d_pct: float | None
    return_5d_pct: float | None
    return_20d_pct: float | None
    sma_10: float | None
    sma_30: float | None
    sma_50: float | None
    sma_200: float | None
    pct_above_sma50: float | None
    pct_above_sma200: float | None
    realized_vol_20d_ann_pct: float | None
    rsi_14: float | None
    high_52w: float | None
    low_52w: float | None
    pct_from_52w_high: float | None
    pct_from_52w_low: float | None
    volume_ratio_20d: float | None
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _safe_pct(numer: float | None, denom: float | None) -> float | None:
    if numer is None or denom is None or denom == 0:
        return None
    return (numer / denom - 1.0) * 100.0


def _sma(closes: pd.Series, window: int) -> float | None:
    if len(closes) < window:
        return None
    return float(closes.tail(window).mean())


def _rsi(closes: pd.Series, period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    delta = closes.diff().dropna()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.tail(period).mean()
    avg_loss = loss.tail(period).mean()
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def analyse(symbol: str, bars: pd.DataFrame) -> ResearchReport:
    notes: list[str] = []

    if bars is None or bars.empty or "close" not in bars.columns:
        return ResearchReport(
            symbol=symbol, bars_used=0, last_close=float("nan"),
            return_1d_pct=None, return_5d_pct=None, return_20d_pct=None,
            sma_10=None, sma_30=None, sma_50=None, sma_200=None,
            pct_above_sma50=None, pct_above_sma200=None,
            realized_vol_20d_ann_pct=None, rsi_14=None,
            high_52w=None, low_52w=None,
            pct_from_52w_high=None, pct_from_52w_low=None,
            volume_ratio_20d=None,
            notes=["no bars available"],
        )

    closes = bars["close"].astype(float)
    last_close = float(closes.iloc[-1])

    def lookback_return(n: int) -> float | None:
        if len(closes) <= n:
            return None
        prior = float(closes.iloc[-1 - n])
        if prior == 0:
            return None
        return (last_close / prior - 1.0) * 100.0

    return_1d = lookback_return(1)
    return_5d = lookback_return(5)
    return_20d = lookback_return(20)

    sma_10 = _sma(closes, 10)
    sma_30 = _sma(closes, 30)
    sma_50 = _sma(closes, 50)
    sma_200 = _sma(closes, 200)

    pct_above_sma50 = _safe_pct(last_close, sma_50)
    pct_above_sma200 = _safe_pct(last_close, sma_200)

    vol = None
    if len(closes) >= 21:
        daily_ret = closes.pct_change().dropna().tail(20)
        vol = float(daily_ret.std() * np.sqrt(252) * 100.0)

    rsi = _rsi(closes, 14)

    high_52w = float(closes.tail(252).max()) if len(closes) >= 1 else None
    low_52w = float(closes.tail(252).min()) if len(closes) >= 1 else None
    pct_from_high = _safe_pct(last_close, high_52w)
    pct_from_low = _safe_pct(last_close, low_52w)

    volume_ratio = None
    if "volume" in bars.columns and len(bars) >= 21:
        recent_vol = float(bars["volume"].iloc[-1])
        avg_vol = float(bars["volume"].tail(20).mean())
        if avg_vol > 0:
            volume_ratio = recent_vol / avg_vol

    # Annotations to help the reader spot regimes quickly.
    if rsi is not None and rsi >= 70:
        notes.append(f"RSI {rsi:.1f} — overbought")
    if rsi is not None and rsi <= 30:
        notes.append(f"RSI {rsi:.1f} — oversold")
    if pct_above_sma200 is not None and pct_above_sma200 < 0:
        notes.append("below 200-day SMA (long-term downtrend signal)")
    if pct_from_high is not None and pct_from_high <= -15:
        notes.append(f"{abs(pct_from_high):.1f}% off 52w high (correction territory)")
    if volume_ratio is not None and volume_ratio >= 1.75:
        notes.append(f"volume {volume_ratio:.1f}x 20-day avg")

    return ResearchReport(
        symbol=symbol,
        bars_used=int(len(closes)),
        last_close=last_close,
        return_1d_pct=return_1d,
        return_5d_pct=return_5d,
        return_20d_pct=return_20d,
        sma_10=sma_10,
        sma_30=sma_30,
        sma_50=sma_50,
        sma_200=sma_200,
        pct_above_sma50=pct_above_sma50,
        pct_above_sma200=pct_above_sma200,
        realized_vol_20d_ann_pct=vol,
        rsi_14=rsi,
        high_52w=high_52w,
        low_52w=low_52w,
        pct_from_52w_high=pct_from_high,
        pct_from_52w_low=pct_from_low,
        volume_ratio_20d=volume_ratio,
        notes=notes,
    )
