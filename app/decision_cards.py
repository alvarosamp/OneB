from __future__ import annotations


def build_decision_card(row: dict) -> dict:
    quality = row.get("quality_gate") or {}
    risk = row.get("risk") or {}
    prediction = row.get("prediction") or {}
    return {
        "symbol": row["symbol"],
        "action": row["action"],
        "direction": row.get("direction"),
        "confidence_pct": row.get("confidence"),
        "regime": (row.get("score_details") or {}).get("market", {}).get("state"),
        "data_quality": {
            "confidence": quality.get("confidence"),
            "allowed": quality.get("allowed"),
            "reason": quality.get("reason"),
        },
        "risk": {
            "allowed": risk.get("allowed"),
            "level": risk.get("level"),
            "kill_switches": risk.get("kill_switches", []),
            "reasons": risk.get("reasons", []),
        },
        "why": row.get("evidence", []),
        "invalidation": row.get("invalidation"),
        "similar_setups": row.get("memory", {}),
        "study_topics": _study_topics(row),
        "prediction": prediction,
    }


def _study_topics(row: dict) -> list[str]:
    topics = []
    risk = row.get("risk") or {}
    quality = row.get("quality_gate") or {}
    evidence_text = " ".join(row.get("evidence", [])).lower()
    if quality.get("reason"):
        topics.append("Qualidade de dados e conflito entre provedores")
    if "volatilidade" in evidence_text:
        topics.append("Volatilidade, ATR e dimensionamento de posição")
    if "earnings" in evidence_text:
        topics.append("Risco de eventos e janela de earnings")
    if risk.get("kill_switches"):
        topics.append("Kill switch e limites de risco")
    return topics[:3]
