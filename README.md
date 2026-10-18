# FutureQuantVexa

**Pattern-Based Signal Generator for Quotex/OTC M1 Trading**

## Strategy

- **Entry 1** → if lost → **MTG1** (same direction, 2× stake) → **STOP**
- No Entry 3 or Entry 4 — MTG1 is the **final recovery entry**
- Max loss per signal: **3× stake** (1 + 2)
- 18 Japanese candlestick patterns × 7 weekdays × 13 pairs = **142 elite combinations**
- Filter: ≥85% historical success (C1+C2) AND positive net profit

## Usage

```bash
# Single file
python futurequantvexa.py USDDZD_otc_1m_10d_xxx.json

# Multiple files
python futurequantvexa.py pair1.json pair2.json pair3.json

# All JSON files in a directory
python futurequantvexa.py *.json
```

## Input Format

JSON file with candle data (array or object with `candles` key):

```json
{
  "candles": [
    {"datetime": "2026-10-09 18:58:00", "time": 1791572280, "open": 0.19681, "high": 0.19688, "low": 0.19662, "close": 0.19679, "volume": 0},
    ...
  ]
}
```

## Output

- **Console table** with all signals sorted by datetime (mixed pairs, chronological order)
- **CSV file**: `futurequantvexa_signals.csv`

## Signal Fields

| Field | Description |
|-------|-------------|
| datetime | When the signal triggers (UTC) |
| pair | Currency pair (e.g. USDDZD) |
| pattern | Candlestick pattern name |
| direction | BUY or SELL |
| weekday | Day of week (Sun-Sat) |
| entry_candle | Entry 1 (first entry) or MTG1 (recovery) |
| stake | 1× for Entry 1, 2× for MTG1 |
| historical_c1 | Success rate on Entry 1 alone |
| historical_c1_c2 | Cumulative success rate (Entry 1 OR MTG1) |
| net_profit | Historical average net profit (× stake) |
| max_loss | 3× stake (if both entries lose) |

## Patterns (18 total)

Doji, Hammer, ShootingStar, Star, 3Soldiers, Harami, Piercing, Tweezer, Marubozu, InsideBar, PinBar, Engulfing, TrendCont, InsideBody, GapRev, Consec2, LongWick, BigBodyRev

## Elite Combinations (142 total)

Each combination is validated with:
- Train/Test split (70% train, 30% test) — chronological, no lookahead bias
- C1+C2 ≥ 85% historical success rate
- Positive net profit (with 80% payout)

## Disclaimer

Educational tool. Not financial advice. Trading involves risk.
