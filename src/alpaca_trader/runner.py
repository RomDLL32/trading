"""Single-tick entry point. Designed to be invoked once per scheduled run."""

from __future__ import annotations

import logging
import sys
from typing import Sequence

from .broker import AlpacaBroker
from .config import Settings
from .data import BarFetcher
from .portfolio import TargetOrder, build_orders
from .reporter import PortfolioReporter, format_report
from .strategy import SmaCrossoverStrategy, StrategyDecision

log = logging.getLogger("alpaca_trader")


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def run_tick(settings: Settings, *, dry_run: bool = False) -> list[TargetOrder]:
    """Run one trading tick. Returns the orders that were (or would be) submitted."""

    settings.require_credentials()

    broker = AlpacaBroker(settings.api_key, settings.api_secret, paper=settings.paper)
    snapshot = broker.snapshot()
    log.info("account equity=%.2f cash=%.2f market_open=%s",
             snapshot.equity, snapshot.cash, snapshot.is_market_open)

    if not snapshot.is_market_open:
        log.info("market closed; skipping tick")
        return []

    fetcher = BarFetcher(settings.api_key, settings.api_secret)
    strategy = SmaCrossoverStrategy(settings.sma_fast, settings.sma_slow)
    bars_by_symbol = fetcher.daily_bars(list(settings.universe), lookback_days=strategy.min_bars + 5)

    decisions: list[StrategyDecision] = []
    for symbol in settings.universe:
        bars = bars_by_symbol.get(symbol)
        if bars is None or len(bars) < strategy.min_bars:
            log.warning("insufficient bars for %s (have %s, need %s)",
                        symbol, 0 if bars is None else len(bars), strategy.min_bars)
            continue
        decision = strategy.decide(symbol, bars)
        log.info("decision %s signal=%s fast=%.2f slow=%.2f close=%.2f",
                 decision.symbol, decision.signal.value, decision.fast,
                 decision.slow, decision.last_close)
        decisions.append(decision)

    orders = build_orders(
        decisions=decisions,
        current_positions=broker.positions(),
        equity=snapshot.equity,
        target_weight=settings.target_weight,
        max_gross_exposure=settings.max_gross_exposure,
    )

    if dry_run:
        for o in orders:
            log.info("[dry-run] would submit %s %s %s (%s)", o.side, o.qty, o.symbol, o.reason)
        return orders

    for o in orders:
        broker.submit(o)
    return orders


def run_report(settings: Settings) -> None:
    settings.require_credentials()
    reporter = PortfolioReporter(settings.api_key, settings.api_secret, paper=settings.paper)
    report = reporter.snapshot()
    for line in format_report(report).splitlines():
        log.info("%s", line)


def main(argv: Sequence[str] | None = None) -> int:
    _configure_logging()
    args = list(sys.argv[1:] if argv is None else argv)
    dry_run = "--dry-run" in args

    try:
        settings = Settings.from_env()
        run_tick(settings, dry_run=dry_run)
        run_report(settings)
    except RuntimeError as exc:
        log.error("%s", exc)
        return 1
    except Exception:
        log.exception("tick failed")
        return 2
    return 0


def report_main(argv: Sequence[str] | None = None) -> int:
    _configure_logging()
    try:
        settings = Settings.from_env()
        run_report(settings)
    except RuntimeError as exc:
        log.error("%s", exc)
        return 1
    except Exception:
        log.exception("report failed")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
