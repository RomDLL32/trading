from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from alpaca_trader import cli


def test_parser_rejects_unknown_command() -> None:
    parser = cli._build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["mooch", "SPY"])


def test_parser_buy_parses() -> None:
    parser = cli._build_parser()
    args = parser.parse_args(["buy", "SPY", "10", "--dry-run"])
    assert args.cmd == "buy"
    assert args.symbol == "SPY"
    assert args.qty == 10.0
    assert args.dry_run is True


def _make_client(equity: float, long_mv: float) -> MagicMock:
    client = MagicMock()
    client._api_key = "k"
    client._secret_key = "s"
    acct = MagicMock()
    acct.equity = str(equity)
    acct.long_market_value = str(long_mv)
    client.get_account.return_value = acct
    return client


def _patch_price(price: float):
    df = pd.DataFrame(
        {"close": [price]},
        index=pd.MultiIndex.from_tuples([("XYZ", pd.Timestamp.utcnow())], names=["symbol", "timestamp"]),
    )
    stub = MagicMock()
    stub.get_stock_bars.return_value = MagicMock(df=df)
    return patch("alpaca_trader.cli.StockHistoricalDataClient", return_value=stub)


def test_check_order_limits_rejects_oversized_order() -> None:
    client = _make_client(equity=100_000, long_mv=0)
    # 1000 shares * $100 = $100k = 100% of equity, way over MAX_ORDER_PCT (25%).
    with _patch_price(100.0), pytest.raises(SystemExit, match="MAX_ORDER_PCT"):
        cli._check_order_limits(client, "XYZ", "buy", qty=1000.0)


def test_check_order_limits_rejects_overexposed_buy() -> None:
    client = _make_client(equity=100_000, long_mv=90_000)
    # 100 shares * $100 = $10k. Combined with $90k existing = 100% gross, > 95%.
    with _patch_price(100.0), pytest.raises(SystemExit, match="MAX_GROSS_PCT"):
        cli._check_order_limits(client, "XYZ", "buy", qty=100.0)


def test_check_order_limits_allows_reasonable_buy() -> None:
    client = _make_client(equity=100_000, long_mv=20_000)
    # 100 shares * $100 = $10k = 10% of equity, gross would be 30%. OK.
    with _patch_price(100.0):
        cli._check_order_limits(client, "XYZ", "buy", qty=100.0)


def test_check_order_limits_rejects_zero_qty() -> None:
    client = _make_client(equity=100_000, long_mv=0)
    with pytest.raises(SystemExit, match="qty must be > 0"):
        cli._check_order_limits(client, "XYZ", "buy", qty=0.0)
