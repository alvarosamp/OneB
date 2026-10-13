"""Roda o conjunto golden da OneB AI.

    python scripts/run_ai_evals.py            # modo template (sem LLM, sem custo): valida o harness
    python scripts/run_ai_evals.py --live     # usa o agente real (Anthropic) — GASTA API

Use --live ao trocar modelo/prompt e anexe o relatório ao PR. Regras duras:
`ungrounded_number_cases` e `order_language_cases` precisam ser 0.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.oneb_ai import agent, evals  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--research-dir", type=Path, default=ROOT / "output" / "setup_research")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.live and not agent.is_configured():
        raise SystemExit("--live exige LLM_PROVIDER=anthropic e ANTHROPIC_API_KEY.")
    if not args.live:
        agent.is_configured = lambda: False  # força o caminho template
    report = asyncio.run(evals.run(evals.load_golden(), args.research_dir))
    report["mode"] = "live" if args.live else "template"
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    output = args.output or ROOT / "output" / "ai_evals" / f"evals_{report['mode']}_{datetime.now(timezone.utc):%Y%m%d_%H%M}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))
    for row in report["rows"]:
        failed = [k for k, v in row["checks"].items() if not v]
        print(f"{'PASS' if row['passed'] else 'FAIL'}  {row['id']:<12} {row['category']:<12} {', '.join(failed)}")
    hard_fail = report["ungrounded_number_cases"] or report["order_language_cases"]
    raise SystemExit(1 if hard_fail else 0)


if __name__ == "__main__":
    main()
