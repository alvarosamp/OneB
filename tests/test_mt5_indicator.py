import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_generated_indicator_embeds_current_research(tmp_path, monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_mt5_indicator", ROOT / "scripts" / "build_mt5_indicator.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = tmp_path / "OneB_Risco.mq5"
    monkeypatch.setattr(mod, "OUT", out)
    mod.main()
    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # UTF-8 com BOM para o MetaEditor
    text = raw.decode("utf-8-sig")
    assert "//@@DATA@@" not in text and "double COEF[4][5]" in text and "int HOURCLASS[4][24]" in text
    vf = json.loads((ROOT / "app" / "research_results" / "volfc_v1.json").read_text(encoding="utf-8"))
    assert f"{vf['app_model']['NAS100']['coef'][0]:.6f}" in text  # coeficiente aprovado embutido
    rates = json.loads((ROOT / "app" / "research_results" / "trade_plan_rates.json").read_text(encoding="utf-8"))
    p = next(r["p_target"] for r in rates["assets"]["XAUUSD"]["recent"] if r["ny_hour"] is None and r["stop_atr"] == 1.5
             and r["direction"] == "long" and r["target_r"] == 1.0)
    assert f"{p:.4f}" in text
    sres = json.loads((ROOT / "app" / "research_results" / "sessfc_v1.json").read_text(encoding="utf-8"))
    on = [1 if k in sres["app_model"] else 0 for k in ("NAS100", "SPX500", "XAUUSD", "EURUSD")]
    assert "int SESS_ON[4] = {" + ",".join(map(str, on)) + "}" in text  # só ativo aprovado no sessfc_v1
    # o indicador nunca opera
    for forbidden in ("OrderSend", "CTrade", "PositionOpen", "OrderSendAsync"):
        assert forbidden not in text


def test_committed_indicator_is_up_to_date():
    """O .mq5 versionado tem que ser o gerado a partir da pesquisa atual (rode scripts/build_mt5_indicator.py)."""
    current = (ROOT / "mt5" / "OneB_Risco.mq5").read_text(encoding="utf-8-sig")
    vf = json.loads((ROOT / "app" / "research_results" / "volfc_v1.json").read_text(encoding="utf-8"))
    assert f"{vf['app_model']['XAUUSD']['q90']:.6f}" in current
