from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from typing import Any

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "nasdaq_monitor.db"


def _read_json(name: str) -> dict[str, Any] | list[Any] | None:
    path = DATA_DIR / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _db_counts() -> dict[str, Any]:
    if not DB_PATH.exists():
        return {"available": False, "reason": "Banco local nao encontrado."}
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        tables = [row["name"] for row in con.execute("select name from sqlite_master where type='table' order by name")]
        counts = {}
        for table in tables:
            try:
                counts[table] = con.execute(f"select count(*) as c from {table}").fetchone()["c"]
            except sqlite3.DatabaseError:
                counts[table] = None
        active_watchlist = []
        if "watchlist_items" in tables:
            watchlist_columns = {
                row["name"] for row in con.execute("pragma table_info(watchlist_items)")
            }
            select_columns = ["symbol", "active"]
            if "name" in watchlist_columns:
                select_columns.insert(1, "name")
            active_watchlist = [
                dict(row)
                for row in con.execute(
                    f"select {', '.join(select_columns)} from watchlist_items where active = 1 order by symbol limit 50"
                )
            ]
        checked_decisions = 0
        decision_win_rate = None
        if "recommendation_decisions" in tables:
            rows = con.execute(
                "select outcome_status from recommendation_decisions "
                "where action in ('BUY_CONTROLLED','WATCH_BUY','SELL_SHORT','WATCH_SHORT') "
                "and outcome_status != 'PENDING'"
            ).fetchall()
            checked_decisions = len(rows)
            if rows:
                wins = sum(1 for row in rows if row["outcome_status"] == "HIT")
                decision_win_rate = round(wins / len(rows) * 100, 2)
        return {
            "available": True,
            "tables": tables,
            "counts": counts,
            "active_watchlist": active_watchlist,
            "checked_decisions": checked_decisions,
            "decision_win_rate_pct": decision_win_rate,
        }
    finally:
        con.close()


def _probability_model_audit() -> dict[str, Any]:
    model = _read_json("probability_model.json")
    history = _read_json("probability_model_history.json") or []
    if not isinstance(model, dict):
        return {"available": False, "risk": "HIGH", "reason": "Modelo probabilistico nao encontrado."}

    train_accuracy = model.get("train_accuracy")
    holdout_accuracy = model.get("holdout_accuracy")
    holdout_positive_rate = model.get("holdout_positive_rate")
    baseline = None
    if holdout_positive_rate is not None:
        baseline = max(float(holdout_positive_rate), 1 - float(holdout_positive_rate))

    warnings = []
    if holdout_accuracy is None:
        warnings.append("Sem holdout; nao usar como prova de qualidade.")
    elif baseline is not None and float(holdout_accuracy) <= baseline:
        warnings.append("Holdout nao supera baseline de classe majoritaria.")
    if train_accuracy is not None and holdout_accuracy is not None and float(train_accuracy) - float(holdout_accuracy) > 0.04:
        warnings.append("Gap treino-holdout sugere overfit ou feature fraca fora da amostra.")

    weights = model.get("weights") or []
    features = model.get("features") or []
    weighted_features = sorted(
        [
            {"feature": feature, "weight": round(float(weight), 4), "abs_weight": round(abs(float(weight)), 4)}
            for feature, weight in zip(features, weights)
            if isinstance(weight, (int, float))
        ],
        key=lambda row: row["abs_weight"],
        reverse=True,
    )
    return {
        "available": True,
        "risk": "MEDIUM" if warnings else "LOW",
        "features": features,
        "train_samples": model.get("train_samples"),
        "holdout_samples": model.get("holdout_samples"),
        "train_accuracy": train_accuracy,
        "holdout_accuracy": holdout_accuracy,
        "holdout_baseline_accuracy": round(baseline, 4) if baseline is not None else None,
        "holdout_positive_rate": holdout_positive_rate,
        "top_weights": weighted_features[:8],
        "history": history,
        "warnings": warnings,
    }


