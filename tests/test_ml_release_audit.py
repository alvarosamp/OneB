from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd

from app.ml_release_audit import audit_artifact_freshness, audit_dataset, audit_model, audit_release_evidence
from app.probability_model import candidate_promotion_failures


def _dataset(path: Path, *, purge: bool) -> Path:
    rows = []
    dates = pd.bdate_range("2025-01-01", periods=18)
    for symbol, offset in (("AAA", 0.0), ("BBB", 10.0)):
        closes = pd.Series(range(100, 118), dtype=float) + offset
        for i, date in enumerate(dates[:-2]):
            split = "train" if i < 6 else "validation" if i < 11 else "test"
            if purge and i in {4, 5, 9, 10}:
                continue
            close = float(closes.iloc[i])
            rows.append(
                {
                    "symbol": symbol,
                    "date": date,
                    "split": split,
                    "open": close,
                    "high": close + 1,
                    "low": close - 1,
                    "close": close,
                    "volume": 1000,
                    "fwd_return_2d": (float(closes.iloc[i + 2]) / close - 1) * 100,
                }
            )
    pd.DataFrame(rows).to_csv(path, index=False)
    path.with_suffix(path.suffix + ".manifest.json").write_text("{}", encoding="utf-8")
    return path


def _work_path(name: str) -> Path:
    directory = Path("tmp") / f"ml-release-audit-{uuid4().hex}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / name


def test_dataset_gate_detects_label_overlap_at_split_boundaries():
    result = audit_dataset(_dataset(_work_path("dataset.csv"), purge=False))
    assert "LABEL_BOUNDARY_LEAKAGE" in {item["code"] for item in result["findings"]}


def test_dataset_gate_accepts_purged_fixture_boundary():
    result = audit_dataset(_dataset(_work_path("dataset.csv"), purge=True))
    codes = {item["code"] for item in result["findings"]}
    assert "LABEL_BOUNDARY_LEAKAGE" not in codes


def test_model_gate_rejects_accuracy_below_majority_baseline():
    path = _work_path("model.json")
    path.write_text(
        json.dumps(
            {
                "holdout_accuracy": 0.48,
                "holdout_positive_rate": 0.49,
                "trained_at": "2025-01-01T00:00:00Z",
                "git_commit": "abc",
                "dataset_sha256": "def",
                "config_sha256": "ghi",
                "holdout_auc": 0.49,
                "holdout_brier": 0.26,
                "calibration_error": 0.2,
            }
        ),
        encoding="utf-8",
    )
    result = audit_model(path)
    assert "MODEL_BELOW_NAIVE_BASELINE" in {item["code"] for item in result["findings"]}


def test_freshness_gate_fails_closed_for_missing_artifact():
    result = audit_artifact_freshness([_work_path("missing.json")], now=datetime.now(timezone.utc))
    assert result["status"] == "FAIL"
    assert result["findings"][0]["code"] == "REQUIRED_ARTIFACT_MISSING"


def test_model_promotion_is_fail_closed():
    failures = candidate_promotion_failures(
        {
            "holdout_samples": 1000,
            "holdout_accuracy": 0.48,
            "holdout_positive_rate": 0.49,
            "holdout_auc": 0.49,
        }
    )
    assert "holdout_accuracy<=majority_baseline" in failures
    assert any(item.endswith("_missing") for item in failures)


def test_failed_data_and_automation_reports_block_release():
    root = _work_path("root")
    (root / "data").mkdir(parents=True)
    (root / "data/data_reliability_gate.json").write_text(
        json.dumps({"status": "FAIL", "failure_count": 2}), encoding="utf-8"
    )
    (root / "data/automation_readiness_report.json").write_text(
        json.dumps({"verdict": "HUMAN_APPROVAL_REQUIRED", "long": {}, "short": {}}), encoding="utf-8"
    )
    result = audit_release_evidence(root)
    codes = {item["code"] for item in result["findings"]}
    assert {"DATA_RELIABILITY_GATE_FAILED", "AUTOMATION_GATE_FAILED"} <= codes
