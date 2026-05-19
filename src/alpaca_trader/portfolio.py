"""Translate strategy decisions + current positions into target orders."""

from __future__ import annotations

from dataclasses import dataclass

from .strategy import Signal, StrategyDecision


@dataclass(frozen=True)
class TargetOrder:
    symbol: str
    side: str  # "buy" or "sell"
    qty: float
    reason: str


def build_orders(
    decisions: list[StrategyDecision],
    current_positions: dict[str, float],
    equity: float,
    target_weight: float,
    max_gross_exposure: float,
) -> list[TargetOrder]:
    """Produce the minimal set of orders to move toward target weights.

    - LONG decision: hold approximately ``target_weight`` of equity in the name.
    - FLAT decision: hold zero.
    - We clamp the total long weight allocated this tick to ``max_gross_exposure``.
    """

    if equity <= 0:
        return []

    longs = [d for d in decisions if d.signal == Signal.LONG]
    cap = max(0.0, max_gross_exposure)
    per_name = target_weight
    if longs and per_name * len(longs) > cap:
        per_name = cap / len(longs)

    orders: list[TargetOrder] = []
    long_symbols = {d.symbol for d in longs}

    # Close any current position whose decision is FLAT or absent from the universe.
    for symbol, qty in current_positions.items():
        if qty == 0:
            continue
        if symbol not in long_symbols:
            orders.append(
                TargetOrder(
                    symbol=symbol,
                    side="sell",
                    qty=abs(qty),
                    reason="exit_flat_signal",
                )
            )

    # Open / resize longs.
    for d in longs:
        target_notional = equity * per_name
        target_qty = target_notional / d.last_close if d.last_close > 0 else 0.0
        current_qty = current_positions.get(d.symbol, 0.0)
        delta = target_qty - current_qty

        # Skip if within 5% of target to avoid churn from rounding noise.
        if current_qty > 0 and abs(delta) / max(target_qty, 1e-9) < 0.05:
            continue

        if delta > 0:
            orders.append(
                TargetOrder(
                    symbol=d.symbol,
                    side="buy",
                    qty=round(delta, 4),
                    reason="enter_or_resize_long",
                )
            )
        elif delta < 0:
            orders.append(
                TargetOrder(
                    symbol=d.symbol,
                    side="sell",
                    qty=round(-delta, 4),
                    reason="trim_long",
                )
            )

    return orders
