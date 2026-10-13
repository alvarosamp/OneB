"""Índice de Confiabilidade de um sinal (0–100).

Responde "quanta evidência auditável sustenta esta leitura?" — NÃO é a
probabilidade de acerto. Cada componente é medido a partir de dados que o
sistema já tem (memória histórica, outcomes registrados, qualidade de dados,
saúde do modelo, holdout de pesquisa), e travas duras limitam o índice quando
falta algo essencial. Componente sem evidência conta como zero: ausência de
prova nunca é tratada como prova neutra.

Taxas de acerto entram pelo limite inferior do intervalo de Wilson (95%), para
que 3 acertos em 3 casos não pareçam melhor que 60 em 100.
"""
from __future__ import annotations

from math import sqrt

METHOD = "reliability_v1"
DISCLAIMER = "Mede quanta evidência sustenta o sinal; não é probabilidade de acerto."
MIN_EVIDENCE_SAMPLES = 30
INTRADAY_MIN_SESSIONS = 250
INTRADAY_MIN_HOLDOUT_TRADES = 100

DIRECTIONAL_ACTIONS = {"BUY_CONTROLLED", "WATCH_BUY", "SELL_SHORT", "WATCH_SHORT"}

GRADE_LABELS = {
    "ALTA": "Confiabilidade alta",
    "MEDIA": "Confiabilidade média",
    "BAIXA": "Confiabilidade baixa",
    "INSUFICIENTE": "Evidência insuficiente",
    "SEM_SINAL": "Sem sinal para avaliar",
}


def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n <= 0:
        return None
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _hit_rate_score(lower_bound: float) -> float:
    """Maps the Wilson lower bound to 0–100: 50% (coin flip) → 50, 70% → 100, 30% → 0."""
    return _clamp(50 + (lower_bound - 0.5) * 250)


def _component(key: str, label: str, weight: int, score: float | None, detail: str) -> dict:
    return {
        "key": key,
        "label": label,
        "weight": weight,
        "available": score is not None,
        "score": round(score) if score is not None else None,
        "detail": detail,
    }


def _hit_rate_component(key: str, label: str, weight: int, wins: int, n: int, min_n: int, unit: str) -> dict:
    if n < min_n:
        return _component(key, label, weight, None, f"{n} {unit}; mínimo {min_n} para contar.")
    low, high = wilson_interval(wins, n)
    return _component(
        key, label, weight, _hit_rate_score(low),
        f"{wins}/{n} acertos; IC95% {low * 100:.0f}–{high * 100:.0f}%.",
    )


def _grade(score: int) -> str:
    if score >= 75:
        return "ALTA"
    if score >= 55:
        return "MEDIA"
    if score >= 35:
        return "BAIXA"
    return "INSUFICIENTE"


def _finish(components: list[dict], caps: list[dict], evidence_samples: int) -> dict:
    raw = sum(c["score"] * c["weight"] for c in components if c["available"]) / sum(c["weight"] for c in components)
    score = raw
    for cap in caps:
        score = min(score, cap["limit"])
    score = int(round(score))
    grade = _grade(score)
    if any(cap["key"] == "EVIDENCE_SAMPLES" for cap in caps) and grade != "INSUFICIENTE" and score <= 40:
        grade = "INSUFICIENTE"
    binding = min(caps, key=lambda cap: cap["limit"]) if caps else None
    if binding is not None and binding["limit"] < raw:
        limiting = binding["reason"]
    else:
        weakest = min(components, key=lambda c: (c["score"] if c["available"] else -1) * c["weight"])
        limiting = f"{weakest['label']}: {weakest['detail']}"
    return {
        "method": METHOD,
        "score": score,
        "raw_score": int(round(raw)),
        "grade": grade,
        "label": GRADE_LABELS[grade],
        "components": components,
        "caps": caps,
        "limiting_factor": limiting,
        "evidence_samples": evidence_samples,
        "disclaimer": DISCLAIMER,
    }


def not_applicable(reason: str) -> dict:
    return {
        "method": METHOD,
        "score": None,
        "raw_score": None,
        "grade": "SEM_SINAL",
        "label": GRADE_LABELS["SEM_SINAL"],
        "components": [],
        "caps": [],
        "limiting_factor": reason,
        "evidence_samples": 0,
        "disclaimer": DISCLAIMER,
    }


