"""Estatística de evidência por setup (plano Fase 1.5) e veredito pré-registrado.

Métrica primária: expectância líquida em R por trade, com IC bootstrap.
Trades censurados ou pulados não entram (sem PnL inventado), mas são contados.
"""
from __future__ import annotations

from math import ceil
from statistics import NormalDist

import numpy as np
import pandas as pd

from app.reliability import wilson_interval

COMPLETED = {"TARGET", "STOP", "TIME_EXIT"}


def bootstrap_mean_ci(values: list[float], *, resamples: int = 10_000, seed: int = 7, alpha: float = 0.05) -> tuple[float, float] | None:
    if len(values) < 2:
        return None
    rng = np.random.default_rng(seed)
    arr = np.asarray(values, dtype=float)
    means = arr[rng.integers(0, len(arr), size=(resamples, len(arr)))].mean(axis=1)
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def required_trades(effect_r: float, sd_r: float, *, alpha: float = 0.05, power: float = 0.8) -> int:
    """n para detectar expectância `effect_r` (teste bilateral) com desvio `sd_r` por trade."""
    z = NormalDist().inv_cdf(1 - alpha / 2) + NormalDist().inv_cdf(power)
    return int(ceil((z * sd_r / effect_r) ** 2))


def max_drawdown(rs: list[float]) -> float:
    equity = np.cumsum(rs) if rs else np.array([0.0])
    peak = np.maximum.accumulate(np.concatenate([[0.0], equity]))
    return float((peak[1:] - equity).max()) if rs else 0.0


def _group(trades: list[dict], key) -> dict:
    groups: dict = {}
    for trade in trades:
        k = key(trade)
        g = groups.setdefault(str(k), {"trades": 0, "sum_r": 0.0, "wins": 0})
        g["trades"] += 1
        g["sum_r"] += trade["r"]
        g["wins"] += trade["r"] > 0
    return {
        k: {"trades": g["trades"], "expectancy_r": round(g["sum_r"] / g["trades"], 4), "win_rate": round(g["wins"] / g["trades"], 4)}
        for k, g in sorted(groups.items())
    }


def summarize(trades: list[dict], *, sessions: int | None = None) -> dict:
    completed = [t for t in trades if t.get("outcome") in COMPLETED and t.get("r") is not None]
    rs = [float(t["r"]) for t in completed]
    wins = sum(r > 0 for r in rs)
    gains = sum(r for r in rs if r > 0)
    losses = -sum(r for r in rs if r < 0)
    ci = bootstrap_mean_ci(rs)
    wil = wilson_interval(wins, len(rs))
    sd = float(np.std(rs, ddof=1)) if len(rs) > 1 else None
    return {
        "sessions": sessions,
        "signals_executed": len(trades),
        "completed_trades": len(rs),
        "censored": sum(t.get("outcome") == "CENSORED" for t in trades),
        "skipped": sum(t.get("outcome") == "SKIPPED" for t in trades),
        "expectancy_r": round(float(np.mean(rs)), 4) if rs else None,
        "expectancy_ci95": [round(ci[0], 4), round(ci[1], 4)] if ci else None,
        "sd_r": round(sd, 4) if sd is not None else None,
        "win_rate": round(wins / len(rs), 4) if rs else None,
        "win_rate_ci95": [round(wil[0], 4), round(wil[1], 4)] if wil else None,
        "profit_factor": round(gains / losses, 4) if losses > 0 else None,
        "total_r": round(sum(rs), 4),
        "max_drawdown_r": round(max_drawdown(rs), 4),
        "avg_mae_r": round(float(np.mean([t["mae_r"] for t in completed])), 4) if completed else None,
        "avg_mfe_r": round(float(np.mean([t["mfe_r"] for t in completed])), 4) if completed else None,
        "outcomes": {o: sum(t.get("outcome") == o for t in trades) for o in ("TARGET", "STOP", "TIME_EXIT", "CENSORED", "SKIPPED")},
        "by_direction": _group(completed, lambda t: t["direction"]),
        "by_brt_hour": _group(completed, lambda t: t.get("brt_hour")),
        "by_month": _group(completed, lambda t: str(t["entry_at"])[:7]),
        "by_weekday": _group(completed, lambda t: pd.Timestamp(t["entry_at"]).day_name()),
    }


def verdict(summary: dict, decision_rule: dict, *, baseline_p95: float | None = None) -> dict:
    """Aplica a regra pré-registrada. Nunca promove com amostra abaixo do mínimo."""
    min_sessions = int(decision_rule.get("min_sessions", 250))
    min_trades = int(decision_rule.get("min_trades", 100))
    sessions = summary.get("sessions") or 0
    n = summary.get("completed_trades") or 0
    ci = summary.get("expectancy_ci95")
    progress = {
        "sessions": f"{sessions}/{min_sessions}",
        "trades": f"{n}/{min_trades}",
        "pct": round(min(sessions / min_sessions, n / min_trades, 1.0) * 100, 1) if min_sessions and min_trades else None,
    }
    if sessions < min_sessions or n < min_trades:
        status = "COLLECTING"
        reason = f"Amostra abaixo do mínimo pré-registrado ({progress['sessions']} sessões, {progress['trades']} trades)."
        if ci is not None and ci[1] < 0:
            reason += " Leitura parcial: IC 95% inteiramente negativo."
        return {"status": status, "reason": reason, "progress": progress}
    if ci is not None and ci[0] > 0 and (baseline_p95 is None or summary["expectancy_r"] > baseline_p95):
        return {"status": "PASSED", "reason": "IC 95% acima de zero e acima da baseline aleatória.", "progress": progress}
    return {
        "status": "ARCHIVE",
        "reason": "Mínimo atingido e o IC 95% contém zero ou é negativo (ou não supera a baseline). Arquivar sem reotimizar.",
        "progress": progress,
    }


def sample_size_note(summary: dict, effect_r: float = 0.15) -> dict:
    sd = summary.get("sd_r") or 1.1
    n = required_trades(effect_r, sd)
    return {"effect_r": effect_r, "sd_r_used": sd, "trades_needed": n,
            "explanation": f"Para detectar +{effect_r}R com desvio {sd:.2f}R por trade (95%/80%): ~{n} trades."}

