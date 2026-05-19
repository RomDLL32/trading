"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


PAPER_ENDPOINT = "https://paper-api.alpaca.markets"


@dataclass(frozen=True)
class Settings:
    api_key: str
    api_secret: str
    base_url: str
    universe: tuple[str, ...]
    sma_fast: int
    sma_slow: int
    target_weight: float
    max_gross_exposure: float
    paper: bool = field(default=True)

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        api_key = os.environ.get("APCA_API_KEY_ID", "")
        api_secret = os.environ.get("APCA_API_SECRET_KEY", "")
        base_url = os.environ.get("APCA_API_BASE_URL", PAPER_ENDPOINT)

        universe_raw = os.environ.get("TRADING_UNIVERSE", "SPY,QQQ,AAPL,MSFT,NVDA")
        universe = tuple(s.strip().upper() for s in universe_raw.split(",") if s.strip())

        sma_fast = int(os.environ.get("TRADING_SMA_FAST", "10"))
        sma_slow = int(os.environ.get("TRADING_SMA_SLOW", "30"))
        if sma_fast >= sma_slow:
            raise ValueError(f"sma_fast ({sma_fast}) must be < sma_slow ({sma_slow})")

        target_weight = float(os.environ.get("TRADING_TARGET_WEIGHT", "0.18"))
        max_gross = float(os.environ.get("TRADING_MAX_GROSS_EXPOSURE", "0.95"))

        return cls(
            api_key=api_key,
            api_secret=api_secret,
            base_url=base_url,
            universe=universe,
            sma_fast=sma_fast,
            sma_slow=sma_slow,
            target_weight=target_weight,
            max_gross_exposure=max_gross,
            paper=base_url == PAPER_ENDPOINT,
        )

    def require_credentials(self) -> None:
        if not self.api_key or not self.api_secret:
            raise RuntimeError(
                "Alpaca paper credentials missing. Set APCA_API_KEY_ID and "
                "APCA_API_SECRET_KEY in the environment or a .env file."
            )
