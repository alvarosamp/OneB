from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone

import numpy as np

from app import paper_simulator as sim
from app import probability_model as pm
from scripts.calibrate_decision_strategy import WALK_FORWARD_FOLDS, WALK_FORWARD_WINDOW_DAYS, _walk_forward_folds
from scripts.compare_recommendations import DEFAULT_SYMBOLS, _load_prepared, _symbols


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def _prepared_hash(prepared: dict) -> str:
    digest = hashlib.sha256()
    for symbol in sorted(prepared):
        history = prepared[symbol]["history"]
        digest.update(symbol.encode())
        digest.update(np.asarray(history.index.astype("int64"), dtype="<i8").tobytes())
        digest.update(np.asarray(history[["open", "high", "low", "close", "volume"]], dtype="<f8").tobytes())
    return digest.hexdigest()


def _config_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _binary_auc(labels: list[int], predictions: list[float]) -> float | None:
    y = np.asarray(labels, dtype=int)
    scores = np.asarray(predictions, dtype=float)
    positive = scores[y == 1]
    negative = scores[y == 0]
    if not len(positive) or not len(negative):
        return None
    comparisons = positive[:, None] - negative[None, :]
    return float(((comparisons > 0).sum() + 0.5 * (comparisons == 0).sum()) / comparisons.size)


def _calibration_error(labels: list[int], predictions: list[float], bins: int = 10) -> float | None:
    if not labels:
        return None
    y = np.asarray(labels, dtype=float)
    scores = np.asarray(predictions, dtype=float)
    edges = np.linspace(0, 1, bins + 1)
    error = 0.0
    for idx in range(bins):
        mask = (scores >= edges[idx]) & (scores < edges[idx + 1] if idx < bins - 1 else scores <= edges[idx + 1])
        if mask.any():
            error += float(mask.mean()) * abs(float(scores[mask].mean()) - float(y[mask].mean()))
    return error


def _samples_in_range(prepared: dict, benchmark: dict | None, start: int, end: int) -> tuple[list[list[float]], list[int]]:
    features_rows: list[list[float]] = []
    labels: list[int] = []
    for data in prepared.values():
        history = data["history"]
        limit = min(end, len(history) - 5)
        for i in range(start, limit):
            features = sim.feature_vector(data, i, benchmark)
            if features is None:
                continue
            price = float(history["close"].iloc[i])
            forward_return = (float(history["close"].iloc[i + 5]) / price - 1) * 100
            features_rows.append(features)
            labels.append(1 if forward_return > 0.5 else 0)
    return features_rows, labels


def main() -> None:
    symbols = _symbols() or DEFAULT_SYMBOLS
    prepared, benchmark, skipped = _load_prepared(symbols)
    max_len = min(len(data["history"]) for data in prepared.values())
    folds = _walk_forward_folds(max_len, WALK_FORWARD_FOLDS, WALK_FORWARD_WINDOW_DAYS, min_start=65)
    if len(folds) < 2:
        raise SystemExit("Historico insuficiente para separar pelo menos 2 janelas (treino + holdout).")

    *train_folds, holdout_fold = folds
    train_x: list[list[float]] = []
    train_y: list[int] = []
    for start, end in train_folds:
        features_rows, labels = _samples_in_range(prepared, benchmark, start, end)
        train_x += features_rows
        train_y += labels
    holdout_x, holdout_y = _samples_in_range(prepared, benchmark, *holdout_fold)

    model = pm.fit(sim.FEATURE_NAMES, train_x, train_y)

    holdout_predictions = [pm.predict_proba(model, features) for features in holdout_x]
    if holdout_y:
        holdout_hits = sum(1 for pred, actual in zip(holdout_predictions, holdout_y) if (pred >= 0.5) == bool(actual))
        model["holdout_accuracy"] = round(holdout_hits / len(holdout_y), 4)
        model["holdout_positive_rate"] = round(sum(holdout_y) / len(holdout_y), 4)
        holdout_auc = _binary_auc(holdout_y, holdout_predictions)
        model["holdout_auc"] = round(holdout_auc, 4) if holdout_auc is not None else None
        model["holdout_brier"] = round(float(np.mean((np.asarray(holdout_predictions) - np.asarray(holdout_y)) ** 2)), 4)
        model["calibration_error"] = round(float(_calibration_error(holdout_y, holdout_predictions)), 4)
    else:
        model["holdout_accuracy"] = None
        model["holdout_positive_rate"] = None
        model["holdout_auc"] = None
        model["holdout_brier"] = None
        model["calibration_error"] = None
    model["holdout_samples"] = len(holdout_y)
    model["train_folds"] = [{"start_index": start, "end_index": end} for start, end in train_folds]
    model["holdout_fold"] = {"start_index": holdout_fold[0], "end_index": holdout_fold[1]}
    model["symbols"] = sorted(prepared)
    model["skipped"] = skipped
    model["trained_at"] = datetime.now(timezone.utc).isoformat()
    model["git_commit"] = _git_commit()
    model["dataset_sha256"] = _prepared_hash(prepared)
    model["config_sha256"] = _config_hash(
        {
            "features": sim.FEATURE_NAMES,
            "folds": model["train_folds"],
            "holdout": model["holdout_fold"],
            "symbols": model["symbols"],
            "market_history_period": sim.MARKET_HISTORY_PERIOD,
        }
    )

    failures = pm.candidate_promotion_failures(model)
    model["promotion_status"] = "REJECTED" if failures else "APPROVED"
    model["promotion_failures"] = failures
    pm.save_model(model, pm.CANDIDATE_MODEL_PATH)
    summary = {key: value for key, value in model.items() if key not in ("weights", "mean", "std")}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(
            "Candidato rejeitado; modelo ativo preservado. "
            f"Motivos: {', '.join(failures)}. Candidato: {pm.CANDIDATE_MODEL_PATH}"
        )
    pm.save_model(model)
    pm.record_training(model)
    print(f"\nModelo aprovado e salvo em {os.getenv('PROBABILITY_MODEL_PATH', str(pm.MODEL_PATH))}")


if __name__ == "__main__":
    main()
