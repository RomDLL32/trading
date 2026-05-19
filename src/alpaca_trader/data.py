"""Historical-bar fetching from Alpaca."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


class BarFetcher:
    """Thin wrapper around alpaca-py's historical client."""

    def __init__(self, api_key: str, api_secret: str) -> None:
        self._client = StockHistoricalDataClient(api_key, api_secret)

    def daily_bars(
        self,
        symbols: list[str],
        lookback_days: int,
    ) -> dict[str, pd.DataFrame]:
        end = datetime.now(tz=timezone.utc) - timedelta(minutes=20)
        # Pull extra calendar days to cover weekends/holidays.
        start = end - timedelta(days=lookback_days * 2 + 14)

        req = StockBarsRequest(
            symbol_or_symbols=list(symbols),
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            feed="iex",  # paper accounts get IEX feed for free
        )
        resp = self._client.get_stock_bars(req)
        frame = resp.df
        if frame is None or frame.empty:
            return {sym: pd.DataFrame() for sym in symbols}

        out: dict[str, pd.DataFrame] = {}
        for sym in symbols:
            try:
                sub = frame.xs(sym, level="symbol").copy()
            except KeyError:
                out[sym] = pd.DataFrame()
                continue
            sub.index = sub.index.tz_convert("UTC") if sub.index.tz else sub.index
            out[sym] = sub.tail(lookback_days)
        return out
