from app.reliability import assess_decision, assess_intraday_card, wilson_interval

GOOD_GATE = {"allowed": True, "confidence": "HIGH", "reason": ""}
OK_RISK = {"allowed": True, "kill_switches": []}
HEALTHY_DESK = {"allowed": True, "operating_mode": "GUARDED", "reason": ""}
MODEL = {"holdout_auc": 0.62}


def _memory(hist_n, hist_rate, logged_n=0, logged_rate=0):
    return {
        "historical_samples": hist_n,
        "historical_win_rate_pct": hist_rate,
        "logged_samples": logged_n,
        "logged_win_rate_pct": logged_rate,
    }


def _assess(**overrides):
    params = {
        "action": "BUY_CONTROLLED",
        "memory": _memory(300, 66, 80, 66),
        "quality_gate": GOOD_GATE,
        "risk": OK_RISK,
        "model": MODEL,
        "model_drift_alert": False,
        "probability": 0.6,
        "earnings_blackout": False,
        "decision_health": HEALTHY_DESK,
    }
    params.update(overrides)
    return assess_decision(**params)


def test_wilson_penalizes_small_samples():
    small = wilson_interval(3, 3)
    large = wilson_interval(60, 100)
    assert small[0] < large[0]
    assert wilson_interval(0, 0) is None


def test_strong_evidence_reaches_high_grade():
    result = _assess()
    assert result["grade"] == "ALTA"
    assert result["score"] >= 75
    assert not result["caps"]
    assert "não é probabilidade" in result["disclaimer"]


def test_small_sample_is_capped_as_insufficient_even_with_perfect_hit_rate():
    result = _assess(memory=_memory(9, 100))
    assert result["score"] <= 40
    assert result["grade"] == "INSUFICIENTE"
    assert "casos de evidência" in result["limiting_factor"]


def test_missing_components_count_as_zero_not_neutral():
    with_model = _assess()
    without_model = _assess(model=None, probability=None)
    assert without_model["raw_score"] < with_model["raw_score"]
    model_component = next(c for c in without_model["components"] if c["key"] == "model")
    assert model_component["available"] is False


def test_hard_caps_from_gates():
    assert _assess(quality_gate={"allowed": False, "confidence": "LOW", "reason": "STALE_DATA"})["score"] <= 20
    assert _assess(risk={"allowed": False, "kill_switches": ["MAX_POSITION"]})["score"] <= 25
    assert _assess(earnings_blackout=True)["score"] <= 50
    desk = _assess(decision_health={"allowed": False, "operating_mode": "OBSERVATION_ONLY", "reason": "amostra"})
    assert desk["score"] <= 60
    assert "OBSERVATION_ONLY" in desk["limiting_factor"]


def test_model_disagreement_and_drift_lower_the_model_component():
    agree = next(c for c in _assess()["components"] if c["key"] == "model")
    disagree = next(c for c in _assess(probability=0.4)["components"] if c["key"] == "model")
    drift = next(c for c in _assess(model_drift_alert=True)["components"] if c["key"] == "model")
    assert agree["score"] > disagree["score"]
    assert drift["score"] == 0


def test_non_directional_actions_have_no_reliability_score():
    result = _assess(action="WAIT")
    assert result["score"] is None
    assert result["grade"] == "SEM_SINAL"


def test_intraday_card_without_approval_or_clock_stays_low():
    card = {
        "action": "NO_TRADE",
        "data_health": {"sessions": 120, "fresh": True, "clock_verified": False},
        "holdout_evidence": {"trades": 12, "profit_factor": 0.8, "bh_q_value": 0.4},
    }
    result = assess_intraday_card(card)
    assert result["score"] <= 30
    assert {cap["key"] for cap in result["caps"]} >= {"CLOCK", "EVIDENCE_SAMPLES", "NOT_APPROVED"}


def test_intraday_card_with_full_evidence_scores_high_when_approved():
    card = {
        "action": "BUY_CANDIDATE",
        "approval": "PAPER",
        "data_health": {"sessions": 300, "fresh": True, "clock_verified": True},
        "holdout_evidence": {"trades": 150, "profit_factor": 1.6, "bh_q_value": 0.01},
    }
    result = assess_intraday_card(card)
    assert result["grade"] == "ALTA"
    assert not result["caps"]


def test_moderate_hit_rate_is_not_sold_as_high():
    # 62% em 120 casos: o limite inferior de Wilson fica perto de 53%.
    result = _assess(memory=_memory(120, 62, 40, 60))
    assert result["grade"] == "MEDIA"
