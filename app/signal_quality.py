"""Signal Quality AI (plano Fase 3): meta-labeling sobre os eventos de um setup.

O setup decide a direção; este modelo só estima P(trade termina positivo |
contexto no instante do READY) para decidir tomar ou pular. Nunca gera direção,
entrada, stop ou alvo.

- Rótulo alinhado ao cartão (triple barrier): o trade simulado com o MESMO
  stop/alvo/prazo do setup; y = R líquido > 0 (TIME_EXIT entra pelo R realizado).
- Split cronológico treino/calibração/teste com embargo de `max_hold`.
- Calibração Venn-Abers indutiva (isotônica): cada previsão sai com intervalo
  [p0, p1] em vez de um número solto.
- Promoção econômica, não por acurácia: no teste, a expectância dos trades
  ACEITOS tem que superar a de todos, com IC bootstrap da diferença > 0.
- Fail-closed: sem eventos suficientes ou sem promoção, predict() devolve None.
"""
from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from app.forward_stats import COMPLETED
from app.research_statistics import session_block_statistics
from app.research_provenance import file_fingerprint

MIN_EVENTS = 150
MODEL_DIR = Path("data/signal_quality")
ACCEPT_THRESHOLD = 0.5
MAX_ECE = 0.08
SCHEMA_VERSION = "signal-quality-v2"


def dataset(trades: list[dict], feature_names: list[str] | None = None) -> tuple[list[str], np.ndarray, np.ndarray, np.ndarray, list[str]]:
    rows = [t for t in trades if t.get("outcome") in COMPLETED and t.get("r") is not None and t.get("features")]
    rows.sort(key=lambda t: t["entry_at"])
    names = feature_names or sorted({k for t in rows for k, v in t["features"].items() if isinstance(v, (int, float))})
    x = np.array([[float(t["features"].get(n) if t["features"].get(n) is not None else np.nan) for n in names] for t in rows])
    r = np.array([float(t["r"]) for t in rows])
    y = (r > 0).astype(int)
    times = [t["entry_at"] for t in rows]
    return names, x, y, r, times


