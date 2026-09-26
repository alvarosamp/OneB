"""Independent, fail-closed checks for ML/research release artifacts.

This module deliberately does not import the trading or data-fetching stack.  It
audits files already produced by that stack, so a broken provider, scheduler or
model cannot make its own release gate pass.  The gate is intended for CI and
release review; it does not claim that passing these mechanical checks proves an
economic edge.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

OHLCV = ("open", "high", "low", "close", "volume")
SPLIT_ORDER = ("train", "validation", "test")
# Linhas removidas de proposito pelo purge/embargo nas fronteiras de split.
# Elas permanecem no arquivo para que a auditoria consiga medir as distancias
# no calendario original -- se fossem apagadas, os blocos voltariam a parecer
# contiguos e o proprio teste de leakage passaria por engano.
PURGED_SPLIT = "purged"
KNOWN_SPLITS = (*SPLIT_ORDER, PURGED_SPLIT)


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finding(code: str, severity: str, message: str, **evidence: Any) -> Finding:
    return Finding(code, severity, message, evidence)


def audit_dataset(dataset_path: Path, summary_path: Path | None = None) -> dict[str, Any]:
    findings: list[Finding] = []
    if not dataset_path.exists():
        findings.append(_finding("DATASET_MISSING", "CRITICAL", "Dataset de pesquisa ausente.", path=str(dataset_path)))
        return {"status": "FAIL", "findings": [item.to_dict() for item in findings]}

    frame = pd.read_csv(dataset_path, low_memory=False)
    required = {"symbol", "date", "split", *OHLCV}
    missing_columns = sorted(required - set(frame.columns))
    if missing_columns:
        findings.append(
            _finding(
                "SCHEMA_MISSING_COLUMNS",
                "CRITICAL",
                "O dataset não satisfaz o contrato mínimo.",
                columns=missing_columns,
            )
        )
        return {
            "status": "FAIL",
            "path": str(dataset_path),
            "sha256": sha256_file(dataset_path),
            "rows": len(frame),
            "findings": [item.to_dict() for item in findings],
        }

    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    invalid_dates = int(frame["date"].isna().sum())
    duplicate_keys = int(frame.duplicated(["symbol", "date"]).sum())
    missing_ohlcv = int(frame[list(OHLCV)].isna().sum().sum())
    bad_ohlc = (
        (frame["high"] < frame[["open", "close", "low"]].max(axis=1))
        | (frame["low"] > frame[["open", "close", "high"]].min(axis=1))
        | (frame[["open", "high", "low", "close"]] <= 0).any(axis=1)
        | (frame["volume"] < 0)
    )
    if invalid_dates:
        findings.append(_finding("INVALID_DATES", "CRITICAL", "Há datas inválidas.", rows=invalid_dates))
    if duplicate_keys:
        findings.append(_finding("DUPLICATE_SYMBOL_DATE", "HIGH", "Há candles duplicados.", rows=duplicate_keys))
    if missing_ohlcv:
        findings.append(_finding("MISSING_OHLCV", "HIGH", "Há células OHLCV ausentes.", cells=missing_ohlcv))
    if int(bad_ohlc.sum()):
        findings.append(_finding("INVALID_OHLC", "CRITICAL", "Há candles economicamente inválidos.", rows=int(bad_ohlc.sum())))

    valid = frame.dropna(subset=["date"]).sort_values(["symbol", "date"]).copy()
    split_dates: dict[str, dict[str, str | int | None]] = {}
    for split in SPLIT_ORDER:
        dates = valid.loc[valid["split"] == split, "date"]
        split_dates[split] = {
            "rows": int(len(dates)),
            "start": dates.min().date().isoformat() if len(dates) else None,
            "end": dates.max().date().isoformat() if len(dates) else None,
        }
    purged_rows = int((valid["split"].astype(str) == PURGED_SPLIT).sum())
    split_dates[PURGED_SPLIT] = {
        "rows": purged_rows,
        "start": None,
        "end": None,
        "note": "linhas removidas pelo purge/embargo nas fronteiras",
    }
    unknown_splits = sorted(set(valid["split"].dropna().astype(str)) - set(KNOWN_SPLITS))
    if unknown_splits or any(split_dates[name]["rows"] == 0 for name in SPLIT_ORDER):
        findings.append(
            _finding(
                "INVALID_SPLITS",
                "CRITICAL",
                "Treino, validação e teste não estão todos bem definidos.",
                unknown=unknown_splits,
                splits=split_dates,
            )
        )
    else:
        train_end = valid.loc[valid["split"] == "train", "date"].max()
        validation_start = valid.loc[valid["split"] == "validation", "date"].min()
        validation_end = valid.loc[valid["split"] == "validation", "date"].max()
        test_start = valid.loc[valid["split"] == "test", "date"].min()
        if not (train_end < validation_start <= validation_end < test_start):
            findings.append(_finding("NON_TEMPORAL_SPLIT", "CRITICAL", "Os splits se sobrepõem ou não são temporais.", splits=split_dates))

    horizons = sorted(
        int(name.removeprefix("fwd_return_").removesuffix("d"))
        for name in valid.columns
        if name.startswith("fwd_return_") and name.endswith("d") and name.removeprefix("fwd_return_").removesuffix("d").isdigit()
    )
    boundary_violations: dict[str, Any] = {}
    if horizons and not unknown_splits:
        for horizon in horizons:
            for left, right in zip(SPLIT_ORDER, SPLIT_ORDER[1:], strict=False):
                left_end = valid.loc[valid["split"] == left, "date"].max()
                right_start = valid.loc[valid["split"] == right, "date"].min()
                if pd.isna(left_end) or pd.isna(right_start):
                    continue
                business_day_gap = int(np.busday_count(left_end.date(), right_start.date()))
                if business_day_gap <= horizon:
                    boundary_violations[f"{left}_to_{right}_{horizon}d"] = {
                        "business_day_gap": business_day_gap,
                        "required_minimum": horizon + 1,
                    }
    if boundary_violations:
        findings.append(
            _finding(
                "LABEL_BOUNDARY_LEAKAGE",
                "CRITICAL",
                "Labels futuros atravessam fronteiras de split; falta purge compatível com o maior horizonte.",
                violations=boundary_violations,
                max_horizon_days=max(horizons),
            )
        )

    label_mismatches: dict[str, int] = {}
    for horizon in horizons:
        column = f"fwd_return_{horizon}d"
        expected = valid.groupby("symbol", sort=False)["close"].shift(-horizon) / valid["close"] * 100 - 100
        comparable = expected.notna() & valid[column].notna()
        mismatches = int((~np.isclose(expected[comparable], valid.loc[comparable, column], rtol=1e-7, atol=1e-7)).sum())
        if mismatches:
            label_mismatches[column] = mismatches
    if label_mismatches:
        findings.append(
            _finding(
                "LABEL_RECOMPUTATION_MISMATCH",
                "CRITICAL",
                "Labels persistidos não são reproduzíveis a partir dos closes persistidos.",
                mismatches=label_mismatches,
            )
        )

    manifest_path = dataset_path.with_suffix(dataset_path.suffix + ".manifest.json")
    if not manifest_path.exists():
        findings.append(
            _finding(
                "DATASET_MANIFEST_MISSING",
                "HIGH",
                "Não há manifesto imutável ligando dataset, fontes, código e configuração.",
                expected_path=str(manifest_path),
            )
        )

    summary_hash = None
    if summary_path and summary_path.exists():
        summary_hash = sha256_file(summary_path)
    return {
        "status": "FAIL" if findings else "PASS",
        "path": str(dataset_path),
        "sha256": sha256_file(dataset_path),
        "summary_sha256": summary_hash,
        "rows": int(len(frame)),
        "symbols": int(frame["symbol"].nunique()),
        "date_start": valid["date"].min().date().isoformat() if len(valid) else None,
        "date_end": valid["date"].max().date().isoformat() if len(valid) else None,
        "split_dates": split_dates,
        "quality": {
            "invalid_dates": invalid_dates,
            "duplicate_symbol_dates": duplicate_keys,
            "missing_ohlcv_cells": missing_ohlcv,
            "invalid_ohlc_rows": int(bad_ohlc.sum()),
        },
        "findings": [item.to_dict() for item in findings],
    }


def audit_model(model_path: Path) -> dict[str, Any]:
    findings: list[Finding] = []
    if not model_path.exists():
        findings.append(_finding("MODEL_MISSING", "CRITICAL", "Artefato do modelo ausente.", path=str(model_path)))
        return {"status": "FAIL", "findings": [item.to_dict() for item in findings]}
    try:
        model = json.loads(model_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(_finding("MODEL_INVALID", "CRITICAL", "Artefato do modelo ilegível.", error=str(exc)))
        return {"status": "FAIL", "findings": [item.to_dict() for item in findings]}

    accuracy = model.get("holdout_accuracy")
    positive_rate = model.get("holdout_positive_rate")
    baseline = max(float(positive_rate), 1 - float(positive_rate)) if positive_rate is not None else None
    if accuracy is None:
        findings.append(_finding("MODEL_NO_HOLDOUT", "CRITICAL", "Modelo não registra desempenho holdout."))
    elif baseline is not None and float(accuracy) <= baseline:
        findings.append(
            _finding(
                "MODEL_BELOW_NAIVE_BASELINE",
                "CRITICAL",
                "A acurácia holdout não supera a classe majoritária.",
                holdout_accuracy=float(accuracy),
                majority_baseline=round(baseline, 4),
            )
        )
    required_provenance = ("trained_at", "git_commit", "dataset_sha256", "config_sha256")
    missing_provenance = [key for key in required_provenance if not model.get(key)]
    if missing_provenance:
        findings.append(
            _finding(
                "MODEL_PROVENANCE_INCOMPLETE",
                "HIGH",
                "Não é possível ligar o modelo a dados, código e configuração exatos.",
                missing=missing_provenance,
            )
        )
    missing_metrics = [key for key in ("holdout_auc", "holdout_brier", "calibration_error") if model.get(key) is None]
    if missing_metrics:
        findings.append(
            _finding(
                "MODEL_VALIDATION_INCOMPLETE",
                "HIGH",
                "Faltam métricas de discriminação e calibração probabilística.",
                missing=missing_metrics,
            )
        )
    return {
        "status": "FAIL" if findings else "PASS",
        "path": str(model_path),
        "sha256": sha256_file(model_path),
        "train_samples": model.get("train_samples"),
        "holdout_samples": model.get("holdout_samples"),
        "train_accuracy": model.get("train_accuracy"),
        "holdout_accuracy": accuracy,
        "majority_baseline": round(baseline, 4) if baseline is not None else None,
        "findings": [item.to_dict() for item in findings],
    }


def audit_artifact_freshness(paths: list[Path], *, now: datetime, max_age_days: int = 7) -> dict[str, Any]:
    rows = []
    findings: list[Finding] = []
    now_utc = now.astimezone(timezone.utc)
    for path in paths:
        if not path.exists():
            rows.append({"path": str(path), "exists": False, "age_days": None})
            findings.append(_finding("REQUIRED_ARTIFACT_MISSING", "HIGH", "Artefato operacional ausente.", path=str(path)))
            continue
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        age_days = (now_utc - modified).total_seconds() / 86400
        rows.append({"path": str(path), "exists": True, "modified_at": modified.isoformat(), "age_days": round(age_days, 2)})
        if age_days > max_age_days:
            findings.append(
                _finding(
                    "STALE_RELEASE_ARTIFACT",
                    "HIGH",
                    "Artefato excede a idade máxima para decisão de lançamento.",
                    path=str(path),
                    age_days=round(age_days, 2),
                    max_age_days=max_age_days,
                )
            )
    return {"status": "FAIL" if findings else "PASS", "artifacts": rows, "findings": [item.to_dict() for item in findings]}


def audit_release_evidence(root: Path) -> dict[str, Any]:
    """Check the verdicts and realized outcomes, not just file presence."""
    findings: list[Finding] = []
    metrics: dict[str, Any] = {}

    data_gate_path = root / "data/data_reliability_gate.json"
    if data_gate_path.exists():
        gate = json.loads(data_gate_path.read_text(encoding="utf-8"))
        metrics["data_gate"] = {"status": gate.get("status"), "failure_count": gate.get("failure_count")}
        if gate.get("status") != "PASS":
            findings.append(
                _finding(
                    "DATA_RELIABILITY_GATE_FAILED",
                    "CRITICAL",
                    "O gate de dados vigente reprova os inputs de pesquisa.",
                    status=gate.get("status"),
                    failure_count=gate.get("failure_count"),
                )
            )

    automation_path = root / "data/automation_readiness_report.json"
    if automation_path.exists():
        automation = json.loads(automation_path.read_text(encoding="utf-8"))
        metrics["automation"] = {
            "verdict": automation.get("verdict"),
            "long_passed_folds": (automation.get("long") or {}).get("aggregate", {}).get("passed_folds"),
            "short_passed_folds": (automation.get("short") or {}).get("aggregate", {}).get("passed_folds"),
        }
        if automation.get("verdict") != "AUTOMATION_READY":
            findings.append(
                _finding(
                    "AUTOMATION_GATE_FAILED",
                    "CRITICAL",
                    "A validação de estratégia não autoriza automação.",
                    **metrics["automation"],
                )
            )

    replay_path = root / "data/paper_simulator_deep_replay.json"
    if replay_path.exists():
        replay = json.loads(replay_path.read_text(encoding="utf-8"))
        metrics["deep_replay"] = {
            key: replay.get(key) for key in ("return_pct", "closed_trades", "win_rate_pct", "profit_factor", "max_drawdown_pct")
        }
        if (replay.get("return_pct") or 0) <= 0 or (replay.get("profit_factor") or 0) <= 1:
            findings.append(
                _finding(
                    "DEEP_REPLAY_FAILED",
                    "HIGH",
                    "O replay persistido não demonstra vantagem líquida.",
                    **metrics["deep_replay"],
                )
            )

    db_path = root / "data/nasdaq_monitor.db"
    if db_path.exists():
        try:
            connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
            total, hits, false_positives = connection.execute(
                "SELECT count(*), "
                "sum(CASE WHEN outcome_status='HIT' THEN 1 ELSE 0 END), "
                "sum(CASE WHEN outcome_status='FALSE_POSITIVE' THEN 1 ELSE 0 END) "
                "FROM recommendation_decisions WHERE outcome_status!='PENDING'"
            ).fetchone()
            connection.close()
            total = int(total or 0)
            hits = int(hits or 0)
            false_positives = int(false_positives or 0)
            win_rate = hits / total if total else None
            metrics["online_outcomes"] = {
                "evaluated": total,
                "hits": hits,
                "false_positives": false_positives,
                "win_rate": round(win_rate, 4) if win_rate is not None else None,
            }
            if total and win_rate is not None and win_rate < 0.45:
                findings.append(
                    _finding(
                        "ONLINE_PERFORMANCE_BELOW_GATE",
                        "HIGH",
                        "Outcomes registrados estão abaixo do piso operacional.",
                        **metrics["online_outcomes"],
                    )
                )
        except (sqlite3.Error, OSError) as exc:
            findings.append(_finding("ONLINE_EVIDENCE_UNREADABLE", "HIGH", "Não foi possível auditar outcomes online.", error=str(exc)))

    return {"status": "FAIL" if findings else "PASS", "metrics": metrics, "findings": [item.to_dict() for item in findings]}


def build_release_audit(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    dataset = audit_dataset(
        root / "data/research/research_dataset_v1.csv",
        root / "data/research/research_dataset_v1.summary.json",
    )
    model = audit_model(root / "data/probability_model.json")
    freshness = audit_artifact_freshness(
        [
            root / "data/data_reliability_gate.json",
            root / "data/automation_readiness_report.json",
            root / "data/probability_model.json",
            root / "data/research/research_dataset_v1.summary.json",
        ],
        now=now,
    )
    evidence = audit_release_evidence(root)
    findings = dataset["findings"] + model["findings"] + freshness["findings"] + evidence["findings"]
    severities = {name: sum(item["severity"] == name for item in findings) for name in ("CRITICAL", "HIGH", "MEDIUM", "LOW")}
    return {
        "schema_version": "ml-release-audit-v1",
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "verdict": "NOT_READY",
        "release_allowed": False,
        "severity_counts": severities,
        "dataset": dataset,
        "model": model,
        "freshness": freshness,
        "release_evidence": evidence,
        "findings": findings,
        "limitations": [
            "Checks mecânicos não demonstram edge econômico nem substituem validação externa.",
            "Licença, point-in-time e política de revisões precisam de evidência contratual da fonte.",
            "O gate não consulta rede; ele audita somente artefatos persistidos.",
        ],
    }
