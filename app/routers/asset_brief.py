"""Análise do ativo e mapa de horários: risco medido, não previsão.

- /api/analysis/hour-heatmap: volatilidade e custo por dia/hora (scripts/build_hour_heatmap.py).
- /api/analysis/asset/{key}: preço, ATR, distâncias de stop por ATR, hora atual no mapa,
  próximos eventos com o impacto medido no ativo (calendar_v1), custo na corretora,
  leitura de tendência (descritiva) e o que já foi testado no ativo, com o resultado.

Nada aqui é sinal de compra ou venda: os testes pré-registrados não aprovaram nenhuma regra.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import calendar_risk, response_cache
from app.auth import get_current_user
from app.db import get_db
from app.market_data import service as market_data
from app.models import EconomicEvent
from app.routers import trend as trend_router

router = APIRouter(prefix="/api/analysis", tags=["analysis"], dependencies=[Depends(get_current_user)])

RESULTS = Path(__file__).resolve().parents[1] / "research_results"
NEW_YORK = ZoneInfo("America/New_York")

# Especificação HonorPro lida do MT5 (somente leitura) em 10/10/2026. Spread típico = mediana de
# dias úteis (abr-set/2026), não o valor ao vivo, que no fim de semana fica inflado.
BROKER = {
    "NAS100": {"symbol": "US100.s", "contract_size": 1.0, "volume_min": 1.0, "volume_step": 1.0, "spread_points": 0.7},
    "SPX500": {"symbol": "US500.s", "contract_size": 1.0, "volume_min": 0.1, "volume_step": 0.1, "spread_points": 5.3},
    "XAUUSD": {"symbol": "XAUUSD.s", "contract_size": 100.0, "volume_min": 0.01, "volume_step": 0.01, "spread_points": 0.26},
    "EURUSD": {"symbol": "EURUSD.s", "contract_size": 100000.0, "volume_min": 0.01, "volume_step": 0.01, "spread_points": None},
}
ASSETS = {a["key"]: a for a in trend_router.ASSETS if a["key"] in BROKER}


@lru_cache(maxsize=8)
def _json(name: str, mtime: float) -> dict:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def _result(name: str) -> dict | None:
    path = RESULTS / name
    return _json(name, path.stat().st_mtime) if path.exists() else None


@router.get("/hour-heatmap")
def hour_heatmap():
    data = _result("hour_heatmap.json")
    if data is None:
        raise HTTPException(404, "Mapa de horários ainda não foi gerado.")
    return data


def _atr(bars: pd.DataFrame, period: int = 14) -> float | None:
    if bars is None or len(bars) < period + 1:
        return None
    prev = bars["close"].shift()
    tr = pd.concat([bars["high"] - bars["low"], (bars["high"] - prev).abs(), (bars["low"] - prev).abs()], axis=1).max(axis=1)
    value = tr.rolling(period).mean().iloc[-1]
    return float(value) if pd.notna(value) else None


def _hours_ahead(key: str, now: datetime, count: int = 8) -> list[dict]:
    heat = _result("hour_heatmap.json")
    if not heat or key not in heat["assets"]:
        return []
    cells = {(c["weekday"], c["hour"]): c for c in heat["assets"][key]["cells"]}
    out = []
    ny = now.astimezone(NEW_YORK).replace(minute=0, second=0, microsecond=0)
    for i in range(count):
        t = ny + timedelta(hours=i)
        cell = cells.get((t.weekday(), t.hour))
        out.append({"starts_at": t.astimezone(timezone.utc).isoformat(), "ny_hour": t.hour, "weekday": t.weekday(),
                    "ratio": cell["ratio"] if cell else None, "cost_share": cell["cost_share"] if cell else None,
                    "range_bps": cell["range_bps"] if cell else None})
    return out


def _events(key: str, db: Session, now: datetime) -> list[dict]:
    rows = (db.query(EconomicEvent).filter(EconomicEvent.event_date >= now - timedelta(hours=1))
            .filter(EconomicEvent.event_date <= now + timedelta(days=3)).order_by(EconomicEvent.event_date).limit(40).all())
    out = []
    for e in rows:
        risk = calendar_risk.risk_for(e.event_name)
        mine = next((a for a in (risk or {}).get("assets", []) if a["asset"] == key), None)
        if mine is None and (e.impact or "").lower() not in ("high", "alto"):
            continue
        out.append({"event_name": e.event_name, "event_date": e.event_date.isoformat(), "impact": e.impact,
                    "type": (risk or {}).get("type"), "post30": mine.get("post30") if mine else None,
                    "post120": mine.get("post120") if mine else None, "measured": mine is not None})
    return out[:8]


def _evidence(key: str) -> list[dict]:
    items = []
    lab = _result("lab_v1_summary.json")
    if lab and key in lab["assets"]:
        a = lab["assets"][key]
        items.append({"test": "lab_v1", "title": f"{a['tested']} regras clássicas de gráfico (inclui Duck, RSI, médias, Bollinger)",
                      "status": "FAILED" if not lab["survivors"] else "MIXED",
                      "detail": f"Nenhuma sobreviveu com custo real (2019-2022). Melhor: {a['best']['candidate']} com "
                                f"{a['best']['net_r']:+.3f}R por trade."})
    tsmom = _result("tsmom_v1.json")
    if tsmom:
        mine = tsmom.get("by_instrument", {}).get(ASSETS[key]["instrument"])
        items.append({"test": "tsmom_v1", "title": "Tendência de 1, 3 e 12 meses", "status": tsmom["verdict"]["status"],
                      "detail": f"Carteira de {len(tsmom['universe_used'])} ativos: {tsmom['primary_combined']['mean_monthly'] * 100:+.2f}% ao mês"
                                + (f"; neste ativo {mine['mean_monthly'] * 100:+.2f}% ao mês." if mine else ".")})
    f7 = _result("f7_honor_v1.json")
    if f7 and key == "NAS100":
        p = f7["primary"]
        items.append({"test": "f7_honor_v1", "title": "Momentum da última hora com o custo da HonorPro", "status": f7["status"],
                      "detail": f"{p['trades']} trades em 2023-2026: {p['expectancy_r']:+.3f}R por trade (IC {p['ci95'][0]:+.3f} a {p['ci95'][1]:+.3f})."})
    vf = _result("volfc_v1.json")
    if vf and key in vf.get("assets", {}):
        a = vf["assets"][key]
        items.append({"test": "volfc_v1", "title": "Previsão de quanto o preço vai se mover amanhã", "status": vf["status"],
                      "detail": f"Erro {a['reduction_vs_baseline'] * 100:.0f}% menor que o ATR de 14 dias em 2023-2026; "
                                f"a faixa de 80% acertou {a['coverage80'] * 100:.0f}% dos dias. Diz quanto, não para onde."})
    cal = _result("calendar_v1.json")
    if cal and key in cal.get("assets", {}):
        vol = cal["assets"][key]["H1_volatility"]
        strongest = max(((k, v["post30"]["median_ratio"]) for k, v in vol.items() if v.get("H1_passed")), key=lambda kv: kv[1], default=None)
        if strongest:
            items.append({"test": "calendar_v1", "title": "Impacto do calendário macro", "status": "PASSED",
                          "detail": f"Aprovado para volatilidade (não direção): {strongest[0]} multiplica o movimento de 30 min por {strongest[1]:.1f}."})
    return items


FORECAST_EVENTS = {"CPI", "NFP", "FOMC"}


def _as_utc(value) -> pd.Timestamp:
    """SQLite devolve datas sem fuso; o banco grava em UTC."""
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts


def range_forecast(key: str, daily: pd.DataFrame | None, db: Session, now: datetime) -> dict | None:
    """Amplitude esperada do próximo pregão (teste volfc_v1): HAR no log da amplitude + evento macro.

    Usa só pregões FECHADOS (o dia corrente só conta depois das 17:00 de Nova York).
    """
    from app import volfc

    result = _result("volfc_v1.json")
    if not result or result.get("status") != "PASSED" or key not in result.get("app_model", {}) or daily is None or len(daily) < 30:
        return None
    model = result["app_model"][key]
    bars = daily.copy()
    bars.index = pd.DatetimeIndex(bars.index).tz_localize(None).normalize() if pd.DatetimeIndex(bars.index).tz is not None else pd.DatetimeIndex(bars.index).normalize()
    ny_now = now.astimezone(NEW_YORK)
    trading_today = (ny_now + timedelta(hours=7)).date()
    if bars.index[-1].date() >= trading_today:
        bars = bars.iloc[:-1]  # pregão de hoje ainda aberto
    rng = ((bars["high"] - bars["low"]) / bars["close"].shift(1)).dropna()
    rng = rng[rng > 0]
    if len(rng) < 25:
        return None
    target = bars.index[-1] + pd.offsets.BDay(1)
    events = (db.query(EconomicEvent).filter(EconomicEvent.event_date >= now - timedelta(days=1))
              .filter(EconomicEvent.event_date <= now + timedelta(days=5)).all())
    names = [e.event_name for e in events if calendar_risk.event_type(e.event_name) in FORECAST_EVENTS
             and _as_utc(e.event_date).tz_convert(NEW_YORK).date() == target.date()]
    lr = np.log(rng)
    f = volfc.features(lr).iloc[-1]
    coef = np.asarray(model["coef"])
    mid = float(coef[0] + coef[1] * f["d"] + coef[2] * f["w"] + coef[3] * f["m"] + coef[4] * (1.0 if names else 0.0))
    price = float(bars["close"].iloc[-1])
    atr14 = float(np.exp(f["atr14"]))
    return {"target_date": target.date().isoformat(), "based_on": bars.index[-1].date().isoformat(),
            "expected_pct": np.exp(mid) * 100, "low80_pct": np.exp(mid + model["q10"]) * 100,
            "high80_pct": np.exp(mid + model["q90"]) * 100, "expected_price": np.exp(mid) * price,
            "low80_price": np.exp(mid + model["q10"]) * price, "high80_price": np.exp(mid + model["q90"]) * price,
            "atr14_pct": atr14 * 100, "event": names[0] if names else None,
            "coverage80_test": model.get("coverage80_test"), "test": "volfc_v1",
            "note": "Previsão de quanto o preço deve se mover no próximo pregão (máxima - mínima), não da direção. Aprovada em teste pré-registrado: erro 10% menor que o ATR de 14 dias em 2023-2026."}


@router.get("/asset/{key}")
def asset_brief(key: str, db: Session = Depends(get_db)):
    key = key.upper()
    if key not in ASSETS:
        raise HTTPException(404, f"Ativo sem estudo: {key}. Disponíveis: {', '.join(ASSETS)}")
    market = response_cache.cached(f"brief:market:{key}", 120, lambda: _market(key))
    now = datetime.now(timezone.utc)
    heat = _result("hour_heatmap.json") or {"assets": {}}
    daily = response_cache.cached(f"brief:daily:{key}", 300, lambda: market_data.get_bars(ASSETS[key]["symbol"], period="6mo", interval="1d"))
    forecast = range_forecast(key, daily, db, now)
    return {"key": key, "label": ASSETS[key]["label"], "symbol": ASSETS[key]["symbol"], "generated_at": now.isoformat(),
            "broker": BROKER[key], "market": market, "range_forecast": forecast, "hours_ahead": _hours_ahead(key, now),
            "heatmap_meta": {k: heat["assets"][key][k] for k in ("typical_range_bps", "period", "cost_source")} if key in heat["assets"] else None,
            "events": _events(key, db, now), "evidence": _evidence(key),
            "note": "Distâncias de stop por ATR são gestão de risco, não previsão. Nenhuma regra testada foi aprovada para direção."}


def _market(key: str) -> dict:
    symbol = ASSETS[key]["symbol"]
    daily = market_data.get_bars(symbol, period="6mo", interval="1d")
    hourly = market_data.get_bars(symbol, period="1mo", interval="1h")
    out: dict = {"available": daily is not None and not daily.empty}
    if not out["available"]:
        return out
    close = daily["close"].astype(float)
    out.update({"price": float(close.iloc[-1]), "prev_close": float(close.iloc[-2]) if len(close) > 1 else None,
                "as_of": pd.Timestamp(daily.index[-1]).isoformat(), "atr_d1": _atr(daily), "atr_h1": _atr(hourly)})
    if out["prev_close"]:
        out["change_pct"] = (out["price"] / out["prev_close"] - 1) * 100
    try:
        out["trend"] = trend_router._reading(ASSETS[key])
    except Exception:  # noqa: BLE001 - leitura de tendência é complementar
        out["trend"] = None
    return out


@router.get("/next-session")
def next_session(db: Session = Depends(get_db)):
    """Amplitude esperada do próximo pregão nos ativos estudados + eventos dos próximos 7 dias com o impacto medido."""
    now = datetime.now(timezone.utc)
    assets = []
    for key, asset in ASSETS.items():
        daily = response_cache.cached(f"brief:daily:{key}", 300, lambda s=asset["symbol"]: market_data.get_bars(s, period="6mo", interval="1d"))
        try:
            fc = range_forecast(key, daily, db, now)
        except Exception:  # noqa: BLE001 - um ativo sem dado não derruba os outros
            fc = None
        assets.append({"key": key, "label": asset["label"], "forecast": fc})
    rows = (db.query(EconomicEvent).filter(EconomicEvent.event_date >= now - timedelta(hours=1))
            .filter(EconomicEvent.event_date <= now + timedelta(days=7)).order_by(EconomicEvent.event_date).all())
    events = []
    for e in rows:
        risk = calendar_risk.risk_for(e.event_name)
        if risk is None and (e.impact or "").lower() not in ("high", "alto"):
            continue
        events.append({"event_name": e.event_name, "event_date": _as_utc(e.event_date).isoformat(), "type": (risk or {}).get("type"),
                       "assets": [{"label": a["label"], "post30": a.get("post30")} for a in (risk or {}).get("assets", [])]})
    return {"generated_at": now.isoformat(), "assets": assets, "events": events[:10],
            "note": "Amplitude = quanto deve se mover (máxima - mínima), não para onde. Teste volfc_v1 aprovado."}
