from alpaca_trader.portfolio import build_orders
from alpaca_trader.strategy import Signal, StrategyDecision


def _decision(sym: str, signal: Signal, close: float = 100.0) -> StrategyDecision:
    return StrategyDecision(symbol=sym, signal=signal, fast=1.0, slow=1.0, last_close=close)


def test_opens_longs_for_each_long_signal() -> None:
    decisions = [_decision("AAA", Signal.LONG), _decision("BBB", Signal.LONG)]
    orders = build_orders(
        decisions=decisions,
        current_positions={},
        equity=100_000.0,
        target_weight=0.2,
        max_gross_exposure=0.95,
    )
    assert {o.symbol for o in orders} == {"AAA", "BBB"}
    assert all(o.side == "buy" for o in orders)
    # 20% of 100k = 20k notional at $100 = 200 shares.
    assert all(o.qty == 200.0 for o in orders)


def test_closes_position_when_signal_flips_flat() -> None:
    orders = build_orders(
        decisions=[_decision("AAA", Signal.FLAT)],
        current_positions={"AAA": 50.0},
        equity=100_000.0,
        target_weight=0.2,
        max_gross_exposure=0.95,
    )
    assert orders == [orders[0]]
    assert orders[0].side == "sell"
    assert orders[0].qty == 50.0


def test_clamps_gross_exposure() -> None:
    decisions = [_decision(s, Signal.LONG) for s in ("A", "B", "C", "D", "E", "F")]
    orders = build_orders(
        decisions=decisions,
        current_positions={},
        equity=100_000.0,
        target_weight=0.20,  # 6 * 0.20 = 1.20, must be clamped to 0.95
        max_gross_exposure=0.95,
    )
    total_notional = sum(o.qty * 100.0 for o in orders)
    assert total_notional <= 100_000.0 * 0.95 + 1e-6


def test_skips_tiny_rebalances() -> None:
    # Current ~= target -> no churn order.
    orders = build_orders(
        decisions=[_decision("AAA", Signal.LONG, close=100.0)],
        current_positions={"AAA": 199.0},  # target is 200
        equity=100_000.0,
        target_weight=0.20,
        max_gross_exposure=0.95,
    )
    assert orders == []


def test_zero_equity_emits_nothing() -> None:
    orders = build_orders(
        decisions=[_decision("AAA", Signal.LONG)],
        current_positions={},
        equity=0.0,
        target_weight=0.2,
        max_gross_exposure=0.95,
    )
    assert orders == []
