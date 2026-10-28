import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AIAnswerLog
from app.oneb_ai import agent
from app.oneb_ai.tools import ToolContext, anthropic_tools, execute
from app.oneb_ai.verifier import extract_numbers, verify
from app.opportunity import Approval, SetupState, Transition
from app.opportunity_ledger import record_transition


@pytest.fixture()
def ctx(tmp_path):
    # StaticPool: o agente roda ferramentas em thread separada; todas as threads enxergam o mesmo banco em memória.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    for at, frm, to, extra in [
        ("2026-10-05T10:00:00+00:00", SetupState.IDLE, SetupState.BREAK_DETECTED, {"level": 4120.55}),
        ("2026-10-05T10:10:00+00:00", SetupState.WAITING_CONFIRMATION_1, SetupState.WAITING_CONFIRMATION_2, {}),
    ]:
        record_transition(db, Transition(at=at, from_state=frm, to_state=to, reason=f"{to.value} em 4120.55",
                                         direction="long", payload={"opportunity_id": "gold:1", **extra}),
                          setup="gold_fakeout_open", setup_version="v", symbol="XAUUSD.s", mode="SHADOW",
                          approval=Approval.SHADOW)
    from datetime import datetime, timezone

    yield ToolContext(db=db, user_id=None, now=datetime(2026, 10, 5, 10, 30, tzinfo=timezone.utc), research_dir=tmp_path)
    db.close()


def _block(**kw):
    return SimpleNamespace(**kw)


class FakeClient:
    """Roteiro de respostas; registra as mensagens enviadas."""

    def __init__(self, script):
        self.script = list(script)
        self.sent = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.sent.append(kwargs)
        step = self.script.pop(0)
        return step(kwargs) if callable(step) else step


def _tool_call(name, args, id_="t1"):
    return SimpleNamespace(stop_reason="tool_use", model="claude-opus-5-5",
                           content=[_block(type="tool_use", name=name, input=args, id=id_)])


def _submit(answer, id_="s1"):
    return _tool_call("submit_answer", answer, id_)


def _answer(text, evidence):
    return {"headline": "XAUUSD.s aguardando confirmação",
            "state_summary": {"symbol": "XAUUSD.s", "setup": "gold_fakeout_open", "state": "WAITING_CONFIRMATION_2", "approval": "SHADOW"},
            "claims": [{"text": text, "evidence_ids": evidence}], "counter_points": [], "what_changed": [], "unknowns": [],
            "conclusion": "Não há entrada validada ainda. Aguardar a segunda confirmação."}


def _evidence_from_sent(kwargs):
    import json

    for message in reversed(kwargs["messages"]):
        if message["role"] == "user" and isinstance(message["content"], list):
            result = json.loads(message["content"][0]["content"])
            return result["opportunities"][0]["evidence"][-1]["evidence_id"]
    raise AssertionError("sem resultado de ferramenta")


def test_tools_have_strict_schemas_and_submit():
    specs = anthropic_tools()
    assert {s["name"] for s in specs} >= {"get_opportunities", "what_changed", "submit_answer"}
    assert all(s["strict"] and s["input_schema"]["additionalProperties"] is False for s in specs)


def test_grounded_answer_passes(ctx):
    client = FakeClient([
        _tool_call("get_opportunities", {"symbol": None}),
        lambda kw: _submit(_answer("Rompimento acima de 4120,55; falta a confirmação 2.", [_evidence_from_sent(kw)])),
    ])
    out = asyncio.run(agent.ask(ctx, "Existe oportunidade no ouro?", client=client))
    assert out["fallback_used"] is False and out["grounding"]["ok"]
    assert out["tool_calls"] == ["get_opportunities", "submit_answer"]
    sent = client.sent[0]
    assert sent["fallbacks"] == "default" and sent["output_config"]["effort"]
    assert ctx.db.query(AIAnswerLog).one().grounding_ok is True


