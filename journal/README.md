# Decision Journal

One JSONL line per scheduled trading session, appended to `decisions.jsonl`.
The routine reads the tail of this file at startup so today's session knows
what prior sessions decided and why.

## Schema

```json
{
  "timestamp": "2026-05-19T13:35:00Z",
  "session_id": "abc-123",
  "market_open": true,
  "account": {
    "equity_start": 100000.00,
    "equity_end":   100080.32,
    "day_pl":           80.32,
    "day_pl_pct":        0.08,
    "cash":           9991.76
  },
  "positions_after": [
    {"symbol": "AAPL", "qty": 60.43, "market_value": 18100.32}
  ],
  "decisions": [
    {
      "symbol": "NVDA",
      "action": "buy",            // buy | sell | trim | close | hold | skip
      "qty": 80.95,
      "reasoning": "20d return +18%, RSI 62 (room), 4% above SMA-50, vol regime rising. Initiating 18% target weight.",
      "research_cited": {"rsi_14": 62.1, "return_20d_pct": 18.2, "pct_above_sma50": 4.1}
    }
  ],
  "summary": "Opened full basket on initial run; all 5 names long-trending."
}
```

## Conventions

- Append-only. Never edit historical entries.
- One line per session, no pretty-printing.
- Commit the journal as part of each routine run.

---

## Weekly Review log — `reviews.jsonl`

Written by the weekly-review routine. Grades the past week of decisions
against subsequent price action and flags patterns to adjust.

```json
{
  "timestamp": "2026-05-25T20:00:00Z",
  "review_window": {"from": "2026-05-19", "to": "2026-05-23"},
  "sessions_reviewed": 5,
  "graded_decisions": [
    {
      "from_session": "2026-05-19",
      "symbol": "NVDA",
      "action": "buy",
      "entry_price": 222.35,
      "current_price": 231.40,
      "pnl_pct_since": 4.07,
      "grade": "good",                  // good | mixed | bad | too_early
      "thesis_held": true,
      "comment": "Trend thesis intact, RSI normalized to 58. Hold."
    }
  ],
  "patterns": [
    "Consistently bought into RSI > 80 — got lucky once, burned twice. Tighten RSI ceiling.",
    "Trims around 52w-high too early — see AAPL and MSFT both ran another 3% after trim."
  ],
  "suggested_adjustments": [
    "Avoid new longs when RSI > 75 unless price is < 2% above 50-SMA.",
    "Hold trims until pct_from_52w_high > 0 AND RSI < 70."
  ],
  "benchmarks": {
    "portfolio_pct": 1.2,
    "spy_pct": 0.9,       // S&P 500
    "vt_pct": 0.7,        // total world (developed + emerging)
    "sso_pct": 1.75,      // 2x daily-reset S&P 500 (path-dependent)
    "best_passive": "sso",
    "alpha_vs_spy_pct": 0.3
  },
  "summary": "Week +1.2%; SPY +0.9%, VT +0.7%, SSO +1.75%. Decisions mostly aligned with momentum; one bad rotation out of QQQ."
}
```

Read with `alpaca journal-tail --path journal/reviews.jsonl -n 4`.
Append with `alpaca journal-append --path journal/reviews.jsonl --entry '<json>'`.
