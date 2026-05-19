"""Granular trading CLI. Each subcommand is one read or one write — Claude (or
a human) composes them inside a routine to make decisions.

Safety rails:
- Refuses to run against a non-paper base URL.
- Refuses single orders that exceed MAX_ORDER_PCT of current equity.
- Refuses buys that would push gross long exposure above MAX_GROSS_PCT.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Sequence

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest

from .config import PAPER_ENDPOINT, Settings
from .reporter import PortfolioReporter, format_report
from .strategy import SmaCrossoverStrategy
from .data import BarFetcher

log = logging.getLogger("alpaca_trader.cli")

# Hard safety caps — independent of strategy config.
MAX_ORDER_PCT = 0.25      # no single order > 25% of equity
MAX_GROSS_PCT = 0.95      # total long exposure cap
DAILY_BAR_LIMIT = 200     # never return more bars than this in one call


def _emit(payload: object) -> None:
    print(json.dumps(payload, default=str, indent=2))


def _trading(settings: Settings) -> TradingClient:
    if settings.base_url != PAPER_ENDPOINT:
        raise SystemExit(f"refusing to run against non-paper endpoint: {settings.base_url}")
    return TradingClient(settings.api_key, settings.api_secret, paper=True)


# ---------------- read-only commands ----------------

def cmd_account(settings: Settings, _args: argparse.Namespace) -> int:
    client = _trading(settings)
    acct = client.get_account()
    clock = client.get_clock()
    _emit({
        "equity": float(acct.equity),
        "last_equity": float(acct.last_equity) if acct.last_equity else None,
        "cash": float(acct.cash),
        "buying_power": float(acct.buying_power),
        "long_market_value": float(acct.long_market_value or 0),
        "pattern_day_trader": bool(acct.pattern_day_trader),
        "market_open": bool(clock.is_open),
        "next_open": clock.next_open.isoformat() if clock.next_open else None,
        "next_close": clock.next_close.isoformat() if clock.next_close else None,
    })
    return 0


def cmd_positions(settings: Settings, _args: argparse.Namespace) -> int:
    client = _trading(settings)
    positions = client.get_all_positions()
    _emit([
        {
            "symbol": p.symbol,
            "qty": float(p.qty),
            "avg_entry": float(p.avg_entry_price),
            "market_price": float(p.current_price) if p.current_price else None,
            "market_value": float(p.market_value),
            "unrealized_pl": float(p.unrealized_pl) if p.unrealized_pl else 0.0,
            "unrealized_plpc_pct": (float(p.unrealized_plpc) * 100.0) if p.unrealized_plpc else 0.0,
        }
        for p in positions
    ])
    return 0


def cmd_orders(settings: Settings, args: argparse.Namespace) -> int:
    client = _trading(settings)
    since = datetime.now(tz=timezone.utc) - timedelta(hours=args.hours)
    orders = client.get_orders(GetOrdersRequest(
        status=QueryOrderStatus.ALL, after=since, limit=200,
    ))
    _emit([
        {
            "id": str(o.id),
            "symbol": o.symbol,
            "side": o.side.value,
            "qty": float(o.qty) if o.qty else None,
            "filled_qty": float(o.filled_qty) if o.filled_qty else 0.0,
            "filled_avg_price": float(o.filled_avg_price) if o.filled_avg_price else None,
            "status": o.status.value,
            "submitted_at": o.submitted_at.isoformat() if o.submitted_at else None,
        }
        for o in orders
    ])
    return 0


def cmd_bars(settings: Settings, args: argparse.Namespace) -> int:
    days = min(args.days, DAILY_BAR_LIMIT)
    client = StockHistoricalDataClient(settings.api_key, settings.api_secret)
    end = datetime.now(tz=timezone.utc) - timedelta(minutes=20)
    start = end - timedelta(days=days * 2 + 14)
    req = StockBarsRequest(
        symbol_or_symbols=[args.symbol.upper()],
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        feed="iex",
    )
    resp = client.get_stock_bars(req)
    frame = resp.df
    if frame is None or frame.empty:
        _emit({"symbol": args.symbol.upper(), "bars": []})
        return 0
    sub = frame.xs(args.symbol.upper(), level="symbol").tail(days)
    _emit({
        "symbol": args.symbol.upper(),
        "bars": [
            {
                "timestamp": ts.isoformat(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
            for ts, row in sub.iterrows()
        ],
    })
    return 0


def cmd_signals(settings: Settings, _args: argparse.Namespace) -> int:
    """Show the baseline SMA-crossover view as advisory input."""
    strategy = SmaCrossoverStrategy(settings.sma_fast, settings.sma_slow)
    fetcher = BarFetcher(settings.api_key, settings.api_secret)
    bars = fetcher.daily_bars(list(settings.universe), lookback_days=strategy.min_bars + 5)
    rows = []
    for symbol in settings.universe:
        b = bars.get(symbol)
        if b is None or len(b) < strategy.min_bars:
            rows.append({"symbol": symbol, "signal": "insufficient_data"})
            continue
        d = strategy.decide(symbol, b)
        rows.append({
            "symbol": d.symbol,
            "signal": d.signal.value,
            "fast_sma": d.fast,
            "slow_sma": d.slow,
            "last_close": d.last_close,
        })
    _emit({
        "fast": settings.sma_fast,
        "slow": settings.sma_slow,
        "universe": list(settings.universe),
        "rows": rows,
    })
    return 0


def cmd_report(settings: Settings, _args: argparse.Namespace) -> int:
    reporter = PortfolioReporter(settings.api_key, settings.api_secret, paper=settings.paper)
    print(format_report(reporter.snapshot()))
    return 0


# ---------------- write commands ----------------

def _check_order_limits(client: TradingClient, symbol: str, side: str, qty: float) -> None:
    if qty <= 0:
        raise SystemExit("qty must be > 0")
    acct = client.get_account()
    equity = float(acct.equity)
    if equity <= 0:
        raise SystemExit("account has no equity")

    # Fetch a quick last-trade-ish price from the latest bar.
    data_client = StockHistoricalDataClient(client._api_key, client._secret_key)  # noqa: SLF001
    end = datetime.now(tz=timezone.utc) - timedelta(minutes=20)
    start = end - timedelta(days=7)
    bars = data_client.get_stock_bars(StockBarsRequest(
        symbol_or_symbols=[symbol],
        timeframe=TimeFrame.Day,
        start=start, end=end, feed="iex",
    )).df
    if bars is None or bars.empty:
        raise SystemExit(f"cannot estimate price for {symbol} — aborting")
    last_close = float(bars.xs(symbol, level="symbol")["close"].iloc[-1])
    notional = qty * last_close
    pct = notional / equity
    if pct > MAX_ORDER_PCT:
        raise SystemExit(
            f"order rejected: {notional:.0f} ({pct*100:.1f}% of equity) > MAX_ORDER_PCT "
            f"({MAX_ORDER_PCT*100:.0f}%)"
        )

    if side == "buy":
        long_mv = float(acct.long_market_value or 0)
        projected_gross = (long_mv + notional) / equity
        if projected_gross > MAX_GROSS_PCT:
            raise SystemExit(
                f"order rejected: projected gross long exposure "
                f"{projected_gross*100:.1f}% > MAX_GROSS_PCT ({MAX_GROSS_PCT*100:.0f}%)"
            )


def _submit(settings: Settings, symbol: str, side: str, qty: float, dry_run: bool) -> int:
    client = _trading(settings)
    symbol = symbol.upper()
    _check_order_limits(client, symbol, side, qty)
    if dry_run:
        _emit({"dry_run": True, "side": side, "symbol": symbol, "qty": qty})
        return 0
    req = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    )
    placed = client.submit_order(req)
    _emit({
        "id": str(placed.id),
        "symbol": placed.symbol,
        "side": placed.side.value,
        "qty": float(placed.qty) if placed.qty else None,
        "status": placed.status.value,
    })
    return 0


def cmd_buy(settings: Settings, args: argparse.Namespace) -> int:
    return _submit(settings, args.symbol, "buy", args.qty, args.dry_run)


def cmd_sell(settings: Settings, args: argparse.Namespace) -> int:
    return _submit(settings, args.symbol, "sell", args.qty, args.dry_run)


def cmd_cancel(settings: Settings, args: argparse.Namespace) -> int:
    client = _trading(settings)
    client.cancel_order_by_id(args.order_id)
    _emit({"cancelled": args.order_id})
    return 0


def cmd_close(settings: Settings, args: argparse.Namespace) -> int:
    """Liquidate a single position at market."""
    client = _trading(settings)
    try:
        pos = client.get_open_position(args.symbol.upper())
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"no open position for {args.symbol.upper()}: {exc}")
    qty = abs(float(pos.qty))
    if qty == 0:
        _emit({"noop": True, "symbol": args.symbol.upper()})
        return 0
    return _submit(settings, args.symbol, "sell", qty, args.dry_run)


# ---------------- parser ----------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="alpaca", description="Paper-trading CLI.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("account", help="Account state + market clock").set_defaults(fn=cmd_account)
    sub.add_parser("positions", help="Current open positions").set_defaults(fn=cmd_positions)
    sub.add_parser("signals", help="Advisory SMA-crossover view").set_defaults(fn=cmd_signals)
    sub.add_parser("report", help="Human-readable portfolio report").set_defaults(fn=cmd_report)

    p_orders = sub.add_parser("orders", help="Recent orders")
    p_orders.add_argument("--hours", type=int, default=48)
    p_orders.set_defaults(fn=cmd_orders)

    p_bars = sub.add_parser("bars", help="Daily bars for a symbol")
    p_bars.add_argument("symbol")
    p_bars.add_argument("--days", type=int, default=60)
    p_bars.set_defaults(fn=cmd_bars)

    p_buy = sub.add_parser("buy", help="Market buy (paper, with safety caps)")
    p_buy.add_argument("symbol")
    p_buy.add_argument("qty", type=float)
    p_buy.add_argument("--dry-run", action="store_true")
    p_buy.set_defaults(fn=cmd_buy)

    p_sell = sub.add_parser("sell", help="Market sell")
    p_sell.add_argument("symbol")
    p_sell.add_argument("qty", type=float)
    p_sell.add_argument("--dry-run", action="store_true")
    p_sell.set_defaults(fn=cmd_sell)

    p_cancel = sub.add_parser("cancel", help="Cancel an open order by id")
    p_cancel.add_argument("order_id")
    p_cancel.set_defaults(fn=cmd_cancel)

    p_close = sub.add_parser("close", help="Liquidate one position at market")
    p_close.add_argument("symbol")
    p_close.add_argument("--dry-run", action="store_true")
    p_close.set_defaults(fn=cmd_close)

    return p


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    parser = _build_parser()
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    settings.require_credentials()
    return args.fn(settings, args)


if __name__ == "__main__":
    raise SystemExit(main())
