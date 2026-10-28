"""Boletim de confiabilidade da OneB AI: roda as avaliações e grava o resultado para a página 'Por que confiar'.

    python scripts/run_ai_evals.py

- golden: perguntas com resposta esperada (estado, recusa, risco, plano...), regras duras: 0 número sem fonte, 0 ordem;
- roteamento: a mesma pergunta escrita de vários jeitos cai na resposta certa.
Grava app/research_results/ai_reliability.json. Roda sem LLM (respostas determinísticas das ferramentas).
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.oneb_ai import agent, evals  # noqa: E402


def main() -> None:
    agent.is_configured = lambda: False
    golden = evals.load_golden()
    g = asyncio.run(evals.run(golden, Path(tempfile.mkdtemp())))
    r = asyncio.run(evals.run_routing(golden))
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "golden": {"cases": g["cases"], "passed": g["passed"], "ungrounded_number_cases": g["ungrounded_number_cases"],
                   "order_language_cases": g["order_language_cases"]},
        "routing": {"cases": r["cases"], "passed": r["passed"], "routes": len({x["route"] for x in r["rows"]})},
        "failures": [x["id"] for x in g["rows"] if not x["passed"]] + [x["question"] for x in r["rows"] if not x["passed"]],
    }
    path = ROOT / "app" / "research_results" / "ai_reliability.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "generated_at"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
