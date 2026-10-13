"""Baselines obrigatórias (plano Fase 2.4), com a MESMA execução e os MESMOS custos.

Um setup que não bate a entrada aleatória na mesma janela não tem vantagem
demonstrada: o resultado pode vir só do horário, da tendência do período ou
da geometria stop/alvo.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.execution_sim import CostModel, SimTrade, replay_ready_signals
from app.forward_stats import COMPLETED
from app.opportunity import SetupState, Transition
from app.setups.gold_fakeout import GoldFakeoutOpen


class PlainBreakout(GoldFakeoutOpen):
    """Rompimento de N barras na janela, sem MM longa e sem confirmações."""

    name = "plain_breakout"

    def step(self, at: pd.Timestamp, row: pd.Series) -> list[Transition]:
        self.state = SetupState.IDLE
        if pd.isna(row["prior_high"]) or not bool(row["in_window"]):
            return []
        close = float(row["close"])
        if close > float(row["prior_high"]):
            direction, stop = "long", float(row["low"])
        elif close < float(row["prior_low"]):
            direction, stop = "short", float(row["high"])
        else:
            return []
        return [self._move(at, SetupState.READY_TO_ENTER, "Rompimento simples.", direction,
                           opportunity_id=f"{self.name}:{at.isoformat()}", stop=stop,
                           target_r=float(self.config["target_r"]), max_hold_minutes=int(self.config["max_hold_minutes"]),
                           brt_hour=int(row["brt_hour"]))]


def ready_signals(transitions: list[Transition]) -> list[dict]:
    return [
        {**t.payload, "at": t.at, "direction": t.direction}
        for t in transitions
        if t.to_state == SetupState.READY_TO_ENTER
    ]


def _expectancy(trades: list[SimTrade]) -> float | None:
    rs = [t.r for t in trades if t.outcome in COMPLETED and t.r is not None]
    return float(np.mean(rs)) if rs else None


def random_entry_distribution(
    bars_m5: pd.DataFrame,
    strategy_trades: list[SimTrade],
    config: dict,
    costs: CostModel,
    *,
    seeds: int = 200,
) -> dict:
    """Mesmo número de entradas, mesma proporção de direção e mesmas distâncias de stop, em horários aleatórios da janela."""
    real = [t for t in strategy_trades if t.outcome in COMPLETED]
    if not real:
        return {"seeds": 0, "expectancies": [], "p95": None, "p50": None}
    window = GoldFakeoutOpen(config).features(bars_m5[["open", "high", "low", "close", "spread", "tick_volume"]].copy())
    candidates = window.index[window["in_window"].to_numpy()]
    hours = window.loc[candidates, "brt_hour"].to_numpy()
    directions = [t.direction for t in real]
    distances = [abs(t.entry - t.stop) for t in real]
    out: list[float] = []
    for seed in range(seeds):
        rng = np.random.default_rng(seed)
        picks = np.sort(rng.choice(len(candidates), size=len(real), replace=False))
        signals = []
        for k, pick in enumerate(picks):
            at = candidates[pick] + pd.Timedelta(minutes=5)  # fechamento da barra M5 sorteada
            nxt = bars_m5.index.searchsorted(at, side="left")
            if nxt >= len(bars_m5):
                continue
            bar = bars_m5.iloc[nxt]
            direction = directions[rng.integers(len(directions))]
            side = 1 if direction == "long" else -1
            est_entry = float(bar["open"]) + (float(bar["spread"]) * costs.point if side == 1 else 0)
            dist = distances[rng.integers(len(distances))]
            signals.append({
                "opportunity_id": f"random:{seed}:{k}", "at": at.isoformat(), "direction": direction,
                "stop": est_entry - side * dist, "target_r": float(config["target_r"]),
                "max_hold_minutes": int(config["max_hold_minutes"]), "brt_hour": int(hours[pick]),
            })
        trades, _ = replay_ready_signals(bars_m5, signals, costs)
        value = _expectancy(trades)
        if value is not None:
            out.append(value)
    arr = np.asarray(out)
    return {
        "seeds": len(out),
        "p05": round(float(np.quantile(arr, 0.05)), 4),
        "p50": round(float(np.quantile(arr, 0.5)), 4),
        "p95": round(float(np.quantile(arr, 0.95)), 4),
        "mean": round(float(arr.mean()), 4),
        "expectancies": [round(v, 4) for v in out],
    }


def percentile_of(value: float | None, distribution: list[float]) -> float | None:
    if value is None or not distribution:
        return None
    return round(float(np.mean(np.asarray(distribution) <= value)) * 100, 1)
