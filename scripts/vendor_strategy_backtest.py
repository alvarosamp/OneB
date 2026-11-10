"""Causal walk-forward tests for the purchased indicator rule families.

These are documented reproductions, not decompilations of the closed EX5 files.
Signals are computed on completed bars and filled at the next bar open.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from intraday_setup_research import _adx, _true_range, load_intraday_csv, resample_bars
from scipy import stats

NY = "America/New_York"


@dataclass(frozen=True)
class CostSpec:
    point_value: float
    round_trip_cost: float


COSTS = {"NQ": CostSpec(20.0, 15.0), "XAUUSD": CostSpec(1.0, 0.28)}


def features(bars: pd.DataFrame) -> pd.DataFrame:
    f = bars.copy()
    f["atr"] = _true_range(f).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    for n in (5, 10, 13, 60, 100):
        f[f"ema{n}"] = f.close.ewm(span=n, adjust=False, min_periods=n).mean()
        f[f"sma{n}"] = f.close.rolling(n, min_periods=n).mean()
    d = f.close.diff()
    gain = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    loss = -d.clip(upper=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    f["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    f = f.join(_adx(f.high, f.low, f.close, 14))
    f["bb_mid"] = f.close.rolling(20).mean()
    sd = f.close.rolling(20).std()
    f["bb_up"] = f.bb_mid + 2 * sd
    f["bb_dn"] = f.bb_mid - 2 * sd
    local = f.index.tz_convert(NY)
    f["date"] = local.date
    f["hour"] = local.hour + local.minute / 60
    return f


def completed_mtf_side(bars: pd.DataFrame, rule: str) -> pd.Series:
    close = bars.close.resample(rule, closed="left", label="right").last().dropna()
    side = np.sign(close - close.rolling(60, min_periods=60).mean())
    return side.reindex(bars.index, method="ffill")


def crossed_recent(a: pd.Series, b: pd.Series, direction: int, window: int) -> pd.Series:
    event = (a > b) & (a.shift(1) <= b.shift(1)) if direction == 1 else (a < b) & (a.shift(1) >= b.shift(1))
    return event.rolling(window + 1, min_periods=1).max().astype(bool)


def signal_gold_fakeout(f: pd.DataFrame, p: dict) -> pd.Series:
    ema = f.ema100
    long = (f.low <= ema + p["touch_atr"] * f.atr) & (f.close > ema) & (f.close.shift(1) > ema.shift(1))
    short = (f.high >= ema - p["touch_atr"] * f.atr) & (f.close < ema) & (f.close.shift(1) < ema.shift(1))
    # Bollinger must agree with the side of the EMA; exact proprietary direction is unknown.
    long &= f.close >= f.bb_mid
    short &= f.close <= f.bb_mid
    if p["window"] == "video":
        long &= f.hour.between(6, 10.5)  # 07:00-11:30 Sao Paulo approximated in NY (UTC-4 assumption)
        short &= f.hour.between(6, 10.5)
        friday_cut = (pd.DatetimeIndex(f.index).tz_convert(NY).weekday == 4) & (f.hour > 9)
        long &= ~friday_cut
        short &= ~friday_cut
    return long.astype(int) - short.astype(int)


def signal_13x(f: pd.DataFrame, p: dict) -> pd.Series:
    plus, minus = f.plus_di, f.minus_di
    long = (plus > minus) & (plus.shift(1) <= minus.shift(1)) & (f.close > f.ema13) & (f.adx >= p["adx"])
    short = (minus > plus) & (minus.shift(1) <= plus.shift(1)) & (f.close < f.ema13) & (f.adx >= p["adx"])
    return long.astype(int) - short.astype(int)


def signal_100_pips(f: pd.DataFrame, p: dict) -> pd.Series:
    fast, slow = f[p["ma"] + "5"], f[p["ma"] + "10"]
    rsi50 = pd.Series(50.0, index=f.index)
    long = crossed_recent(fast, slow, 1, p["sync"]) & crossed_recent(f.rsi, rsi50, 1, p["sync"])
    short = crossed_recent(fast, slow, -1, p["sync"]) & crossed_recent(f.rsi, rsi50, -1, p["sync"])
    separation = (fast - slow).abs() / f.atr.replace(0, np.nan)
    long &= (f.adx >= p["adx"]) & (separation >= p["separation"])
    short &= (f.adx >= p["adx"]) & (separation >= p["separation"])
    return long.astype(int) - short.astype(int)


def signal_duck(f: pd.DataFrame, p: dict) -> pd.Series:
    h1 = completed_mtf_side(f, "60min")
    h4 = completed_mtf_side(f, "240min")
    m5_up = (f.close > f.sma60) & (f.close.shift(1) <= f.sma60.shift(1))
    m5_dn = (f.close < f.sma60) & (f.close.shift(1) >= f.sma60.shift(1))
    return (m5_up & (h1 > 0) & (h4 > 0)).astype(int) - (m5_dn & (h1 < 0) & (h4 < 0)).astype(int)


def signal_london_box(f: pd.DataFrame, p: dict) -> pd.Series:
    end, hours = p["end_hour_ny"], p["box_hours"]
    inside = f.hour.between(end - hours, end, inclusive="left")
    hi = f.high.where(inside).groupby(f.date).transform("max")
    lo = f.low.where(inside).groupby(f.date).transform("min")
    active = f.hour.between(end, end + 4, inclusive="left")
    buffer = p["buffer_atr"] * f.atr
    long = active & (f.close > hi + buffer) & (f.close.shift(1) <= hi.shift(1) + buffer.shift(1))
    short = active & (f.close < lo - buffer) & (f.close.shift(1) >= lo.shift(1) - buffer.shift(1))
    return long.astype(int) - short.astype(int)


def signal_gap_drive(f: pd.DataFrame, p: dict) -> pd.Series:
    # OHLC proxy only: exact EX5 uses a hidden bid/ask bias calculation.
    target = p["hour_ny"]
    first = f.hour.between(target, target + 0.11, inclusive="left")
    direction = np.sign(f.close - f.open) if p["direction"] == "first_bar" else np.sign(f.open - f.close.shift(1))
    one = first & ~first.groupby(f.date).shift(1).fillna(False)
    return direction.where(one, 0).fillna(0).astype(int)


def simulate(f: pd.DataFrame, signal: pd.Series, cost: CostSpec, p: dict, allowed: set | None = None) -> list[dict]:
    bar_minutes = int(f.index.to_series().diff().dt.total_seconds().div(60).median())
    max_bars = max(1, int(p["hold_minutes"] / bar_minutes))
    values = signal.fillna(0).to_numpy()
    dates = f.date.to_numpy()
    out, next_pos = [], 0
    for i in np.flatnonzero(values != 0):
        if i < next_pos or i + 1 >= len(f) or (allowed is not None and dates[i] not in allowed) or dates[i + 1] != dates[i]:
            continue
        side, entry_pos = int(values[i]), i + 1
        entry = float(f.open.iloc[entry_pos])
        if p.get("fixed_stop") is not None:
            risk = float(p["fixed_stop"])
            reward = float(p["fixed_target"])
        else:
            risk = float(f.atr.iloc[i]) * p["stop_atr"]
            reward = risk * p["reward_r"]
        if not np.isfinite(risk) or risk <= 0:
            continue
        stop, target = entry - side * risk, entry + side * reward
        exit_pos, exit_price, reason = entry_pos, entry, "time"
        for j in range(entry_pos, min(len(f), entry_pos + max_bars)):
            if dates[j] != dates[i]:
                break
            exit_pos, exit_price = j, float(f.close.iloc[j])
            stop_hit = f.low.iloc[j] <= stop if side == 1 else f.high.iloc[j] >= stop
            target_hit = f.high.iloc[j] >= target if side == 1 else f.low.iloc[j] <= target
            if stop_hit:
                exit_price, reason = stop, "stop"
                break
            if target_hit:
                exit_price, reason = target, "target"
                break
        pnl = side * (exit_price - entry) * cost.point_value - cost.round_trip_cost
        out.append({"decision_time": f.index[i].isoformat(), "date": str(dates[i]), "side": side, "entry": entry,
                    "exit": exit_price, "reason": reason, "net_pnl": pnl, "net_r": pnl / (risk * cost.point_value)})
        next_pos = exit_pos + 1
    return out


def metrics(trades: list[dict]) -> dict:
    if not trades:
        return {"trades": 0, "net_pnl": 0.0, "expectancy": None, "profit_factor": None, "win_rate": None, "sharpe": None, "max_drawdown": 0.0, "p_value": None}
    d = pd.DataFrame(trades)
    pnl = d.net_pnl
    daily = d.groupby("date").net_pnl.sum()
    equity = daily.cumsum()
    losses = -pnl[pnl < 0].sum()
    sd = daily.std(ddof=1)
    test = stats.ttest_1samp(pnl, 0, alternative="greater") if len(pnl) > 2 and pnl.std(ddof=1) > 0 else None
    return {"trades": len(d), "net_pnl": round(pnl.sum(), 2), "expectancy": round(pnl.mean(), 3),
            "profit_factor": round(pnl[pnl > 0].sum() / losses, 3) if losses else None,
            "win_rate": round((pnl > 0).mean(), 4), "sharpe": round(daily.mean() / sd * math.sqrt(252), 3) if sd > 0 else None,
            "max_drawdown": round((equity - equity.cummax()).min(), 2),
            "p_value": float(test.pvalue) if test is not None else None}


def grids() -> dict[str, tuple[str, Callable, list[dict]]]:
    # Compact neighbourhoods limit both runtime and data-mined winners.
    risk = [{"stop_atr": s, "reward_r": r, "hold_minutes": h} for s in (.75, 1.0) for r in (1.5, 2.0) for h in (120, 240)]
    return {
        "gold_fakeout": ("XAUUSD", signal_gold_fakeout,
            [{"touch_atr": t, "window": w, "fixed_stop": 2.0, "fixed_target": 1.5, "hold_minutes": 240}
             for t in (0, .05, .1) for w in ("crazy_24_7", "video")]),
        "13x": ("NQ", signal_13x, [{**q, "adx": a} for q in risk for a in (20, 25)]),
        "100_pips": ("NQ", signal_100_pips,
            [{**q, "ma": ma, "sync": sync, "adx": a, "separation": sep} for q in risk for ma in ("ema", "sma") for sync in (0, 2) for a in (20, 25) for sep in (0, .1)]),
        "duck": ("NQ", signal_duck, risk),
        "london_box": ("XAUUSD", signal_london_box,
            [{**q, "end_hour_ny": e, "box_hours": bh, "buffer_atr": b} for q in risk for e in (3, 4) for bh in (2, 3, 4) for b in (0, .1)]),
        "nasdaq_gap_drive_proxy": ("NQ", signal_gap_drive,
            [{**q, "hour_ny": h, "direction": d} for q in risk for h in (18, 19, 9.5) for d in ("first_bar", "gap")]),
    }


def bh(values: pd.Series) -> pd.Series:
    out = pd.Series(np.nan, index=values.index)
    valid = values.dropna().sort_values()
    if len(valid):
        out.loc[valid.index] = (valid * len(valid) / np.arange(1, len(valid) + 1)).iloc[::-1].cummin().iloc[::-1].clip(upper=1)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nq", type=Path, required=True)
    ap.add_argument("--xau", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--family", action="append", default=[])
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    raw = {"NQ": load_intraday_csv(args.nq, "UTC"), "XAUUSD": load_intraday_csv(args.xau, "UTC")}
    data = {"NQ": features(raw["NQ"]), "XAUUSD": features(raw["XAUUSD"])}
    all_rows, holdout_trades = [], []
    for family, (symbol, fn, candidates) in grids().items():
        if args.family and family not in args.family:
            continue
        print(f"START {family}: {len(candidates)} candidates", flush=True)
        f = data[symbol]
        dates = sorted(pd.unique(f.date))
        cut1, cut2 = int(.6 * len(dates)), int(.8 * len(dates))
        train, validate, holdout = set(dates[:cut1]), set(dates[cut1:cut2]), set(dates[cut2:])
        scored = []
        signal_cache = {}
        for p in candidates:
            signal_key = json.dumps({k: v for k, v in p.items() if k not in {"stop_atr", "reward_r", "hold_minutes", "fixed_stop", "fixed_target"}}, sort_keys=True)
            if signal_key not in signal_cache:
                signal_cache[signal_key] = fn(f, p)
            sig = signal_cache[signal_key]
            mt = metrics(simulate(f, sig, COSTS[symbol], p, train))
            mv = metrics(simulate(f, sig, COSTS[symbol], p, validate))
            stable = int((mt["expectancy"] or -1e99) > 0) + int((mv["expectancy"] or -1e99) > 0)
            scored.append((stable, mv["expectancy"] or -1e99, mt["expectancy"] or -1e99, p, sig, mt, mv))
        best = max(scored, key=lambda x: (x[0], x[1], x[2]))
        _, _, _, p, sig, mt, mv = best
        trades = simulate(f, sig, COSTS[symbol], p, holdout)
        mh = metrics(trades)
        row = {"family": family, "symbol": symbol, "parameters": p, "development": mt, "validation": mv, "holdout": mh,
               "candidates_tested": len(candidates), "holdout_start": str(dates[cut2]), "holdout_end": str(dates[-1])}
        all_rows.append(row)
        for trade in trades:
            holdout_trades.append({"family": family, **trade})
        (args.output / "partial_results.json").write_text(json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8")
        pd.DataFrame(holdout_trades).to_csv(args.output / "partial_holdout_trades.csv", index=False)
        print(f"DONE {family}: holdout={mh}", flush=True)
    pvals = pd.Series([row["holdout"]["p_value"] for row in all_rows])
    qvals = bh(pvals)
    for i, row in enumerate(all_rows):
        row["holdout"]["bh_q_value"] = None if pd.isna(qvals.iloc[i]) else float(qvals.iloc[i])
        h = row["holdout"]
        row["classification"] = "experimental" if h["trades"] >= 30 and (h["expectancy"] or 0) > 0 and (h["bh_q_value"] or 1) < .10 else "rejected"
    all_rows.append({"family": "caixa_americana", "symbol": "WIN", "classification": "needs_more_data", "reason": "No causal WIN M2 history was supplied or available from the HonorPro account."})
    payload = {"method": "60% development / 20% validation selection / 20% untouched holdout; next-bar execution; costs included", "results": all_rows}
    (args.output / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(holdout_trades).to_csv(args.output / "holdout_trades.csv", index=False)
    manifest = {"inputs": {"NQ": str(args.nq), "XAUUSD": str(args.xau)}, "sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.nq, args.xau)}, "costs": {k: asdict(v) for k,v in COSTS.items()}}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
