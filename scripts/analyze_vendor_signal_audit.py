"""Find revisions to closed-bar buffers in tester-only VendorSignalAudit output.

Changes are diagnostic, not proof that a trade signal repaints: buffers may hold
non-signal series. No changes is not proof of causality outside the sampled window.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def analyze(path: Path) -> dict:
    previous: dict[tuple[str, int], tuple[str, float | None, str]] = {}
    checks = changes = missing = rows = 0
    examples = []
    by_buffer: dict[int, dict[str, int]] = {}
    first_observed = last_observed = None
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream, delimiter=";"):
            rows += 1
            observed = row["observed_at"]
            first_observed = observed if first_observed is None else min(first_observed, observed)
            last_observed = observed if last_observed is None else max(last_observed, observed)
            buffer = int(row["buffer"])
            stats = by_buffer.setdefault(buffer, {"valid_rows": 0, "unavailable_rows": 0, "rechecks": 0, "changes": 0})
            status = row["status"]
            if status == "unavailable":
                missing += 1
                stats["unavailable_rows"] += 1
                continue
            if status not in ("ok", "empty"):
                raise ValueError(f"Unknown status: {status}")
            if int(row["shift"]) < 1:
                raise ValueError("Audit contains a forming-bar observation")
            if row["bar_time"] >= observed:
                raise ValueError("Bar time must precede observation time")
            value = float(row["value"]) if status == "ok" else None
            if value is not None and not math.isfinite(value):
                raise ValueError("Nonfinite value marked ok")
            key = (row["bar_time"], buffer)
            stats["valid_rows"] += 1
            if key in previous:
                old_status, old_value, old_observed = previous[key]
                if observed < old_observed:
                    raise ValueError("Observations are not chronological")
                checks += 1
                stats["rechecks"] += 1
                changed = status != old_status or (
                    status == "ok" and not math.isclose(value, old_value, rel_tol=1e-10, abs_tol=1e-10)
                )
                if changed:
                    changes += 1
                    stats["changes"] += 1
                    if len(examples) < 30:
                        examples.append({"bar_time": key[0], "buffer": buffer, "observed_at": observed,
                                         "before": old_value, "after": value,
                                         "before_status": old_status, "after_status": status})
            previous[key] = (status, value, observed)
    return {"source": str(path.resolve()), "rows": rows, "first_observed": first_observed,
            "last_observed": last_observed, "rechecks": checks, "closed_bar_buffer_changes": changes,
            "unavailable_rows": missing, "by_buffer": by_buffer, "examples": examples,
            "classification": "experimental",
            "warning": "No profitability inference. Buffer revisions require mapping to entry/exit signals. "
                       "Zero revisions does not certify absence of repaint or intrabar changes."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("buffers", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = json.dumps(analyze(args.buffers), ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
