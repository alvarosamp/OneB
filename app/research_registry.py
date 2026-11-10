from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

REGISTRY_DIR = Path(os.getenv("RESEARCH_REGISTRY_DIR", "data/research_registry"))
REGISTRY_LOG = REGISTRY_DIR / "experiments.jsonl"


@dataclass(frozen=True)
class ExperimentRecord:
    experiment_id: str
    name: str
    status: str
    hypothesis: str
    git_commit: str = "unknown"
    dataset_version: str = "unknown"
    feature_set: list[str] = field(default_factory=list)
    universe: list[str] = field(default_factory=list)
    training_period: str = ""
    validation_period: str = ""
    model: str = ""
    hyperparameters: dict = field(default_factory=dict)
    transaction_costs: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    artifacts: dict = field(default_factory=dict)
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


def create_experiment(
    name: str,
    hypothesis: str,
    *,
    status: str = "RECORDED",
    git_commit: str = "unknown",
    dataset_version: str = "unknown",
    feature_set: list[str] | None = None,
    universe: list[str] | None = None,
    training_period: str = "",
    validation_period: str = "",
    model: str = "",
    hyperparameters: dict | None = None,
    transaction_costs: dict | None = None,
    metrics: dict | None = None,
    artifacts: dict | None = None,
    notes: str = "",
) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id=f"EXP-{uuid4().hex[:8].upper()}",
        name=name,
        status=status,
        hypothesis=hypothesis,
        git_commit=git_commit,
        dataset_version=dataset_version,
        feature_set=feature_set or [],
        universe=universe or [],
        training_period=training_period,
        validation_period=validation_period,
        model=model,
        hyperparameters=hyperparameters or {},
        transaction_costs=transaction_costs or {},
        metrics=metrics or {},
        artifacts=artifacts or {},
        notes=notes,
    )


def save_experiment(record: ExperimentRecord, registry_dir: Path = REGISTRY_DIR) -> Path:
    registry_dir.mkdir(parents=True, exist_ok=True)
    payload = record.to_dict()
    path = registry_dir / f"{record.experiment_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with (registry_dir / "experiments.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return path


def list_experiments(registry_dir: Path = REGISTRY_DIR, limit: int = 50) -> list[dict]:
    log_path = registry_dir / "experiments.jsonl"
    if not log_path.exists():
        return []
    rows = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]
