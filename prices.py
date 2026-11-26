"""Step 5: did the share price move after each signal?

For every signal, records the closing price on the day it was detected and the
return 1, 5 and 20 trading days later, alongside the FTSE AIM All-Share for
comparison. Writes data/backtest.csv and data/backtest.json.

    python prices.py
"""
import json
from pathlib import Path

import pandas as pd
import yfinance as yf

DATA = Path(__file__).resolve().parent / "data"
BENCHMARK = "^FTAI"  # FTSE AIM All-Share; swap for "^FTSE" if you prefer
HORIZONS = [1, 5, 20]


def closes(symbol, start):
    df = yf.download(symbol, start=start, progress=False, auto_adjust=True)
    if df.empty:
        return pd.Series(dtype=float)
    s = df["Close"]
    return s.iloc[:, 0] if isinstance(s, pd.DataFrame) else s


def forward_returns(series, day):
    """Returns from the first close on/after `day` to N trading days later."""
    after = series[series.index >= day]
    if after.empty:
        return None, {}
    base = after.iloc[0]
    out = {}
    for n in HORIZONS:
        out[f"ret_{n}d"] = round(float(after.iloc[n] / base - 1) * 100, 2) if len(after) > n else None
    return float(base), out


def main():
    signals = json.loads((DATA / "signals.json").read_text()) if (DATA / "signals.json").exists() else []
    signals = [s for s in signals if s["severity"] in {"high", "medium"}]
    if not signals:
        print("No medium/high signals yet.")
        return
    start = min(s["detected_at"][:10] for s in signals)
    bench = closes(BENCHMARK, start)
    cache = {}
    rows = []
    for s in signals:
        sym = s["ticker"] + ".L"
        if sym not in cache:
            cache[sym] = closes(sym, start)
        day = pd.Timestamp(s["detected_at"][:10])
        price, rets = forward_returns(cache[sym], day)
        _, brets = forward_returns(bench, day) if not bench.empty else (None, {})
        row = {k: s[k] for k in ("detected_at", "ticker", "nct_id", "note", "severity")}
        row["price_at_signal"] = price
        for n in HORIZONS:
            r, b = rets.get(f"ret_{n}d"), brets.get(f"ret_{n}d")
            row[f"ret_{n}d"] = r
            row[f"vs_index_{n}d"] = round(r - b, 2) if r is not None and b is not None else None
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(DATA / "backtest.csv", index=False)
    (DATA / "backtest.json").write_text(df.to_json(orient="records", indent=1))
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
