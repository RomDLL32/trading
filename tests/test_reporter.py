from datetime import datetime, timezone

from alpaca_trader.reporter import PortfolioReport, PositionRow, format_report


def _report(positions: list[PositionRow]) -> PortfolioReport:
    return PortfolioReport(
        timestamp=datetime(2026, 5, 19, 13, 35, tzinfo=timezone.utc),
        equity=101_234.56,
        last_equity=100_000.00,
        cash=5_000.00,
        buying_power=10_000.00,
        day_pl=1_234.56,
        day_pl_pct=1.23456,
        positions=positions,
        recent_order_count=5,
    )


def test_format_report_with_positions() -> None:
    out = format_report(_report([
        PositionRow("SPY", 24.0, 700.0, 738.0, 17712.0, 912.0, 5.43),
    ]))
    assert "Portfolio Report" in out
    assert "Day P/L:       $    1,234.56" in out
    assert "SPY" in out
    assert "Recent orders (24h): 5" in out


def test_format_report_no_positions() -> None:
    out = format_report(_report([]))
    assert "(none)" in out
