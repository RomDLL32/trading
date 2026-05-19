"""Integration-style test of run_tick with broker + data mocked out."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

import numpy as np
import pandas as pd

from alpaca_trader.broker import AccountSnapshot
from alpaca_trader.config import Settings
from alpaca_trader.runner import run_tick


@dataclass
class FakeBroker:
    snap: AccountSnapshot
    pos: dict[str, float]
    submitted: list = None

    def __post_init__(self) -> None:
        self.submitted = []

    def snapshot(self) -> AccountSnapshot:
        return self.snap

    def positions(self) -> dict[str, float]:
        return self.pos

    def submit(self, order) -> str:
        self.submitted.append(order)
        return "fake-id"


class FakeFetcher:
    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self._frames = frames

    def daily_bars(self, symbols, lookback_days):  # noqa: ARG002
        return self._frames


def _settings() -> Settings:
    return Settings(
        api_key="k",
        api_secret="s",
        base_url="https://paper-api.alpaca.markets",
        universe=("AAA", "BBB"),
        sma_fast=3,
        sma_slow=10,
        target_weight=0.2,
        max_gross_exposure=0.95,
        paper=True,
    )


def _rising_frame() -> pd.DataFrame:
    return pd.DataFrame({"close": list(np.linspace(100.0, 200.0, 20))})


def _falling_frame() -> pd.DataFrame:
    return pd.DataFrame({"close": list(np.linspace(200.0, 100.0, 20))})


def test_run_tick_skips_when_market_closed() -> None:
    broker = FakeBroker(
        snap=AccountSnapshot(equity=100_000, cash=100_000, buying_power=200_000, is_market_open=False),
        pos={},
    )
    with patch("alpaca_trader.runner.AlpacaBroker", return_value=broker), \
         patch("alpaca_trader.runner.BarFetcher", return_value=FakeFetcher({})):
        orders = run_tick(_settings())
    assert orders == []
    assert broker.submitted == []


def test_run_tick_buys_rising_symbol_and_skips_falling() -> None:
    broker = FakeBroker(
        snap=AccountSnapshot(equity=100_000, cash=100_000, buying_power=200_000, is_market_open=True),
        pos={},
    )
    frames = {"AAA": _rising_frame(), "BBB": _falling_frame()}
    with patch("alpaca_trader.runner.AlpacaBroker", return_value=broker), \
         patch("alpaca_trader.runner.BarFetcher", return_value=FakeFetcher(frames)):
        orders = run_tick(_settings())
    symbols = {o.symbol for o in orders}
    assert "AAA" in symbols
    assert "BBB" not in symbols  # never held, signal flat, no order needed
    assert len(broker.submitted) == len(orders)


def test_run_tick_dry_run_does_not_submit() -> None:
    broker = FakeBroker(
        snap=AccountSnapshot(equity=100_000, cash=100_000, buying_power=200_000, is_market_open=True),
        pos={},
    )
    frames = {"AAA": _rising_frame(), "BBB": _rising_frame()}
    with patch("alpaca_trader.runner.AlpacaBroker", return_value=broker), \
         patch("alpaca_trader.runner.BarFetcher", return_value=FakeFetcher(frames)):
        orders = run_tick(_settings(), dry_run=True)
    assert orders  # decided to buy
    assert broker.submitted == []  # but did not submit
