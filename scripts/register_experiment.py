from __future__ import annotations

import argparse
import json
import subprocess

from app.research_registry import create_experiment, save_experiment


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def _json_arg(raw: str) -> dict:
    if not raw:
        return {}
    return json.loads(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description="Register a reproducible research experiment.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--hypothesis", required=True)
    parser.add_argument("--status", default="RECORDED")
    parser.add_argument("--dataset-version", default="unknown")
    parser.add_argument("--features", default="", help="Comma-separated feature names.")
    parser.add_argument("--universe", default="", help="Comma-separated symbols.")
    parser.add_argument("--training-period", default="")
    parser.add_argument("--validation-period", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--metrics-json", default="")
    parser.add_argument("--artifacts-json", default="")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    record = create_experiment(
        name=args.name,
        hypothesis=args.hypothesis,
        status=args.status,
        git_commit=_git_commit(),
        dataset_version=args.dataset_version,
        feature_set=[item.strip() for item in args.features.split(",") if item.strip()],
        universe=[item.strip().upper() for item in args.universe.split(",") if item.strip()],
        training_period=args.training_period,
        validation_period=args.validation_period,
        model=args.model,
        metrics=_json_arg(args.metrics_json),
        artifacts=_json_arg(args.artifacts_json),
        notes=args.notes,
    )
    path = save_experiment(record)
    print(json.dumps({"saved": str(path), **record.to_dict()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