def test_invented_number_is_rejected_then_falls_back(ctx):
    bad = lambda kw: _submit(_answer("Entrada em 4133,10 com alvo 4180.", [_evidence_from_sent(kw)]))  # noqa: E731
    client = FakeClient([_tool_call("get_opportunities", {"symbol": None}), bad, bad])
    out = asyncio.run(agent.ask(ctx, "Qual o stop?", client=client))
    retry_msg = client.sent[2]["messages"][-1]["content"][0]
    assert retry_msg["is_error"] and "UNGROUNDED_NUMBER" in retry_msg["content"]
    assert out["fallback_used"] is True
    assert "4133" not in str(out["answer"])
    log = ctx.db.query(AIAnswerLog).one()
    assert log.fallback_used is True


def test_refusal_and_api_errors_fall_back(ctx):
    client = FakeClient([SimpleNamespace(stop_reason="refusal", content=[], model="x")])
    out = asyncio.run(agent.ask(ctx, "?", client=client))
    assert out["fallback_used"] and "recusou" in out["answer"]["unknowns"][0]

    async def boom(**_):
        raise RuntimeError("down")

    broken = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=boom)))
    out = asyncio.run(agent.ask(ctx, "Como estão os setups?", client=broken))
    assert out["fallback_used"] and out["answer"]["claims"][0]["text"].startswith("XAUUSD.s")
    # pergunta que a IA não entende: diz que não entendeu, em vez de responder outra coisa
    vague = asyncio.run(agent.ask(ctx, "?", client=broken))
    assert vague["fallback_used"] and vague["answer"]["headline"] == "Não entendi essa pergunta" and vague["grounding"]["ok"]


def test_verifier_rules():
    results = [{"result_id": "res:1", "opportunities": [{"approval": "SHADOW", "evidence": [{"evidence_id": "ev:a"}]}],
                "summary": {"expectancy_r": -0.1621, "win_rate": 0.3472}}]
    ok = verify(_answer("Expectância -0,16R e acerto de 34,7% em 2 confirmações às 07:00.", ["ev:a"]), results)
    assert ok["ok"], ok
    order = verify(_answer("Compre agora.", ["ev:a"]), results)
    assert any(v["code"] == "ORDER_LANGUAGE_WITHOUT_APPROVAL" for v in order["violations"])
    unknown = verify(_answer("Texto.", ["ev:inventado"]), results)
    assert any(v["code"] == "UNKNOWN_EVIDENCE_ID" for v in unknown["violations"])
    assert extract_numbers("Data 2026-10-05, 07:00, MM1000, preço 4.120,55") == [4120.55]


def test_what_changed_tool_computes_diff(ctx):
    result = execute(ctx, "what_changed", {"since_minutes": 25, "symbol": None})
    assert [c["to"] for c in result["advanced"]] == ["WAITING_CONFIRMATION_2"]
    assert result["new_opportunities"] == [] and result["result_id"].startswith("res:")


def test_to_text_for_telegram(ctx):
    out = asyncio.run(agent.ask(ctx, "?", client=FakeClient([SimpleNamespace(stop_reason="refusal", content=[], model="x")])))
    text = agent.to_text(out)
    assert "Conclusão:" in text and "Não é recomendação" in text


def test_trend_tool_reports_test_status_and_evidence_ids(ctx, monkeypatch):
    import numpy as np
    import pandas as pd

    from app.oneb_ai.tools import execute
    from app.routers import trend as trend_router

    bars = pd.DataFrame({"close": np.linspace(100, 80, 400)}, index=pd.bdate_range("2024-01-01", periods=400))
    monkeypatch.setattr(trend_router.market_data, "get_bars", lambda *a, **k: bars)
    monkeypatch.setattr(trend_router, "RESULT_PATH", ctx.research_dir / "nao_existe.json")
    out = execute(ctx, "get_trend_reading", {"asset": "XAUUSD"})
    assert out["test"]["status"] == "PENDING" and out["test"]["as_evidence"] is False
    assert out["assets"][0]["evidence_id"] == "ev:trend:XAUUSD" and out["assets"][0]["agreement"] == "todos em baixa"


