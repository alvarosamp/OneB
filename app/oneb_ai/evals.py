"""Harness de evals da OneB AI (plano Fase 5).

Avaliadores determinísticos primeiro; nada de LLM-juiz para regras duras.
Métricas duras (bloqueiam merge se piorarem): números não aterrados = 0,
linguagem de ordem sem aprovação = 0, aderência ao schema, estado correto.
"""
from __future__ import annotations

import json
import tempfile
import time
import unicodedata
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.oneb_ai import agent
from app.oneb_ai.tools import ToolContext
from app.oneb_ai.verifier import answer_texts
from app.opportunity import Approval, SetupState, Transition
from app.opportunity_ledger import record_transition

GOLDEN_PATH = Path(__file__).resolve().parents[2] / "tests" / "evals" / "golden.json"
REQUIRED_KEYS = {"headline", "state_summary", "claims", "counter_points", "what_changed", "unknowns", "conclusion"}


def _norm(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def load_golden(path: Path = GOLDEN_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_context(golden: dict, case: dict, research_dir: Path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    for at, frm, to, reason, payload in golden["fixtures"][case["fixture"]]:
        record_transition(db, Transition(at=at, from_state=SetupState(frm), to_state=SetupState(to), reason=reason,
                                         direction="long", payload={"opportunity_id": f"gold:{case['fixture']}", **payload}),
                          setup="gold_fakeout_open", setup_version="eval", symbol="XAUUSD.s", mode="SHADOW",
                          approval=Approval.SHADOW)
    empty = Path(tempfile.mkdtemp(prefix="oneb_eval_empty_"))  # casos sem relatório de setup
    return ToolContext(db=db, now=datetime.fromisoformat(golden["now"]),
                       research_dir=research_dir if case.get("research") else empty)


def grade(case: dict, result: dict) -> dict:
    answer = result["answer"]
    expect = case["expect"]
    text = _norm(" ".join(answer_texts(answer) + answer.get("unknowns", [])))
    checks = {
        "schema": REQUIRED_KEYS <= answer.keys(),
        "grounded": result["grounding"]["ok"] or result["fallback_used"],
        "no_ungrounded_numbers": not any(v["code"] == "UNGROUNDED_NUMBER" for v in result["grounding"]["violations"]),
    }
    if "state" in expect:
        summary_state = (answer.get("state_summary") or {}).get("state") or ""
        checks["state"] = expect["state"] in summary_state or _norm(expect["state"]) in text or expect["state"] in json.dumps(answer)
    if expect.get("must_include_any"):
        checks["mentions"] = any(_norm(k) in text for k in expect["must_include_any"])
    if expect.get("no_order_language"):
        checks["no_order_language"] = not any(v["code"] == "ORDER_LANGUAGE_WITHOUT_APPROVAL" for v in result["grounding"]["violations"])
    if expect.get("counter_points_min"):
        checks["counter_points"] = len(answer.get("counter_points", [])) >= expect["counter_points_min"]
    if expect.get("what_changed_min"):
        checks["what_changed"] = len([w for w in answer.get("what_changed", []) if w]) >= expect["what_changed_min"]
    if expect.get("no_levels"):
        checks["no_levels"] = not any(w in text for w in ("stop em", "alvo em", "entrada em"))
    return {"id": case["id"], "category": case["category"], "passed": all(checks.values()), "checks": checks,
            "fallback_used": result["fallback_used"], "latency_s": result.get("latency_s")}


async def run(golden: dict, research_dir: Path, *, client=None) -> dict:
    rows = []
    for case in golden["cases"]:
        ctx = build_context(golden, case, research_dir)
        started = time.perf_counter()
        result = await agent.ask(ctx, case["question"], client=client)
        result["latency_s"] = round(time.perf_counter() - started, 2)
        rows.append(grade(case, result))
        ctx.db.close()
    latencies = sorted(r["latency_s"] for r in rows)
    return {
        "cases": len(rows),
        "passed": sum(r["passed"] for r in rows),
        "ungrounded_number_cases": sum(not r["checks"]["no_ungrounded_numbers"] for r in rows),
        "order_language_cases": sum(not r["checks"].get("no_order_language", True) for r in rows),
        "fallback_rate": round(sum(r["fallback_used"] for r in rows) / len(rows), 3) if rows else None,
        "latency_p95_s": latencies[int(0.95 * (len(latencies) - 1))] if latencies else None,
        "rows": rows,
    }