def chronological_split(n: int, times: list[str], embargo_minutes: int, fractions=(0.6, 0.2),
                        label_ends: list[str] | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Índices de treino/calibração/teste em ordem temporal, removendo trades do embargo nas fronteiras."""
    import pandas as pd

    stamps = pd.to_datetime(times, utc=True)
    if n != len(stamps) or n < 3 or embargo_minutes < 0:
        raise ValueError("Invalid chronological split.")
    if not 0 < fractions[0] < 1 or not 0 < fractions[1] < 1 or sum(fractions) >= 1:
        raise ValueError("Invalid split fractions.")
    if stamps.hasnans or not stamps.is_monotonic_increasing:
        raise ValueError("Timestamps must be valid and ordered.")
    a, b = int(n * fractions[0]), int(n * (fractions[0] + fractions[1]))
    embargo = pd.Timedelta(minutes=embargo_minutes)

    def keep_after(start: int, end: int) -> np.ndarray:
        if start == 0:
            return np.arange(0, end)
        boundary = stamps[start - 1] + embargo
        return np.array([i for i in range(start, end) if stamps[i] > boundary], dtype=int)

    tr, ca, te = np.arange(0, a), keep_after(a, b), keep_after(b, n)
    # Even without explicit exits, assume the maximum lifetime rather than
    # permitting labels from train/calibration to reach the following block.
    ends = pd.to_datetime(label_ends, utc=True) if label_ends is not None else stamps + embargo
    if len(ends) != n or ends.hasnans or (ends < stamps).any():
        raise ValueError("Invalid label availability timestamps.")
    if len(ca):
        tr = tr[ends[tr] < stamps[ca[0]]]
    if len(te):
        ca = ca[ends[ca] < stamps[te[0]]]
    return tr, ca, te


def venn_abers(calib_scores: np.ndarray, calib_y: np.ndarray, score: float) -> tuple[float, float]:
    """Inductive Venn-Abers: intervalo [p0, p1] de probabilidade calibrada para um score."""
    out = []
    for label in (0, 1):
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        iso.fit(np.append(calib_scores, score), np.append(calib_y, label))
        out.append(float(iso.predict([score])[0]))
    return out[0], out[1]


def _merge(p0: float, p1: float) -> float:
    return p1 / (1 - p0 + p1) if (1 - p0 + p1) > 0 else 0.5


def _ece(probs: np.ndarray, y: np.ndarray, bins: int = 5) -> float:
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (probs >= lo) & (probs < hi if hi < 1 else probs <= hi)
        if mask.any():
            total += mask.mean() * abs(probs[mask].mean() - y[mask].mean())
    return float(total)


def _auc(y: np.ndarray, p: np.ndarray) -> float | None:
    pos, neg = p[y == 1], p[y == 0]
    if not len(pos) or not len(neg):
        return None
    return float(((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()) / (len(pos) * len(neg)))


def train(trades: list[dict], *, setup: str, max_hold_minutes: int, min_events: int = MIN_EVENTS) -> dict:
    names, x, y, r, times = dataset(trades)
    base = {"schema_version": SCHEMA_VERSION, "setup": setup, "trained_at": datetime.now(timezone.utc).isoformat(), "events": int(len(y)),
            "min_events": min_events, "features": names}
    if len(y) < min_events:
        return {**base, "status": "INSUFFICIENT_EVENTS", "promoted": False,
                "promotion_failures": [f"events<{min_events}"],
                "reason": f"{len(y)} eventos completos; o modelo só é treinado a partir de {min_events}."}
    import pandas as pd
    rows = sorted([t for t in trades if t.get("outcome") in COMPLETED and t.get("r") is not None and t.get("features")],
                  key=lambda t: t["entry_at"])
    # exit_at in the bar simulator is the opening of the exit candle. The
    # outcome becomes observable only when that candle has closed.
    ends = [(pd.Timestamp(t["label_end_at"]) if t.get("label_end_at") else
             pd.Timestamp(t["exit_at"]) + pd.Timedelta(minutes=5) if t.get("exit_at") else
             pd.Timestamp(t["entry_at"]) + pd.Timedelta(minutes=max_hold_minutes)).isoformat() for t in rows]
    tr, ca, te = chronological_split(len(y), times, max_hold_minutes, label_ends=ends)
    if any(len(part) < 20 for part in (tr, ca, te)) or not names or not np.isfinite(r).all() or np.isinf(x).any():
        return {**base, "status": "INVALID_DATA_OR_SPLIT", "promoted": False,
                "promotion_failures": ["invalid_data_or_split"]}
    if len(np.unique(y[tr])) < 2 or len(np.unique(y[ca])) < 2:
        return {**base, "status": "INSUFFICIENT_CLASSES", "promoted": False,
                "promotion_failures": ["training_or_calibration_single_class"]}
    # Feature schema and preprocessing are learned solely from training data.
    usable = ~np.isnan(x[tr]).all(axis=0)
    x, names = x[:, usable], [name for name, use in zip(names, usable) if use]
    if not names:
        return {**base, "status": "NO_TRAINING_FEATURES", "promoted": False,
                "promotion_failures": ["no_training_features"]}
    medians = np.nanmedian(x[tr], axis=0)
    x = np.where(np.isnan(x), medians, x)
    mean, std = x[tr].mean(axis=0), x[tr].std(axis=0)
    std = np.where(std == 0, 1.0, std)
    z = (x - mean) / std
    clf = LogisticRegression(C=0.5, max_iter=1000)
    clf.fit(z[tr], y[tr])
    scores = clf.decision_function(z)
    calib_scores, calib_y = scores[ca], y[ca]
    test_probs = np.array([_merge(*venn_abers(calib_scores, calib_y, s)) for s in scores[te]])
    accept_mask = test_probs >= ACCEPT_THRESHOLD
    accepted = r[te][accept_mask]
    stats = session_block_statistics(r[te], [times[i] for i in te], accepted=accept_mask,
                                     block_sessions=max(5, int(np.ceil(max_hold_minutes / 1440))))
    base_probability = float(y[tr].mean())
    test_brier = float(np.mean((test_probs - y[te]) ** 2))
    baseline_brier = float(np.mean((base_probability - y[te]) ** 2))
    metrics = {
        "train": int(len(tr)), "calibration": int(len(ca)), "test": int(len(te)),
        "test_auc": _auc(y[te], test_probs),
        "test_brier": test_brier,
        "baseline_brier": baseline_brier,
        "baseline_probability": base_probability,
        "brier_skill": 1 - test_brier / baseline_brier if baseline_brier > 0 else None,
        "test_ece": _ece(test_probs, y[te]) if len(te) else None,
        "test_expectancy_all_r": float(r[te].mean()) if len(te) else None,
        "test_expectancy_accepted_r": float(accepted.mean()) if len(accepted) else None,
        "test_accepted": int(len(accepted)),
        "accepted_minus_all_ci95": stats["accepted_minus_all_ci"],
        "accepted_expectancy_ci95": stats["accepted_mean_ci"],
        "policy_delta_ci95": stats["policy_delta_ci"],
        "policy_delta_r_per_session": stats["policy_delta_r_per_session"],
        "test_sessions": stats["sessions"],
        "coverage": float(accept_mask.mean()),
        "inference": stats,
    }
    failures = []
    if stats["accepted_minus_all_ci"] is None or stats["accepted_minus_all_ci"][0] <= 0:
        failures.append("accepted_expectancy_not_above_all")
    if stats["accepted_mean_ci"] is None or stats["accepted_mean_ci"][0] <= 0:
        failures.append("accepted_expectancy_not_positive")
    if stats["policy_delta_ci"] is None or stats["policy_delta_ci"][0] <= 0:
        failures.append("paired_policy_not_improved")
    if baseline_brier <= 0 or test_brier >= baseline_brier:
        failures.append("brier_not_above_baseline")
    if metrics["test_ece"] is None or metrics["test_ece"] > MAX_ECE:
        failures.append(f"ece>{MAX_ECE}")
    if metrics["test_auc"] is None or metrics["test_auc"] <= 0.5:
        failures.append("auc<=0.5")
    return {
        **base, "features": names, "status": "TRAINED", "metrics": metrics, "promoted": not failures, "promotion_failures": failures,
        "label": "net_r_positive_including_time_exit", "interval_kind": "venn_abers_bounds_not_ci95",
        "imputation_medians": medians.tolist(),
        "dataset_sha256": hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest(),
        "code": [file_fingerprint(__file__), file_fingerprint(Path(__file__).with_name("research_statistics.py"))],
        "mean": mean.tolist(), "std": std.tolist(), "coef": clf.coef_[0].tolist(), "intercept": float(clf.intercept_[0]),
        "calibration_scores": calib_scores.tolist(), "calibration_labels": calib_y.tolist(),
        "accept_threshold": ACCEPT_THRESHOLD,
    }


def save(model: dict, directory: Path = MODEL_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{model['setup']}.json"
    path.write_text(json.dumps(model, indent=2), encoding="utf-8")
    return path


def load(setup: str, directory: Path = MODEL_DIR) -> dict | None:
    path = directory / f"{setup}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def predict(model: dict | None, features: dict) -> dict | None:
    """P(trade positivo) com intervalo Venn-Abers. None se o modelo não foi promovido."""
    if not model or not model.get("promoted") or model.get("schema_version") != SCHEMA_VERSION:
        return None
    # Unmigrated promoted artifacts cannot bypass the new preprocessing/gates.
    if "imputation_medians" not in model:
        return None
    try:
        x = np.array([float(features[n]) if features.get(n) is not None else np.nan for n in model["features"]])
    except (ValueError, TypeError):
        return None
    if np.isinf(x).any() or np.isnan(x).all():
        return None
    x = np.where(np.isnan(x), np.asarray(model["imputation_medians"]), x)
    z = (x - np.array(model["mean"])) / np.array(model["std"])
    score = float(z @ np.array(model["coef"]) + model["intercept"])
    p0, p1 = venn_abers(np.array(model["calibration_scores"]), np.array(model["calibration_labels"]), score)
    p = _merge(p0, p1)
    return {"p_positive": round(p, 4), "interval": [round(p0, 4), round(p1, 4)],
            "interval_kind": "venn_abers_bounds_not_ci95", "label": model["label"],
            "take": p >= model["accept_threshold"], "n_calibration": len(model["calibration_labels"]),
            "trained_at": model["trained_at"]}
