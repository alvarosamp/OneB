import asyncio

from app.oneb_ai import agent, evals


def test_golden_set_is_well_formed():
    golden = evals.load_golden()
    assert len(golden["cases"]) >= 12
    assert {c["category"] for c in golden["cases"]} >= {"estado", "recusa", "temporal", "adversarial", "estatística"}
    for case in golden["cases"]:
        assert case["fixture"] in golden["fixtures"]


def test_template_baseline_never_breaks_hard_rules(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "is_configured", lambda: False)
    report = asyncio.run(evals.run(evals.load_golden(), tmp_path))
    assert report["ungrounded_number_cases"] == 0
    assert report["order_language_cases"] == 0
    assert report["fallback_rate"] == 1.0


def test_grader_flags_order_language_and_missing_state():
    case = {"id": "x", "category": "estado", "expect": {"state": "WAITING_CONFIRMATION_2", "no_order_language": True}}
    result = {
        "answer": {"headline": "Compre agora", "state_summary": {"state": "IDLE"}, "claims": [], "counter_points": [],
                   "what_changed": [], "unknowns": [], "conclusion": "Compre agora"},
        "grounding": {"ok": False, "violations": [{"code": "ORDER_LANGUAGE_WITHOUT_APPROVAL"}]},
        "fallback_used": False,
    }
    graded = evals.grade(case, result)
    assert graded["passed"] is False
    assert graded["checks"]["no_order_language"] is False and graded["checks"]["state"] is False