def assess_decision(
    *,
    action: str,
    memory: dict,
    quality_gate: dict | None,
    risk: dict | None,
    model: dict | None,
    model_drift_alert: bool,
    probability: float | None,
    earnings_blackout: bool,
    decision_health: dict | None,
) -> dict:
    """Confiabilidade de uma leitura diária do decision_engine."""
    if action not in DIRECTIONAL_ACTIONS:
        return not_applicable("Leitura sem direção (esperar/evitar); não há sinal para medir.")

    hist_n = int(memory.get("historical_samples") or 0)
    hist_wins = round(hist_n * float(memory.get("historical_win_rate_pct") or 0) / 100)
    logged_n = int(memory.get("logged_samples") or 0)
    logged_wins = round(logged_n * float(memory.get("logged_win_rate_pct") or 0) / 100)

    gate = quality_gate or {}
    data_level = gate.get("confidence")
    # Escala ordinal do validador de dados (app.data_quality): não é probabilidade.
    data_score = {"HIGH": 100, "MEDIUM": 60, "LOW": 15}.get(data_level)

    if model is None:
        model_component = _component("model", "Modelo validado", 20, None, "Nenhum modelo probabilístico promovido.")
    elif probability is None:
        model_component = _component("model", "Modelo validado", 20, None, "Modelo não estima esta direção.")
    elif model_drift_alert:
        model_component = _component("model", "Modelo validado", 20, 0, "Alerta de drift: acurácia recente abaixo do piso.")
    else:
        auc = model.get("holdout_auc")
        auc_score = _clamp((float(auc) - 0.5) * 1000) if auc is not None else 0
        agrees = probability >= 0.5
        score = auc_score if agrees else auc_score * 0.25
        model_component = _component(
            "model", "Modelo validado", 20, score,
            f"AUC holdout {auc if auc is not None else 'n/d'}; estimativa {probability * 100:.0f}% "
            f"{'concorda' if agrees else 'discorda'} da direção.",
        )

    components = [
        _hit_rate_component("backtest", "Histórico do padrão", 30, hist_wins, hist_n, 8, "casos históricos"),
        _hit_rate_component("forward", "Resultado real registrado", 30, logged_wins, logged_n, 5, "leituras checadas"),
        _component(
            "data", "Qualidade dos dados", 20, data_score,
            f"Validador de cotações: {data_level or 'sem leitura'}.",
        ),
        model_component,
    ]

    caps: list[dict] = []
    if gate and not gate.get("allowed", True):
        caps.append({"key": "DATA_GATE", "limit": 20, "reason": f"Quality gate bloqueou: {gate.get('reason')}."})
    if risk and not risk.get("allowed", True):
        caps.append({"key": "RISK", "limit": 25, "reason": "Risk engine bloqueou: " + ", ".join(risk.get("kill_switches") or [])})
    evidence_samples = hist_n + logged_n
    if evidence_samples < MIN_EVIDENCE_SAMPLES:
        caps.append({
            "key": "EVIDENCE_SAMPLES", "limit": 40,
            "reason": f"Só {evidence_samples} casos de evidência; mínimo {MIN_EVIDENCE_SAMPLES}.",
        })
    if earnings_blackout:
        caps.append({"key": "EVENT", "limit": 50, "reason": "Earnings dentro da janela de cautela."})
    if decision_health and not decision_health.get("allowed", True):
        caps.append({
            "key": "DESK_HEALTH", "limit": 60,
            "reason": f"Mesa em {decision_health.get('operating_mode')}: {decision_health.get('reason')}",
        })
    return _finish(components, caps, evidence_samples)


def assess_intraday_card(card: dict) -> dict:
    """Confiabilidade de um cartão intradiário (broker MT5 + holdout de pesquisa).

    Mesmo com action=NO_TRADE o índice é útil: mostra quanto falta para o
    setup ter evidência suficiente para sair da pesquisa.
    """
    health = card.get("data_health") or {}
    holdout = card.get("holdout_evidence") or {}

    sessions = int(health.get("sessions") or 0)
    trades = holdout.get("trades")
    pf = holdout.get("profit_factor")
    q = holdout.get("bh_q_value")

    data_score = (50 if health.get("fresh") else 0) + (50 if health.get("clock_verified") else 0)
    components = [
        _component(
            "history", "Histórico da corretora", 25, _clamp(sessions / INTRADAY_MIN_SESSIONS * 100),
            f"{sessions}/{INTRADAY_MIN_SESSIONS} sessões do mesmo símbolo.",
        ),
        _component(
            "holdout", "Teste fora da amostra", 35,
            None if not trades else _clamp(trades / INTRADAY_MIN_HOLDOUT_TRADES * 50)
            + (_clamp((float(pf) - 1.0) * 100, 0, 50) if pf is not None else 0),
            f"{trades or 0} operações no holdout; PF {pf if pf is not None else 'n/d'}.",
        ),
        _component(
            "significance", "Significância (q-value)", 20,
            None if q is None else _clamp((0.10 - float(q)) / 0.10 * 100),
            f"q-value {q if q is not None else 'n/d'} (limite 0,10).",
        ),
        _component(
            "data", "Dados e relógio", 20, data_score,
            f"Cotação {'atual' if health.get('fresh') else 'desatualizada'}; "
            f"relógio {'verificado' if health.get('clock_verified') else 'não verificado'}.",
        ),
    ]
    caps: list[dict] = []
    if card.get("approval", "RESEARCH") == "RESEARCH" and card.get("action") == "NO_TRADE":
        caps.append({"key": "NOT_APPROVED", "limit": 40, "reason": "Setup ainda não aprovado fora da amostra."})
    if not health.get("clock_verified"):
        caps.append({"key": "CLOCK", "limit": 30, "reason": "Fuso do MT5 não reconciliado."})
    if not health.get("fresh"):
        caps.append({"key": "STALE", "limit": 20, "reason": "Cotação desatualizada."})
    if (trades or 0) < 30:
        caps.append({"key": "EVIDENCE_SAMPLES", "limit": 35, "reason": f"Só {trades or 0} operações de holdout; mínimo 30."})
    return _finish(components, caps, int(trades or 0))
