"""Generate the independent fail-closed ML release audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ml_release_audit import build_release_audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Audita artefatos de dados/ML antes de lançamento.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("data/ml_release_audit.json"))
    args = parser.parse_args()
    report = build_release_audit(args.root.resolve())
    output = args.output if args.output.is_absolute() else args.root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "verdict": report["verdict"],
        "release_allowed": report["release_allowed"],
        "severity_counts": report["severity_counts"],
        "output": str(output),
    }, ensure_ascii=False, indent=2))
    if not report["release_allowed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
