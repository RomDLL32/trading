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
