"""Walk-forward validation for the cross-sectional edge as a tradable strategy.

This turns the IC audit into a practical monthly walk-forward simulation:

- Train only on dates before the validation month.
- Select the best features by train IC.
- Rank symbols daily by a signed multi-feature consensus score.
- Hold the top quantile for PRIMARY_HORIZON trading days.
- Avoid the bottom quantile entirely.
- Apply macro risk sizing from DXY/US10Y/VIX.
- Charge cost + slippage on turnover.
- Report monthly returns, drawdown, turnover and stability.

Run:
    python -m scripts.cross_sectional_strategy_validation
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from app import paper_simulator as sim
from app.market_data import macro_data
from app.market_data import service as market_data_service
from scripts.compare_recommendations import DEFAULT_SYMBOLS, _load_prepared, _symbols
from scripts.data_reliability_gate import build_report as build_data_gate
from scripts.statistical_edge_audit import (
    EMBARGO_DAYS,
    MIN_SYMBOLS_PER_DAY,
    PRIMARY_HORIZON,
    QUANTILE,
    TOP_FEATURES_TO_VALIDATE,
    _build_panel,
    _daily_ic,
    _ic_table,
    _normalize_index,
)

OUT_PATH = Path("data/cross_sectional_strategy_validation.json")
MIN_TRAIN_DAYS = 160
ROUND_TRIP_COST_BPS = (sim.COST_BPS + sim.SLIPPAGE_BPS) * 2
MAX_POSITION_PCT = 0.25
BASE_GROSS_EXPOSURE = 1.0
RISK_OFF_GROSS_EXPOSURE = 0.0
CAUTION_GROSS_EXPOSURE = 0.5
NORMAL_GROSS_EXPOSURE = 1.0
MONTHLY_STOP_LOSS_PCT = -0.08


def _safe_float(value) -> float | None:
    if value is None or pd.isna(value) or np.isinf(value):
        return None
    return float(value)


def _t_stat(values: pd.Series) -> float | None:
    values = values.dropna()
    if len(values) < 3:
        return None
    std = float(values.std())
    if std == 0:
        return None
    return float(values.mean() / std * math.sqrt(len(values)))


def _max_drawdown(equity: list[float]) -> float:
    peak = equity[0] if equity else 1.0
    max_dd = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            max_dd = min(max_dd, value / peak - 1)
    return float(max_dd)


def _macro_frame(dates: pd.Series) -> pd.DataFrame:
    idx = pd.DatetimeIndex(sorted(pd.to_datetime(dates).unique()))
    out = pd.DataFrame(index=idx)
    for key in ["DXY", "US10Y", "VIX"]:
        history = macro_data.get_macro_history(key, period=sim.MARKET_HISTORY_PERIOD, interval="1d")
        if history.empty or "close" not in history:
            out[key.lower()] = np.nan
            continue
        close = history["close"].copy()
        close.index = _normalize_index(close.index)
        close = close[~close.index.duplicated(keep="last")]
        out[key.lower()] = close.reindex(idx, method="ffill")
    out["dxy_ret_5d"] = out["dxy"].pct_change(5) * 100
    out["dxy_ret_20d"] = out["dxy"].pct_change(20) * 100
    out["us10y_change_5d"] = out["us10y"].diff(5)
    out["us10y_change_20d"] = out["us10y"].diff(20)
    qqq = market_data_service.get_bars(sim.BENCHMARK_SYMBOL, period=sim.MARKET_HISTORY_PERIOD, interval="1d")
    if qqq.empty:
        out["qqq_ret_20d"] = np.nan
        out["qqq_sma50_gap_pct"] = np.nan
    else:
        qqq_close = qqq["close"].copy()
        qqq_close.index = _normalize_index(qqq_close.index)
        qqq_close = qqq_close[~qqq_close.index.duplicated(keep="last")].reindex(idx, method="ffill")
        out["qqq_ret_20d"] = qqq_close.pct_change(20) * 100
        out["qqq_sma50_gap_pct"] = (qqq_close / qqq_close.rolling(50, min_periods=50).mean() - 1) * 100
    return out


def _risk_multiplier(row: pd.Series) -> tuple[float, str]:
    vix = row.get("vix")
    dxy_5d = row.get("dxy_ret_5d")
    dxy_20d = row.get("dxy_ret_20d")
    us10y_5d = row.get("us10y_change_5d")
    us10y_20d = row.get("us10y_change_20d")
    qqq_20d = row.get("qqq_ret_20d")
    qqq_sma50_gap = row.get("qqq_sma50_gap_pct")

    severe = (
        (pd.notna(vix) and vix >= 30)
        or (pd.notna(dxy_20d) and dxy_20d > 2.5 and pd.notna(us10y_20d) and us10y_20d > 0.35)
        or (pd.notna(qqq_20d) and qqq_20d <= -8.0)
        or (pd.notna(qqq_sma50_gap) and qqq_sma50_gap <= -6.0)
    )
    caution = (
        (pd.notna(vix) and vix >= 24)
        or (pd.notna(dxy_5d) and dxy_5d > 1.0 and pd.notna(us10y_5d) and us10y_5d > 0.15)
        or (pd.notna(us10y_20d) and us10y_20d > 0.45)
        or (pd.notna(qqq_20d) and qqq_20d <= -4.0)
        or (pd.notna(qqq_sma50_gap) and qqq_sma50_gap <= -2.0)
    )
    if severe:
        return RISK_OFF_GROSS_EXPOSURE, "risk_off"
    if caution:
        return CAUTION_GROSS_EXPOSURE, "caution"
    return NORMAL_GROSS_EXPOSURE, "normal"


def _select_features(train: pd.DataFrame, feature_names: list[str]) -> list[dict]:
    target = f"fwd_return_{PRIMARY_HORIZON}d"
    rows = []
    for feature in feature_names:
        ic = _daily_ic(train, feature, target)
        if len(ic) < 40:
            continue
        mean_ic = float(ic.mean())
        rows.append(
            {
                "feature": feature,
                "mean_ic": mean_ic,
                "abs_ic": abs(mean_ic),
                "direction": 1 if mean_ic >= 0 else -1,
                "days": int(len(ic)),
            }
        )
    rows.sort(key=lambda row: row["abs_ic"], reverse=True)
    return rows[:TOP_FEATURES_TO_VALIDATE]


def _score_holdout(holdout: pd.DataFrame, selected: list[dict]) -> pd.DataFrame:
    scored = holdout[["symbol", "date", f"fwd_return_{PRIMARY_HORIZON}d"]].copy()
    score_parts = []
    for item in selected:
        feature = item["feature"]
        signed_rank = item["direction"] * (holdout.groupby("date")[feature].rank(pct=True) - 0.5)
        col = f"rank_{feature}"
        scored[col] = signed_rank
        score_parts.append(col)
    scored["edge_score"] = scored[score_parts].mean(axis=1)
    return scored


def _target_weights(group: pd.DataFrame, gross_exposure: float) -> dict[str, float]:
    group = group.dropna(subset=["edge_score", f"fwd_return_{PRIMARY_HORIZON}d"])
    if len(group) < MIN_SYMBOLS_PER_DAY or gross_exposure <= 0:
        return {}
    n = max(1, int(len(group) * QUANTILE))
    ranked = group.sort_values("edge_score", ascending=False)
    selected = ranked.head(n)
    # Explicitly avoid the bottom quantile: selected is top quantile only.
    per_position = min(MAX_POSITION_PCT, gross_exposure / len(selected))
    scale = min(gross_exposure, per_position * len(selected))
    if scale <= 0:
        return {}
    per_position = scale / len(selected)
    return {row.symbol: float(per_position) for row in selected.itertuples(index=False)}


def _turnover(prev: dict[str, float], current: dict[str, float]) -> float:
    symbols = set(prev) | set(current)
    return float(sum(abs(current.get(symbol, 0.0) - prev.get(symbol, 0.0)) for symbol in symbols))


def _period_return(group: pd.DataFrame, weights: dict[str, float], turnover: float) -> float:
    returns = group.set_index("symbol")[f"fwd_return_{PRIMARY_HORIZON}d"].to_dict()
    gross = sum(weight * (float(returns.get(symbol, 0.0)) / 100.0) for symbol, weight in weights.items())
    cost = turnover * ROUND_TRIP_COST_BPS / 10000.0
    return float(gross - cost)


def _monthly_windows(panel: pd.DataFrame) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    dates = pd.DatetimeIndex(sorted(pd.to_datetime(panel["date"]).unique()))
    months = pd.PeriodIndex(dates, freq="M").unique()
    windows = []
    for month in months:
        month_dates = dates[pd.PeriodIndex(dates, freq="M") == month]
        if len(month_dates) == 0:
            continue
        windows.append((month_dates.min(), month_dates.max() + pd.Timedelta(days=1)))
    return windows


def _run_strategy(panel: pd.DataFrame, feature_names: list[str]) -> dict:
    target = f"fwd_return_{PRIMARY_HORIZON}d"
    macro = _macro_frame(panel["date"])
    months = _monthly_windows(panel)
    equity = 1.0
    equity_curve = [equity]
    prev_weights: dict[str, float] = {}
    trades = []
    monthly = []

    for start, end in months:
        train_end = start - pd.Timedelta(days=EMBARGO_DAYS)
        train = panel[panel["date"] < train_end].dropna(subset=feature_names + [target])
        holdout = panel[(panel["date"] >= start) & (panel["date"] < end)].dropna(subset=[target])
        if train["date"].nunique() < MIN_TRAIN_DAYS or holdout.empty:
            continue

        selected = _select_features(train, feature_names)
        if not selected:
            continue
        scored = _score_holdout(holdout, selected)
        rebalance_dates = sorted(scored["date"].unique())[::PRIMARY_HORIZON]

        month_start_equity = equity
        month_turnover = 0.0
        month_periods = 0
        month_risk_states: dict[str, int] = {}
        month_stopped = False

        for date in rebalance_dates:
            group = scored[scored["date"] == date]
            if len(group) < MIN_SYMBOLS_PER_DAY:
                continue
            macro_row = macro.loc[date] if date in macro.index else pd.Series(dtype=float)
            if month_stopped:
                gross_exposure, risk_state = 0.0, "monthly_stop"
            else:
                gross_exposure, risk_state = _risk_multiplier(macro_row)
            weights = _target_weights(group, gross_exposure)
            turnover = _turnover(prev_weights, weights)
            period_return = _period_return(group, weights, turnover)
            equity *= 1 + period_return
            if equity / month_start_equity - 1 <= MONTHLY_STOP_LOSS_PCT:
                month_stopped = True
            equity_curve.append(equity)
            prev_weights = weights
            month_turnover += turnover
            month_periods += 1
            month_risk_states[risk_state] = month_risk_states.get(risk_state, 0) + 1
            trades.append(
                {
                    "date": str(pd.Timestamp(date).date()),
                    "risk_state": risk_state,
                    "gross_exposure": round(gross_exposure, 4),
                    "positions": sorted(weights),
                    "turnover": round(turnover, 4),
                    "period_return_pct": round(period_return * 100, 4),
                    "equity": round(equity, 6),
                }
            )

        if month_periods:
            monthly_return = equity / month_start_equity - 1
            monthly.append(
                {
                    "month": str(pd.Timestamp(start).to_period("M")),
                    "return_pct": round(monthly_return * 100, 4),
                    "periods": month_periods,
                    "avg_turnover": round(month_turnover / month_periods, 4),
                    "selected_features": [item["feature"] for item in selected],
                    "risk_states": month_risk_states,
                }
            )

    monthly_returns = pd.Series([row["return_pct"] / 100 for row in monthly], dtype=float)
    total_return = equity - 1
    return {
        "config": {
            "horizon_days": PRIMARY_HORIZON,
            "quantile": QUANTILE,
            "top_features": TOP_FEATURES_TO_VALIDATE,
            "round_trip_cost_bps": ROUND_TRIP_COST_BPS,
            "max_position_pct": MAX_POSITION_PCT,
            "min_train_days": MIN_TRAIN_DAYS,
            "embargo_days": EMBARGO_DAYS,
            "monthly_stop_loss_pct": MONTHLY_STOP_LOSS_PCT * 100,
        },
        "summary": {
            "months": len(monthly),
            "periods": len(trades),
            "total_return_pct": round(total_return * 100, 4),
            "annualized_return_approx_pct": round(((1 + total_return) ** (12 / len(monthly)) - 1) * 100, 4) if monthly else None,
            "max_drawdown_pct": round(_max_drawdown(equity_curve) * 100, 4),
            "monthly_hit_rate": round(float((monthly_returns > 0).mean()), 4) if len(monthly_returns) else None,
            "mean_monthly_return_pct": round(float(monthly_returns.mean() * 100), 4) if len(monthly_returns) else None,
            "monthly_t_stat": round(_t_stat(monthly_returns), 3) if _t_stat(monthly_returns) is not None else None,
            "final_equity": round(equity, 6),
        },
        "monthly": monthly,
        "trades": trades,
    }


def build_report() -> dict:
    gate = build_data_gate()
    if gate["status"] != "PASS":
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "BLOCKED_BY_DATA_GATE",
            "data_gate": gate,
        }

    symbols = _symbols() or DEFAULT_SYMBOLS
    prepared, benchmark, skipped = _load_prepared(symbols)
    panel, feature_names = _build_panel(prepared, benchmark)
    quality_features = []
    for feature in feature_names:
        values = panel[feature]
        if values.isna().mean() <= 0.15 and values.nunique(dropna=True) >= 5 and _safe_float(values.std()) not in (None, 0.0):
            quality_features.append(feature)
    primary_ic = _ic_table(panel, quality_features, PRIMARY_HORIZON)
    strategy = _run_strategy(panel, quality_features)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "symbols_used": sorted(prepared),
        "symbols_skipped": skipped,
        "rows": int(len(panel)),
        "features_usable": len(quality_features),
        "top_trainable_features_full_sample": primary_ic.head(15).to_dict(orient="records"),
        "strategy": strategy,
    }


def main() -> None:
    report = build_report()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("CROSS-SECTIONAL STRATEGY VALIDATION")
    print("=" * 72)
    print(f"Status: {report['status']} | relatorio: {OUT_PATH}")
    if report["status"] != "PASS":
        print("Bloqueado pelo data gate.")
        raise SystemExit(1)
    print(json.dumps(report["strategy"]["summary"], ensure_ascii=False, indent=2))
    print("\nULTIMOS MESES")
    print(pd.DataFrame(report["strategy"]["monthly"]).tail(12).to_string(index=False))


if __name__ == "__main__":
    main()
