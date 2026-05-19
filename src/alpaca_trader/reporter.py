"""Account / portfolio reporting. Read-only — never submits orders."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PositionRow:
    symbol: str
    qty: float
    avg_entry: float
    market_price: float
    market_value: float
    unrealized_pl: float
    unrealized_plpc: float


@dataclass(frozen=True)
class PortfolioReport:
    timestamp: datetime
    equity: float
    last_equity: float
    cash: float
    buying_power: float
    day_pl: float
    day_pl_pct: float
    positions: list[PositionRow]
    recent_order_count: int


class PortfolioReporter:
    def __init__(self, api_key: str, api_secret: str, paper: bool = True) -> None:
        self._client = TradingClient(api_key, api_secret, paper=paper)

    def snapshot(self, recent_order_window_hours: int = 24) -> PortfolioReport:
        account = self._client.get_account()
        positions = self._client.get_all_positions()

        equity = float(account.equity)
        last_equity = float(account.last_equity) if account.last_equity else equity
        day_pl = equity - last_equity
        day_pl_pct = (day_pl / last_equity * 100.0) if last_equity else 0.0

        rows = [
            PositionRow(
                symbol=p.symbol,
                qty=float(p.qty),
                avg_entry=float(p.avg_entry_price),
                market_price=float(p.current_price) if p.current_price else 0.0,
                market_value=float(p.market_value),
                unrealized_pl=float(p.unrealized_pl) if p.unrealized_pl else 0.0,
                unrealized_plpc=float(p.unrealized_plpc) * 100.0 if p.unrealized_plpc else 0.0,
            )
            for p in positions
        ]

        since = datetime.now(tz=timezone.utc) - timedelta(hours=recent_order_window_hours)
        recent_orders = self._client.get_orders(
            GetOrdersRequest(status=QueryOrderStatus.ALL, after=since, limit=500)
        )

        return PortfolioReport(
            timestamp=datetime.now(tz=timezone.utc),
            equity=equity,
            last_equity=last_equity,
            cash=float(account.cash),
            buying_power=float(account.buying_power),
            day_pl=day_pl,
            day_pl_pct=day_pl_pct,
            positions=rows,
            recent_order_count=len(recent_orders),
        )


def format_report(r: PortfolioReport) -> str:
    lines = [
        f"=== Portfolio Report @ {r.timestamp.isoformat(timespec='seconds')} ===",
        f"Equity:        ${r.equity:>12,.2f}",
        f"Last equity:   ${r.last_equity:>12,.2f}",
        f"Day P/L:       ${r.day_pl:>12,.2f} ({r.day_pl_pct:+.2f}%)",
        f"Cash:          ${r.cash:>12,.2f}",
        f"Buying power:  ${r.buying_power:>12,.2f}",
        f"Recent orders (24h): {r.recent_order_count}",
        "",
        "Positions:",
    ]
    if not r.positions:
        lines.append("  (none)")
    else:
        lines.append(
            f"  {'SYMBOL':<8}{'QTY':>10}{'ENTRY':>12}{'PRICE':>12}{'MV':>14}{'UPNL':>12}{'UPNL%':>9}"
        )
        for p in r.positions:
            lines.append(
                f"  {p.symbol:<8}{p.qty:>10.4f}{p.avg_entry:>12.2f}"
                f"{p.market_price:>12.2f}{p.market_value:>14,.2f}"
                f"{p.unrealized_pl:>12,.2f}{p.unrealized_plpc:>8.2f}%"
            )
    return "\n".join(lines)