def _calibration_audit(name: str) -> dict[str, Any]:
    data = _read_json(name)
    if not isinstance(data, dict):
        return {"file": name, "available": False}
    best = data.get("best") or {}
    folds = best.get("folds") or []
    returns = [float(fold.get("return_pct", 0)) for fold in folds]
    win_rates = [float(fold.get("win_rate_pct", 0)) for fold in folds]
    profit_factors = [float(fold.get("profit_factor", 0)) for fold in folds]
    losing_folds = sum(1 for value in returns if value < 0)
    warnings = []
    if losing_folds:
        warnings.append(f"{losing_folds} fold(s) negativo(s).")
    if win_rates and max(win_rates) - min(win_rates) > 25:
        warnings.append("Win rate varia demais entre folds.")
    if profit_factors and min(profit_factors) < 1:
        warnings.append("Pelo menos um fold tem profit factor abaixo de 1.")
    return {
        "file": name,
        "available": True,
        "tested_configs": data.get("tested_configs"),
        "best_params": best.get("params"),
        "reliable": best.get("reliable"),
        "walk_forward_rank": best.get("walk_forward_rank"),
        "mean_return_pct": round(sum(returns) / len(returns), 2) if returns else None,
        "min_return_pct": round(min(returns), 2) if returns else None,
        "max_return_pct": round(max(returns), 2) if returns else None,
        "mean_win_rate_pct": round(sum(win_rates) / len(win_rates), 2) if win_rates else None,
        "losing_folds": losing_folds,
        "warnings": warnings,
    }


def _data_file_audit() -> dict[str, Any]:
    files = {}
    for path in sorted(DATA_DIR.glob("*")):
        if path.is_file():
            files[path.name] = {"bytes": path.stat().st_size, "modified": path.stat().st_mtime}
    return files


def build_report() -> dict[str, Any]:
    report = {
        "db": _db_counts(),
        "probability_model": _probability_model_audit(),
        "calibrations": [
            _calibration_audit("decision_strategy_calibration.json"),
            _calibration_audit("short_strategy_calibration.json"),
        ],
        "data_files": _data_file_audit(),
    }

    recommendations = []
    prob = report["probability_model"]
    if prob.get("warnings"):
        recommendations.append("Nao usar a probabilidade como aprovador de trade; usar apenas como veto ou sinal auxiliar.")
    for cal in report["calibrations"]:
        if cal.get("warnings"):
            recommendations.append(f"Tratar {cal['file']} como pesquisa, nao como threshold definitivo.")
    db = report["db"]
    if db.get("checked_decisions", 0) < 50:
        recommendations.append("Acumular pelo menos 50-100 recomendacoes com outcome checado antes de prometer taxa de acerto.")
    recommendations.append("Adicionar quality gate por feature: frescor, gaps, outliers, divergencia entre fontes e estabilidade por ativo.")
    report["recommendations"] = recommendations
    return report


def main() -> None:
    report = build_report()
    out = DATA_DIR / "feature_quality_audit.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("AUDITORIA DE DADOS E FEATURES")
    print("=============================")
    db = report["db"]
    if db.get("available"):
        print(f"Banco: OK | watchlist ativa: {len(db.get('active_watchlist', []))} | decisoes checadas: {db.get('checked_decisions')}")
        print(f"Win rate real das decisoes checadas: {db.get('decision_win_rate_pct')}")
    else:
        print(f"Banco: {db.get('reason')}")

    prob = report["probability_model"]
    print(
        f"Modelo probabilistico: treino {prob.get('train_accuracy')} | holdout {prob.get('holdout_accuracy')} | "
        f"baseline {prob.get('holdout_baseline_accuracy')}"
    )
    if prob.get("top_weights"):
        print("Features mais influentes:", ", ".join(f"{row['feature']}={row['weight']}" for row in prob["top_weights"][:5]))

    for cal in report["calibrations"]:
        print(
            f"{cal['file']}: retorno medio {cal.get('mean_return_pct')}%, min {cal.get('min_return_pct')}%, "
            f"win medio {cal.get('mean_win_rate_pct')}%, reliable={cal.get('reliable')}"
        )
        for warning in cal.get("warnings", []):
            print(f"  alerta: {warning}")

    for warning in prob.get("warnings", []):
        print(f"alerta modelo: {warning}")

    print("Recomendacoes:")
    for item in report["recommendations"]:
        print(f"- {item}")


if __name__ == "__main__":
    main()