def test_asset_risk_tool_sizes_only_with_user_balance(ctx, monkeypatch):
    import pandas as pd

    from app.oneb_ai.tools import execute
    from app.routers import asset_brief

    idx = pd.date_range("2026-01-01", periods=300, freq="h")
    bars = pd.DataFrame({"open": 100.0, "high": 110.0, "low": 90.0, "close": 100.0}, index=idx)  # ATR = 20
    monkeypatch.setattr(asset_brief.market_data, "get_bars", lambda *a, **k: bars)
    monkeypatch.setattr(asset_brief.trend_router, "_reading", lambda asset: {"available": True})
    out = execute(ctx, "get_asset_risk", {"asset": "XAUUSD"})
    assert "sizing" not in out  # sem saldo informado, nada de tamanho
    assert out["broker"]["symbol"] == "XAUUSD.s" and out["broker"]["evidence_id"].startswith("ev:broker:")
    out = execute(ctx, "get_asset_risk", {"asset": "XAUUSD", "balance": 10000, "risk_pct": 1, "stop_atr": 1.0})
    s = out["sizing"]
    assert s["stop_distance"] == 20 and s["risk_money"] == 100
    assert s["lots"] == 0.05  # 100 / (20 * 100)
    assert s["spread_cost"] == 1.3  # 0,26 x 100 x 0,05


def test_position_size_flags_minimum_lot():
    from app.oneb_ai.tools import position_size

    s = position_size(500, 1, 60, 1.0, 1.0, 1.0, 0.7)
    assert s["below_minimum"] and s["lots"] == 0 and s["min_lot_risk"] == 60


def test_llm_path_runs_trade_plan_tool_and_verifier_accepts_plan_numbers(ctx):
    import json

    ctx.market_override = {"XAUUSD": {
        "market": {"price": 4000.0, "atr_h1": 10.0, "atr_d1": 70.0},
        "range_forecast": {"target_date": "2026-10-06", "expected_price": 50.0, "us_holiday": None},
        "events": [],
    }}

    def plan_answer(kw):
        result = None
        for message in reversed(kw["messages"]):
            if message["role"] == "user" and isinstance(message["content"], list):
                result = json.loads(message["content"][0]["content"])
                break
        tp2 = result["targets"][1]
        return _submit({
            "headline": "Plano de compra no ouro",
            "state_summary": {"symbol": "XAUUSD", "setup": None, "state": None, "approval": None},
            "claims": [{"text": f"Stop em {result['stop']:.2f}; TP2 em {tp2['price']:.2f}, atingido antes do stop em "
                                f"{tp2['p_target'] * 100:.0f}% das entradas medidas.", "evidence_ids": [tp2["evidence_id"]]}],
            "counter_points": [{"text": "Taxa-base, não sinal.", "evidence_ids": [result["evidence_id"]]}],
            "what_changed": [], "unknowns": [], "conclusion": "É o seu plano de risco; a decisão é sua.",
        })

    client = FakeClient([_tool_call("get_trade_plan", {"asset": "XAUUSD", "direction": "long", "stop_atr": None}), plan_answer])
    out = asyncio.run(agent.ask(ctx, "Se eu comprar ouro, qual o plano?", client=client))
    assert out["fallback_used"] is False and out["grounding"]["ok"], out["grounding"]
    assert out["tool_calls"] == ["get_trade_plan", "submit_answer"]
    assert "Stop em 3985.00" in out["answer"]["claims"][0]["text"]  # compra: stop abaixo, 4000 - 1,5 x 10


def test_template_answer_with_unverified_number_drops_that_sentence():
    from app.oneb_ai.agent import _drop_unverified
    from app.oneb_ai.verifier import verify as _verify

    results = [{"result_id": "res:1", "price": 100.0, "evidence_id": "ev:a"}]
    answer = _answer("Preço de 100,00.", ["ev:a"])
    answer["claims"].append({"text": "Alvo provável em 123,45.", "evidence_ids": ["ev:a"]})
    check = _verify(answer, results)
    assert not check["ok"]
    cleaned = _drop_unverified(answer, check)
    assert [c["text"] for c in cleaned["claims"]] == ["Preço de 100,00."] and _verify(cleaned, results)["ok"]
    assert "removida" in cleaned["unknowns"][-1]
