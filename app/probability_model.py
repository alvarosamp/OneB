"""Logistic regression on top of the same features the rule engine already
computes (see app.paper_simulator.feature_vector) — estimates P(the 5-day
forward return beats +0.5%) as a continuous number instead of a hard score
cutoff.

Deliberately NOT a replacement for the rule engine: app.decision_engine only
uses this to *tighten* a would-be BUY_CONTROLLED (downgrade it if the model
disagrees), never to approve a trade the rules would have rejected. If no
trained model file is present, every call here returns None and callers fall
back to the pre-existing score-only behavior — same fail-open philosophy as
the LLM narrator and the earnings-calendar check.

Plain numpy (no scikit-learn): pandas already pulls numpy in transitively,
so this adds no new dependency to the Docker image, and a ~10-feature
logistic regression trained by hand-rolled gradient descent is simple enough
to read top to bottom.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

MODEL_PATH = Path(os.getenv("PROBABILITY_MODEL_PATH", "data/probability_model.json"))
CANDIDATE_MODEL_PATH = Path(os.getenv("PROBABILITY_MODEL_CANDIDATE_PATH", "data/probability_model.candidate.json"))
HISTORY_PATH = Path(os.getenv("PROBABILITY_MODEL_HISTORY_PATH", "data/probability_model_history.json"))
HISTORY_MAX_ENTRIES = int(os.getenv("PROBABILITY_MODEL_HISTORY_MAX_ENTRIES", "52"))
DRIFT_ALERT_ACCURACY = float(os.getenv("PROBABILITY_MODEL_DRIFT_ACCURACY", "0.52"))
PROMOTION_MIN_ACCURACY = float(os.getenv("PROBABILITY_MODEL_PROMOTION_MIN_ACCURACY", "0.52"))
PROMOTION_MIN_AUC = float(os.getenv("PROBABILITY_MODEL_PROMOTION_MIN_AUC", "0.50"))
PROMOTION_MIN_HOLDOUT_SAMPLES = int(os.getenv("PROBABILITY_MODEL_PROMOTION_MIN_HOLDOUT_SAMPLES", "500"))


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def _standardize(x: np.ndarray, mean: np.ndarray | None, std: np.ndarray | None):
    if mean is None:
        mean = x.mean(axis=0)
    if std is None:
        std = x.std(axis=0)
        std = np.where(std == 0, 1.0, std)
    return (x - mean) / std, mean, std


def _train_logistic_regression(x: np.ndarray, y: np.ndarray, epochs: int = 500, lr: float = 0.25, l2: float = 0.02):
    n, d = x.shape
    weights = np.zeros(d)
    bias = 0.0
    for _ in range(epochs):
        preds = _sigmoid(x @ weights + bias)
        error = preds - y
        grad_weights = x.T @ error / n + l2 * weights
        grad_bias = float(error.mean())
        weights -= lr * grad_weights
        bias -= lr * grad_bias
    return weights, bias


def fit(feature_names: list[str], samples: list[list[float]], labels: list[int]) -> dict:
    x = np.array(samples, dtype=float)
    y = np.array(labels, dtype=float)
    x_std, mean, std = _standardize(x, None, None)
    weights, bias = _train_logistic_regression(x_std, y)
    preds = _sigmoid(x_std @ weights + bias)
    accuracy = float(((preds >= 0.5).astype(float) == y).mean())
    return {
        "features": feature_names,
        "mean": mean.tolist(),
        "std": std.tolist(),
        "weights": weights.tolist(),
        "bias": float(bias),
        "train_samples": int(len(y)),
        "train_accuracy": round(accuracy, 4),
        "train_positive_rate": round(float(y.mean()), 4) if len(y) else None,
    }


def predict_proba(model: dict, features: list[float]) -> float:
    x = np.array(features, dtype=float)
    mean = np.array(model["mean"], dtype=float)
    std = np.array(model["std"], dtype=float)
    x_std = (x - mean) / std
    z = float(np.dot(x_std, np.array(model["weights"], dtype=float)) + float(model["bias"]))
    return float(_sigmoid(np.array([z]))[0])


def save_model(model: dict, path: Path = MODEL_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")


def candidate_promotion_failures(model: dict) -> list[str]:
    """Return objective reasons why a candidate must not replace production.

    Promotion is deliberately fail-closed: missing metrics are failures, and
    accuracy must beat both an absolute floor and the majority-class baseline.
    """
    failures: list[str] = []
    samples = int(model.get("holdout_samples") or 0)
    accuracy = model.get("holdout_accuracy")
    auc = model.get("holdout_auc")
    positive_rate = model.get("holdout_positive_rate")
    baseline = max(float(positive_rate), 1 - float(positive_rate)) if positive_rate is not None else None
    if samples < PROMOTION_MIN_HOLDOUT_SAMPLES:
        failures.append(f"holdout_samples<{PROMOTION_MIN_HOLDOUT_SAMPLES}")
    if accuracy is None:
        failures.append("holdout_accuracy_missing")
    else:
        if float(accuracy) < PROMOTION_MIN_ACCURACY:
            failures.append(f"holdout_accuracy<{PROMOTION_MIN_ACCURACY}")
        if baseline is None or float(accuracy) <= baseline:
            failures.append("holdout_accuracy<=majority_baseline")
    if auc is None:
        failures.append("holdout_auc_missing")
    elif float(auc) < PROMOTION_MIN_AUC:
        failures.append(f"holdout_auc<{PROMOTION_MIN_AUC}")
    for key in ("trained_at", "git_commit", "dataset_sha256", "config_sha256", "holdout_brier", "calibration_error"):
        if model.get(key) is None:
            failures.append(f"{key}_missing")
    return failures


def load_model(path: Path = MODEL_PATH) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


_model_cache: object = "unloaded"


def get_model() -> dict | None:
    """Cached accessor used at request time — call reload_model() after
    retraining to pick up a new file without restarting the process."""
    global _model_cache
    if _model_cache == "unloaded":
        _model_cache = load_model()
    return _model_cache


def reload_model() -> None:
    global _model_cache
    _model_cache = "unloaded"


def _load_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def record_training(model: dict) -> None:
    """Appends this training run's headline numbers to a rolling history
    file — what lets health() spot the model's edge quietly decaying toward
    a coin flip over successive weekly retrains, instead of only ever
    seeing the latest snapshot.
    """
    history = _load_history()
    history.append(
        {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "train_samples": model.get("train_samples"),
            "train_accuracy": model.get("train_accuracy"),
            "holdout_samples": model.get("holdout_samples"),
            "holdout_accuracy": model.get("holdout_accuracy"),
        }
    )
    history = history[-HISTORY_MAX_ENTRIES:]
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def health() -> dict:
    """Current model status plus enough history to see the trend."""
    model = get_model()
    history = _load_history()
    latest = history[-1] if history else None
    holdout_accuracy = latest["holdout_accuracy"] if latest else (model or {}).get("holdout_accuracy")
    drift_alert = holdout_accuracy is not None and holdout_accuracy < DRIFT_ALERT_ACCURACY
    return {
        "model_present": model is not None,
        "latest": latest,
        "history": history,
        "drift_alert": drift_alert,
        "drift_alert_threshold": DRIFT_ALERT_ACCURACY,
    }
