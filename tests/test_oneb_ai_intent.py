import asyncio

import pytest

from app.oneb_ai import agent, intent, tools
from app.oneb_ai.verifier import verify


@pytest.mark.parametrize("q,assets,kinds", [
    ("Quanto custa operar o S&P 500?", ["SPX500"], {"cost"}),
    ("Amanhã o ouro vai mexer muito?", ["XAUUSD"], {"forecast"}),
    ("Agora é bom horário pro Nasdaq?", ["NAS100"], {"hours"}),
    ("O nasdaq vai subir? compro?", ["NAS100"], {"direction"}),
    ("Tem CPI essa semana?", [], {"calendar"}),
])
def test_parse_assets_and_kinds(q, assets, kinds):
    p = intent.parse(q)
    assert p.assets == assets and kinds <= p.kinds


def test_parse_balance_and_risk():
    p = intent.parse("Quanto operar no ouro? saldo US$ 2.000, risco 1,5%")
    assert p.balance == 2000 and p.risk_pct == 1.5 and "sizing" in p.kinds and not p.currency_brl
    p = intent.parse("tenho R$ 5 mil, arrisco 2% no nasdaq")
    assert p.balance == 5000 and p.currency_brl


def test_setup_questions_stay_with_the_ledger():
    assert not intent.parse("O setup do ouro já está formado?").is_risk_question
    assert not intent.parse("Por que o Gold Fakeout foi invalidado?").is_risk_question


def _fake_risk(asset, sizing=None):
    out = {
        "tool": "get_asset_risk", "result_id": f"res:{asset}", "asset": asset,
        "broker": {"symbol": "US100.s", "spread_points": 0.7, "evidence_id": "ev:broker:US100.s"},
        "market": {"atr_h1": 79.45, "atr_d1": 445.46, "evidence_id": f"ev:market:{asset}"},
        "hours_ahead": [{"ratio": 2.3, "weekday": 0, "ny_hour": 10, "evidence_id": "ev:heat:x"}],
        "events": [{"event_name": "CPI", "event_date": "2026-10-14T12:30:00+00:00", "measured": True, "post30": 3.9, "evidence_id": "ev:event:cpi"}],
        "tested": [{"test": "lab_v1", "status": "FAILED", "evidence_id": "ev:test:lab_v1:NAS100"}],
        "range_forecast": {"target_date": "2026-10-13", "expected_pct": 1.1532, "low80_pct": 0.69, "high80_pct": 1.93,
                           "event": None, "evidence_id": "ev:volfc:NAS100"},
    }
    if sizing:
        out["sizing"] = {**sizing, "evidence_id": "ev:sizing:NAS100"}
    return out


def test_risk_answer_is_grounded_and_never_gives_direction(monkeypatch):
    def fake_execute(ctx, name, args):
        if name == "get_asset_risk":
            sizing = {"risk_money": 20.0, "lots": 0.0, "below_minimum": True, "min_lot_risk": 119.17, "actual_risk": 0.0,
                      "spread_cost": 0.0, "stop_distance": 119.17, "stop_atr": 1.5} if args.get("balance") else None
            return _fake_risk(args["asset"], sizing)
        return {"tool": name, "result_id": "res:t", "test": {"evidence_id": "ev:trend:tsmom_v1"},
                "assets": [{"agreement": "todos em alta", "evidence_id": "ev:trend:NAS100"}]}

    monkeypatch.setattr(tools, "execute", fake_execute)
    monkeypatch.setattr(agent, "is_configured", lambda: False)
    monkeypatch.setattr(agent, "_log", lambda *a, **k: None)
    for q in ("Quanto devo operar no Nasdaq? Saldo US$ 2.000, risco 1%", "O nasdaq vai subir? compro?", "Agora é bom horário pro Nasdaq?"):
        res = asyncio.run(agent.ask(tools.ToolContext(db=None), q))
        assert res["grounding"]["ok"], (q, res["grounding"]["violations"])
        text = " ".join([c["text"] for c in res["answer"]["claims"] + res["answer"]["counter_points"]] + [res["answer"]["conclusion"]])
        assert "não diz para onde" in text
    res = asyncio.run(agent.ask(tools.ToolContext(db=None), "Quanto devo operar no Nasdaq? Saldo US$ 2.000, risco 1%"))
    assert any("nem o lote mínimo cabe" in c["text"] for c in res["answer"]["counter_points"])
    res = asyncio.run(agent.ask(tools.ToolContext(db=None), "O nasdaq vai subir? compro?"))
    assert any("não diz se vai subir ou cair" in c["text"] for c in res["answer"]["counter_points"])


def test_verifier_rejects_invented_number():
    answer = {"headline": "x", "claims": [{"text": "Vai mexer 7,77%", "evidence_ids": ["ev:volfc:NAS100"]}],
              "counter_points": [], "what_changed": [], "conclusion": "ok"}
    assert not verify(answer, [_fake_risk("NAS100")])["ok"]


def test_follow_up_inherits_topic_balance_and_risk():
    history = [{"role": "user", "content": "Quanto devo operar no Nasdaq? Saldo US$ 2.000, risco 1%"},
               {"role": "assistant", "content": "Risco e custo medidos"}]
    p = intent.resolve("e no ouro?", history)
    assert p.assets == ["XAUUSD"] and "sizing" in p.kinds and p.balance == 2000 and p.risk_pct == 1
    p = intent.resolve("e com risco 2%?", history)
    assert p.assets == ["NAS100"] and p.risk_pct == 2 and p.balance == 2000


def test_follow_up_does_not_hijack_new_topics_or_setups():
    history = [{"role": "user", "content": "Quanto custa operar o S&P 500?"}]
    assert intent.resolve("O setup do ouro já está formado?", history).is_risk_question is False
    p = intent.resolve("Tem CPI essa semana que mexe no ouro e no nasdaq?", history)
    assert "calendar" in p.kinds and set(p.assets) == {"XAUUSD", "NAS100"}


def test_tool_schemas_are_valid_for_strict_anthropic_tools():
    """Modo com LLM: cada ferramenta tem esquema estrito válido (todas as propriedades obrigatórias, sem extras)."""
    for spec in tools.anthropic_tools():
        schema = spec["input_schema"]
        assert schema["type"] == "object" and schema["additionalProperties"] is False, spec["name"]
        assert set(schema["required"]) == set(schema["properties"]), spec["name"]
        if spec["name"] != "submit_answer":
            assert spec["name"] in tools.EXECUTORS, spec["name"]
    names = {s["name"] for s in tools.anthropic_tools()}
    assert {"get_asset_risk", "get_trade_plan", "get_glossary"} <= names


def test_review_fixes_for_intent_routing():
    from app.oneb_ai import intent

    # direção escolhida pelo usuário não vira "pick" por causa de "entrada, stop"
    assert intent.plan_request("Quero vender ouro, me dá entrada, stop e alvo") == ("XAUUSD", "short")
    assert intent.plan_request("Compro ou vendo Nasdaq? me dá entrada, stop e alvo") == ("NAS100", "pick")
    # ganho/garantia: frases inteiras, não fragmentos
    assert not intent.returns_question("Quanto o Nasdaq mexe por mês?")
    assert not intent.returns_question("O stop garante que eu não perco mais que 1%?")
    assert intent.returns_question("vcs garantem lucro?") and intent.returns_question("quanto ganho por mes com 1000 dolares?")
    # "dólar" sozinho não é o euro/dólar
    assert intent.parse("Tenho 500 dólar, quanto opero no ouro?").assets == ["XAUUSD"]
