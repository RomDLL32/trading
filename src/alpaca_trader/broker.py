"""Account + order placement via alpaca-py's TradingClient."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from .portfolio import TargetOrder

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AccountSnapshot:
    equity: float
    cash: float
    buying_power: float
    is_market_open: bool


class AlpacaBroker:
    def __init__(self, api_key: str, api_secret: str, paper: bool = True) -> None:
        self._client = TradingClient(api_key, api_secret, paper=paper)

    def snapshot(self) -> AccountSnapshot:
        account = self._client.get_account()
        clock = self._client.get_clock()
        return AccountSnapshot(
            equity=float(account.equity),
            cash=float(account.cash),
            buying_power=float(account.buying_power),
            is_market_open=bool(clock.is_open),
        )

    def positions(self) -> dict[str, float]:
        return {p.symbol: float(p.qty) for p in self._client.get_all_positions()}

    def submit(self, order: TargetOrder) -> str | None:
        if order.qty <= 0:
            return None
        side = OrderSide.BUY if order.side == "buy" else OrderSide.SELL
        req = MarketOrderRequest(
            symbol=order.symbol,
            qty=order.qty,
            side=side,
            time_in_force=TimeInForce.DAY,
        )
        try:
            placed = self._client.submit_order(req)
        except Exception as exc:  # noqa: BLE001 - we want to log and continue
            log.error("order failed %s %s %s: %s", order.side, order.qty, order.symbol, exc)
            return None
        log.info("order placed %s %s %s id=%s reason=%s",
                 order.side, order.qty, order.symbol, placed.id, order.reason)
        return str(placed.id)
