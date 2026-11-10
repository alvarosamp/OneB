"""Build the first clean feature/label dataset for AI research.

Run:
    python -m scripts.build_research_dataset

Useful overrides:
    python -m scripts.build_research_dataset --period 2y --symbols AAPL,MSFT,NVDA,QQQ
    python -m scripts.build_research_dataset --refresh
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.research_dataset import ResearchDatasetConfig, build_research_dataset


def _symbols(raw: str) -> list[str]:
    return sorted({symbol.strip().upper() for symbol in raw.split(",") if symbol.strip()})


def main() -> None:
    defaults = ResearchDatasetConfig.from_env()
    parser = argparse.ArgumentParser(description="Build ResearchDataset v1 for AI experiments.")
    parser.add_argument("--symbols", default=",".join(defaults.symbols), help="Comma-separated stock symbols.")
    parser.add_argument("--benchmark", default=defaults.benchmark_symbol, help="Benchmark symbol for relative strength.")
    parser.add_argument("--period", default=defaults.period, help="Market data period, for example 2y or 5y.")
    parser.add_argument("--min-rows", type=int, default=defaults.min_rows, help="Minimum candles required per symbol.")
    parser.add_argument("--output-dir", default=str(defaults.output_dir), help="Output directory.")
    parser.add_argument("--refresh", action="store_true", default=defaults.refresh, help="Refresh provider data before building.")
    args = parser.parse_args()

    config = ResearchDatasetConfig(
        symbols=_symbols(args.symbols),
        benchmark_symbol=args.benchmark.upper().strip(),
        period=args.period,
        min_rows=args.min_rows,
        output_dir=Path(args.output_dir),
        refresh=args.refresh,
    )
    panel, summary = build_research_dataset(config)
    quality = summary["dataset_quality"]
    outputs = summary.get("outputs", {})

    print(json.dumps({
        "status": quality["status"],
        "rows": len(panel),
        "symbols": quality.get("symbols", 0),
        "features": quality.get("feature_count", 0),
        "issues": quality.get("issues", []),
        "dataset": outputs.get("dataset"),
        "summary": outputs.get("summary"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
