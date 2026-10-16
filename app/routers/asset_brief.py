"""Análise do ativo e mapa de horários: risco medido, não previsão.

- /api/analysis/hour-heatmap: volatilidade e custo por dia/hora (scripts/build_hour_heatmap.py).
- /api/analysis/asset/{key}: preço, ATR, distâncias de stop por ATR, hora atual no mapa,
  próximos eventos com o impacto medido no ativo (calendar_v1), custo na corretora,
  leitura de tendência (descritiva) e o que já foi testado no ativo, com o resultado.

Nada aqui é sinal de compra ou venda: os testes pré-registrados não aprovaram nenhuma regra.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, time, timedelta, timezone
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["analysis"], dependencies=[Depends(get_current_user)])

RESULTS = Path(__file__).resolve().parents[1] / "research_results"
NEW_YORK = ZoneInfo("America/New_York")

# Especificação da corretora (contrato, lote mínimo, passo, spread mediano em preço) num arquivo de dados,
# conferido contra o MT5 por scripts/check_broker_specs.py (--write atualiza). A HonorPro muda isso sem
# aviso: em 25/09/2026 o US100.s tinha lote mínimo 1,0; em 14/10/2026, 0,1.
BROKER_FILE = Path(__file__).resolve().parents[2] / "configs" / "broker" / "honorpro.json"
_BROKER_SPEC = json.loads(BROKER_FILE.read_text(encoding="utf-8"))
BROKER_VERIFIED_AT: str = _BROKER_SPEC["verified_at"]
BROKER: dict[str, dict] = _BROKER_SPEC["assets"]
ASSETS = {a["key"]: a for a in trend_router.ASSETS if a["key"] in BROKER}


def _br(x: float, d: int) -> str:
    """Número no formato brasileiro (1.234,56)."""
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


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


def _sgn(x: float, d: int) -> str:
    return ("+" if x >= 0 else "") + _br(x, d)


def _evidence(key: str) -> list[dict]:
    items = []
    lab = _result("lab_v1_summary.json")
    if lab and key in lab["assets"]:
        a = lab["assets"][key]
        items.append({"test": "lab_v1", "title": f"{a['tested']} regras clássicas de gráfico (inclui Duck, RSI, médias, Bollinger)",
                      "status": "FAILED" if not lab["survivors"] else "MIXED",
                      "detail": f"Nenhuma sobreviveu com custo real (2019-2022). Melhor: {a['best']['candidate']} com "
                                f"{_sgn(a['best']['net_r'], 3)}R por trade."})
    tsmom = _result("tsmom_v1.json")
    if tsmom:
        mine = tsmom.get("by_instrument", {}).get(ASSETS[key]["instrument"])
        items.append({"test": "tsmom_v1", "title": "Tendência de 1, 3 e 12 meses", "status": tsmom["verdict"]["status"],
                      "detail": f"Carteira de {len(tsmom['universe_used'])} ativos: {_sgn(tsmom['primary_combined']['mean_monthly'] * 100, 2)}% ao mês"
                                + (f"; neste ativo {_sgn(mine['mean_monthly'] * 100, 2)}% ao mês." if mine else ".")})
    f7 = _result("f7_honor_v1.json")
    if f7 and key == "NAS100":
        p = f7["primary"]
        items.append({"test": "f7_honor_v1", "title": "Momentum da última hora com o custo da HonorPro", "status": f7["status"],
                      "detail": f"{p['trades']} trades em 2023-2026: {_sgn(p['expectancy_r'], 3)}R por trade (IC {_sgn(p['ci95'][0], 3)} a {_sgn(p['ci95'][1], 3)})."})
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
                          "detail": f"Aprovado para volatilidade (não direção): {strongest[0]} multiplica o movimento de 30 min por {_br(strongest[1], 1)}."})
    return items


FORECAST_EVENTS = {"CPI", "NFP", "FOMC"}


def us_holiday(day: pd.Timestamp) -> str | None:
    """Feriado federal americano no dia (bolsa ou mercado de títulos fechados): o pregão tende a ser atípico.
    O modelo volfc não conhece feriados; em 12/10/2026 (Columbus Day) o dia mexeu bem menos que o previsto."""
    from pandas.tseries.holiday import USFederalHolidayCalendar

    names = USFederalHolidayCalendar().holidays(day, day, return_name=True)
    return str(names.iloc[0]) if len(names) else None


def _as_utc(value) -> pd.Timestamp:
    """SQLite devolve datas sem fuso; o banco grava em UTC."""
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts


MIN_SESSION_HOURS = 15


def sessions_from_hourly(hourly: pd.DataFrame) -> pd.DataFrame:
    """Pregões de 17:00 a 17:00 de Nova York (a mesma virada do estudo volfc_v1) montados das barras de 1 hora.

    A barra diária do Yahoo para futuros não serve: quando o pregão da noite abre (18:00 de NY), a barra
    do dia é sobrescrita pelo começo da sessão nova e o pregão do dia some (visto em 15/10/2026)."""
    if hourly is None or hourly.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    idx = pd.DatetimeIndex(hourly.index)
    ny = (idx.tz_localize("UTC") if idx.tz is None else idx).tz_convert(NEW_YORK)
    session = pd.DatetimeIndex((ny + pd.Timedelta(hours=7)).date)
    g = hourly.groupby(session)
    d = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(), "close": g["close"].last(),
                      "volume": g["volume"].sum() if "volume" in hourly else 0, "hours": g["close"].count()})
    d = d[d.index.dayofweek < 5]
    # o último pregão pode estar em andamento (poucas horas): fica, e quem usa descarta o "de hoje";
    # pregões antigos incompletos (buraco de dados) saem
    keep = (d["hours"] >= MIN_SESSION_HOURS) | (d.index == d.index.max())
    return d[keep].drop(columns="hours")


def _daily(symbol: str, refresh: bool = False) -> pd.DataFrame:
    """Barras diárias para as previsões: das barras de 1 hora; cai para a diária do provedor se faltar."""
    try:
        hourly = market_data.get_bars(symbol, period="6mo", interval="1h", refresh=refresh)
        d = sessions_from_hourly(hourly)
        if len(d) >= 30:
            d.attrs.update(getattr(hourly, "attrs", {}))  # mantém fetched_at / cache_fallback para o selo de dados
            return d
    except Exception:  # noqa: BLE001
        logger.exception("Barras de 1 hora indisponíveis para %s", symbol)
    return market_data.get_bars(symbol, period="6mo", interval="1d")


def session_start(target_date: str) -> pd.Timestamp:
    """Início do pregão (18:00 de NY do dia útil anterior), em UTC."""
    prev = (pd.Timestamp(target_date) - pd.offsets.BDay(1)).date()
    return pd.Timestamp(datetime.combine(prev, time(18, 0), tzinfo=NEW_YORK)).tz_convert("UTC")


def record_forecast(db: Session | None, key: str, target_date: str, based_on: str, expected: float, low: float, high: float,
                    event: bool, now: datetime, kind: str = "volfc", deadline: pd.Timestamp | None = None) -> None:
    """Grava a previsão do pregão `target_date` na primeira vez que ela é calculada (nunca reescreve).
    Não grava depois que o pregão alvo terminou (17:00 de NY): seria previsão do passado."""
    from app.models import ForecastLiveRecord

    if db is None:
        return
    end = deadline if deadline is not None else pd.Timestamp(datetime.combine(date.fromisoformat(target_date), time(17, 0), tzinfo=NEW_YORK))
    if pd.Timestamp(now) >= end:
        return
    try:
        exists = (db.query(ForecastLiveRecord.id).filter(ForecastLiveRecord.kind == kind, ForecastLiveRecord.asset == key,
                                                         ForecastLiveRecord.target_date == target_date).first())
        if exists is None:
            db.add(ForecastLiveRecord(kind=kind, asset=key, target_date=target_date, based_on=based_on, expected_pct=expected,
                                      low80_pct=low, high80_pct=high, event=event, recorded_at=now))
            db.commit()
    except Exception:  # noqa: BLE001 - gravar é complementar; a previsão continua sendo mostrada
        getattr(db, "rollback", lambda: None)()
        logger.exception("Falha ao gravar a previsão de %s para %s", key, target_date)


def recorded_forecasts(db: Session | None, key: str, kind: str = "volfc") -> dict[str, dict]:
    from app.models import ForecastLiveRecord

    if db is None:
        return {}
    try:
        rows = db.query(ForecastLiveRecord).filter(ForecastLiveRecord.kind == kind, ForecastLiveRecord.asset == key).all()
    except Exception:  # noqa: BLE001 - sem gravação, o placar usa a reconstrução
        return {}
    out = {}
    for r in rows:
        if not hasattr(r, "target_date"):
            continue
        rec = r.recorded_at if r.recorded_at.tzinfo else r.recorded_at.replace(tzinfo=timezone.utc)
        out[r.target_date] = {"expected_pct": r.expected_pct, "low80_pct": r.low80_pct, "high80_pct": r.high80_pct, "event": r.event,
                              "before_session": bool(pd.Timestamp(rec) < session_start(r.target_date)), "recorded_at": rec.isoformat()}
    return out


def range_forecast(key: str, daily: pd.DataFrame | None, db: Session, now: datetime, record: bool = False) -> dict | None:
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
    holiday = us_holiday(target)
    based_on_end = pd.Timestamp(datetime.combine(bars.index[-1].date(), time(17, 0), tzinfo=NEW_YORK))
    if record and pd.Timestamp(now) >= based_on_end + pd.Timedelta(minutes=15):  # a última hora do pregão-base já chegou
        record_forecast(db, key, target.date().isoformat(), bars.index[-1].date().isoformat(), float(np.exp(mid) * 100),
                        float(np.exp(mid + model["q10"]) * 100), float(np.exp(mid + model["q90"]) * 100), bool(names), now)
    return {"target_date": target.date().isoformat(), "based_on": bars.index[-1].date().isoformat(), "us_holiday": holiday,
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
    daily = response_cache.cached(f"brief:session_daily:{key}", 300, lambda: _daily(ASSETS[key]["symbol"]))
    forecast = range_forecast(key, daily, db, now)
    try:
        session_fc = session_forecast(key, db, now)
    except Exception:  # noqa: BLE001 - previsão complementar
        logger.exception("Previsão até o fechamento indisponível para %s", key)
        session_fc = None
    try:
        fresh = freshness(key, now)
    except Exception:  # noqa: BLE001 - diagnóstico não pode derrubar a tela
        fresh = None
    return {"key": key, "label": ASSETS[key]["label"], "symbol": ASSETS[key]["symbol"], "generated_at": now.isoformat(),
            "broker": BROKER[key], "market": market, "range_forecast": forecast, "session_forecast": session_fc, "freshness": fresh,
            "hours_ahead": _hours_ahead(key, now),
            "heatmap_meta": {k: heat["assets"][key][k] for k in ("typical_range_bps", "period", "cost_source")} if key in heat["assets"] else None,
            "events": _events(key, db, now), "evidence": _evidence(key),
            "note": "Distâncias de stop por ATR são gestão de risco, não previsão. Nenhuma regra testada foi aprovada para direção."}


def _market(key: str) -> dict:
    symbol = ASSETS[key]["symbol"]
    daily = _daily(symbol)
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
        daily = response_cache.cached(f"brief:session_daily:{key}", 300, lambda s=asset["symbol"]: _daily(s))
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


FORWARD_START = pd.Timestamp("2026-10-12")  # primeiro pregão depois do congelamento do modelo (10/10/2026)


def volfc_scoreboard(key: str, daily: pd.DataFrame | None, db: Session, now: datetime) -> dict | None:
    """Placar ao vivo do volfc_v1: para cada pregão FECHADO desde FORWARD_START, previsão feita só com a
    véspera (coeficientes congelados) contra a amplitude realizada. Reconstruível a partir do diário."""
    from app import volfc

    result = _result("volfc_v1.json")
    if not result or key not in result.get("app_model", {}) or daily is None or len(daily) < 30:
        return None
    model = result["app_model"][key]
    coef = np.asarray(model["coef"])
    bars = daily.copy()
    idx = pd.DatetimeIndex(bars.index)
    bars.index = (idx.tz_localize(None) if idx.tz is not None else idx).normalize()
    trading_today = (now.astimezone(NEW_YORK) + timedelta(hours=7)).date()
    if bars.index[-1].date() >= trading_today:
        bars = bars.iloc[:-1]
    rng = ((bars["high"] - bars["low"]) / bars["close"].shift(1)).dropna()
    rng = rng[rng > 0]
    lr = np.log(rng)
    feats = volfc.features(lr)
    events = db.query(EconomicEvent).filter(EconomicEvent.event_date >= FORWARD_START.tz_localize("UTC") - timedelta(days=1)).all()
    event_days = {_as_utc(e.event_date).tz_convert(NEW_YORK).date() for e in events
                  if calendar_risk.event_type(e.event_name) in FORECAST_EVENTS}
    stored = recorded_forecasts(db, key)
    rows = []
    for i in range(1, len(lr)):
        day = lr.index[i]
        if day < FORWARD_START:
            continue
        f = feats.iloc[i - 1]  # só a véspera
        if f[["d", "w", "m"]].isna().any():
            continue
        ev = 1.0 if day.date() in event_days else 0.0
        mid = float(coef[0] + coef[1] * f["d"] + coef[2] * f["w"] + coef[3] * f["m"] + coef[4] * ev)
        low, high = mid + model["q10"], mid + model["q90"]
        saved = stored.get(day.date().isoformat())
        if saved:  # a previsão gravada antes manda; a reconstrução só preenche dias sem gravação
            mid, low, high = (float(np.log(saved[k] / 100)) for k in ("expected_pct", "low80_pct", "high80_pct"))
            ev = 1.0 if saved["event"] else 0.0
        real = float(lr.iloc[i])
        rows.append({"date": day.date().isoformat(), "expected_pct": float(np.exp(mid) * 100),
                     "low80_pct": float(np.exp(low) * 100), "high80_pct": float(np.exp(high) * 100),
                     "realized_pct": float(np.exp(real) * 100), "atr14_pct": float(np.exp(f["atr14"]) * 100),
                     "inside80": bool(low <= real <= high), "event": bool(ev),
                     "registered": ("antes" if saved["before_session"] else "durante") if saved else None,
                     "_err": (real - mid) ** 2, "_err_atr": (real - f["atr14"]) ** 2})
    n = len(rows)
    inside = int(sum(bool(r["inside80"]) for r in rows))
    err, err_atr = float(sum(r["_err"] for r in rows)), float(sum(r["_err_atr"] for r in rows))
    summary = {"days": n, "inside80": inside, "coverage80": inside / n if n else None,
               "beats_atr_days": int(sum(bool(r["_err"] < r["_err_atr"]) for r in rows)),
               "mse_ratio_vs_atr": err / err_atr if n and err_atr else None,
               "registered_before": int(sum(r["registered"] == "antes" for r in rows))}
    for r in rows:
        r.pop("_err"), r.pop("_err_atr")
    return {"start": FORWARD_START.date().isoformat(), "summary": summary, "rows": rows[-30:],
            "note": "Acompanhamento ao vivo: coeficientes congelados em 10/10/2026; cada previsão usa só os dados até a véspera. Com poucos dias, o placar ainda é ruído."}


@router.get("/volfc-scoreboard")
def volfc_scoreboard_all(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    out = {}
    for key, asset in ASSETS.items():
        daily = response_cache.cached(f"brief:session_daily:{key}", 300, lambda s=asset["symbol"]: _daily(s))
        out[key] = {"label": asset["label"], **(volfc_scoreboard(key, daily, db, now) or {"summary": None, "rows": []})}
    return {"generated_at": now.isoformat(), "assets": out}


PLAN_STOPS = (1.0, 1.5, 2.0)

PLAN_TARGETS = (1.0, 2.0, 3.0)


def _rate(rows: list[dict], direction: str, stop_atr: float, target_r: float, ny_hour: int | None) -> dict | None:
    for r in rows:
        if r["direction"] == direction and r["stop_atr"] == stop_atr and r["target_r"] == target_r and r["ny_hour"] == ny_hour:
            return r
    return None


BASIS_NOTE = ("O preço do gráfico é o do futuro (Yahoo, ~15 min de atraso). O CFD da corretora tem outro preço: em 14/10/2026 "
              "o US100.s estava ~1% acima do NQ=F e o XAUUSD.s ~0,7% abaixo do GC=F. Use as DISTÂNCIAS a partir da sua entrada, "
              "ou informe o seu preço no MT5.")


def trade_plan(key: str, direction: str, stop_atr: float, market: dict, forecast: dict | None, events: list[dict],
               now: datetime, entry: float | None = None, session_fc: dict | None = None) -> dict:
    """Plano para a direção que o USUÁRIO escolheu: níveis por ATR e a chance MEDIDA de cada alvo antes do stop.

    A confiança vem de scripts/build_trade_plan_rates.py (taxa-base 2023-2026, compra no ask e venda no bid,
    stop primeiro quando os dois tocam na mesma barra). Não é previsão de direção nem recomendação.
    """
    rates = _result("trade_plan_rates.json") or {"assets": {}}
    rows = rates["assets"].get(key, {})
    recent, older = rows.get("recent", []), rows.get("older", [])
    price, atr_h1 = market.get("price"), market.get("atr_h1")
    if not price or not atr_h1:
        return {"available": False, "reason": "Preço ou ATR indisponível agora."}
    entry_source = "mt5" if entry else "chart"
    price = float(entry) if entry else price
    side = 1 if direction == "long" else -1
    stop_dist = stop_atr * atr_h1
    ny_hour = now.astimezone(NEW_YORK).hour
    targets = []
    for t in PLAN_TARGETS:
        overall = _rate(recent, direction, stop_atr, t, None)
        hour = _rate(recent, direction, stop_atr, t, ny_hour)
        old = _rate(older, direction, stop_atr, t, None)
        targets.append({
            "target_r": t, "price": price + side * t * stop_dist, "distance": t * stop_dist,
            "p_target": overall["p_target"] if overall else None, "p_stop": overall["p_stop"] if overall else None,
            "p_open_24h": overall["p_open_24h"] if overall else None, "mean_r": overall["mean_r"] if overall else None,
            "n": overall["n"] if overall else None,
            "p_target_this_hour": hour["p_target"] if hour else None, "n_this_hour": hour["n"] if hour else None,
            "p_target_2019_2022": old["p_target"] if old else None,
        })
    warnings = []
    if forecast and forecast.get("expected_price"):
        exp_move = forecast["expected_price"]
        for tg in targets:
            tg["share_of_expected_range"] = tg["distance"] / exp_move
        if targets[1]["distance"] > exp_move:
            warnings.append("O alvo 2R fica além da amplitude prevista para o pregão inteiro: tende a precisar de mais de um dia.")
        if stop_dist < 0.2 * exp_move:
            warnings.append("Stop curto perto do movimento previsto do dia: o ruído costuma alcançá-lo.")
        if forecast.get("us_holiday"):
            warnings.append(f"Feriado nos EUA ({forecast['us_holiday']}): pregão tende a ser atípico.")
    if session_fc and not session_fc.get("closed"):
        far = [t for t in targets if t["distance"] > session_fc["high80_points"]]
        if far:
            warnings.append(f"TP{int(far[0]['target_r'])} fica além do que o mercado anda até o fechamento de NY em 8 de cada 10 dias "
                            f"({_br(session_fc['high80_points'], 2)}): tende a ficar para a noite ou para amanhã.")
    soon = [e for e in events if e.get("measured") and _as_utc(e["event_date"]) <= pd.Timestamp(now) + pd.Timedelta(hours=24)]
    for e in soon:
        warnings.append(f"{e['event_name']} nas próximas 24 h: o movimento costuma multiplicar por {_br(e['post30'], 1)} na primeira meia hora.")
    broker = BROKER[key]
    if broker.get("spread_points"):
        warnings.append(f"Spread no {broker['symbol']}: {_br(broker['spread_points'], 2 if broker['spread_points'] >= 0.1 else 5)}, que é {_br(broker['spread_points'] / stop_dist * 100, 1)}% do stop.")
    min_risk = stop_dist * broker["contract_size"] * broker["volume_min"]
    min_lot = {"symbol": broker["symbol"], "volume_min": broker["volume_min"], "risk_usd": round(min_risk, 2),
               "balance_1pct": round(min_risk / 0.01, 0), "balance_2pct": round(min_risk / 0.02, 0)}
    return {
        "available": True, "asset": key, "direction": direction, "stop_atr": stop_atr, "entry": price, "entry_source": entry_source,
        "min_lot": min_lot,
        "basis_note": None if entry_source == "mt5" else BASIS_NOTE,
        "stop": price - side * stop_dist, "stop_distance": stop_dist, "atr_h1": atr_h1, "ny_hour": ny_hour,
        "targets": targets, "warnings": warnings, "measured_period": "jan/2023 a set/2026",
        "method": "Taxa-base medida: toda hora cheia, compra no ask e venda no bid, stop por ATR(14) de 1 h; até 24 h.",
        "note": "Plano para a direção que você escolheu. A chance é a frequência histórica de bater o alvo antes do stop em "
                "qualquer entrada desse tipo: não é sinal, e nenhuma regra de direção foi aprovada nos testes.",
    }


@router.get("/trade-plan/{key}")
def trade_plan_endpoint(key: str, direction: str = "long", stop_atr: float = 1.5, entry: float | None = None,
                        db: Session = Depends(get_db)):
    key = key.upper()
    if key not in ASSETS:
        raise HTTPException(404, f"Ativo sem estudo: {key}")
    if direction not in ("long", "short") or stop_atr not in PLAN_STOPS:
        raise HTTPException(422, "direction deve ser long ou short; stop_atr 1.0, 1.5 ou 2.0")
    now = datetime.now(timezone.utc)
    market = response_cache.cached(f"brief:market:{key}", 120, lambda: _market(key))
    daily = response_cache.cached(f"brief:session_daily:{key}", 300, lambda: _daily(ASSETS[key]["symbol"]))
    forecast = range_forecast(key, daily, db, now)
    if entry is not None and entry <= 0:
        raise HTTPException(422, "entry deve ser o preço positivo da sua entrada no MT5")
    try:
        session_fc = session_forecast(key, db, now)
    except Exception:  # noqa: BLE001
        session_fc = None
    return trade_plan(key, direction, stop_atr, market, forecast, _events(key, db, now), now, entry=entry, session_fc=session_fc)


def _pct(x: float | None, d: int = 0) -> str:
    return "—" if x is None else f"{_br(x * 100, d)}%"


def build_report(key: str, db: Session, now: datetime) -> dict:
    """Análise completa em um clique: só números medidos, organizados para ler e compartilhar."""
    asset = ASSETS[key]
    label = asset["label"]
    market = response_cache.cached(f"brief:market:{key}", 120, lambda: _market(key))
    daily = response_cache.cached(f"brief:session_daily:{key}", 300, lambda: _daily(asset["symbol"]))
    forecast = range_forecast(key, daily, db, now)
    events = _events(key, db, now)
    hours = _hours_ahead(key, now)
    board = volfc_scoreboard(key, daily, db, now)
    plans = {d: trade_plan(key, d, 1.5, market, forecast, events, now) for d in ("long", "short")}
    price = market.get("price")
    dp = 2 if (price or 0) >= 10 else 5
    sections = []

    bullets = []
    if price:
        change = market.get("change_pct")
        bullets.append(f"Preço {_br(price, dp)}" + (f" ({'+' if change >= 0 else ''}{_br(change, 2)}% no dia)." if change is not None else "."))
    trend = market.get("trend") or {}
    if trend.get("agreement"):
        bullets.append(f"Tendência de 1, 3 e 12 meses: {trend['agreement']} (descrição do preço; o teste dessa regra não aprovou).")
    if market.get("atr_d1"):
        bullets.append(f"Movimento típico: {_br(market['atr_d1'], dp)} por dia e {_br(market['atr_h1'], dp)} por hora (ATR).")
    sections.append({"title": "Onde está o preço", "bullets": bullets})

    bullets = []
    if forecast:
        day = pd.Timestamp(forecast["target_date"]).strftime("%d/%m")
        bullets.append(f"Pregão de {day}: deve mexer cerca de {_br(forecast['expected_pct'], 2)}% entre máxima e mínima "
                       f"(8 em 10 dias: {_br(forecast['low80_pct'], 2)}% a {_br(forecast['high80_pct'], 2)}%).")
        ratio = forecast["expected_pct"] / forecast["atr14_pct"] - 1 if forecast.get("atr14_pct") else None
        if ratio is not None:
            bullets.append(f"Isso é {_br(abs(ratio) * 100, 0)}% {'acima' if ratio >= 0 else 'abaixo'} da média dos últimos 14 dias.")
        if forecast.get("event"):
            bullets.append(f"Já considera {forecast['event']} nesse dia.")
        if forecast.get("us_holiday"):
            bullets.append(f"Feriado nos EUA ({forecast['us_holiday']}): o pregão tende a ser mais calmo que o previsto.")
    if board and board["summary"]["days"]:
        sm = board["summary"]
        bullets.append(f"Placar ao vivo da previsão: {sm['inside80']} de {sm['days']} pregões dentro da faixa de 80% desde {pd.Timestamp(board['start']).strftime('%d/%m')}.")
    sections.append({"title": "Quanto deve mexer", "bullets": bullets or ["Previsão indisponível agora."]})

    bullets = []
    for e in events[:4]:
        when = _as_utc(e["event_date"]).tz_convert("America/Sao_Paulo").strftime("%d/%m %H:%M")
        if e.get("measured") and e.get("post30"):
            bullets.append(f"{e['event_name']} em {when} (Brasília): costuma multiplicar o movimento por {_br(e['post30'], 1)} na primeira meia hora.")
        else:
            bullets.append(f"{e['event_name']} em {when} (Brasília).")
    sections.append({"title": "Eventos", "bullets": bullets or ["Nenhum evento de alto impacto nos próximos 3 dias."]})

    bullets = []
    open_hours = [h for h in hours if h.get("ratio") is not None]
    if open_hours:
        busiest = max(open_hours, key=lambda h: h["ratio"])
        when = pd.Timestamp(busiest["starts_at"]).tz_convert("America/Sao_Paulo").strftime("%d/%m %Hh")
        now_h = hours[0]
        if now_h.get("ratio") is not None:
            bullets.append(f"A hora atual costuma ter {_br(now_h['ratio'], 1)}x o movimento médio.")
        bullets.append(f"Hora mais agitada nas próximas 8: {when} (Brasília), com {_br(busiest['ratio'], 1)}x. Agitado é risco maior, não oportunidade garantida.")
    broker = BROKER[key]
    if broker.get("spread_points") and market.get("atr_h1"):
        bullets.append(f"Custo no {broker['symbol']}: spread de {_br(broker['spread_points'], 2 if broker['spread_points'] >= 0.1 else 5)} contra {_br(market['atr_h1'], dp)} de movimento típico por hora.")
    digest = hours_digest(key, now)
    if digest:
        bullets = [b for b in digest["bullets"] if b.startswith(("Melhor janela", "Horário de pico", "Evite", "No "))] + bullets
    sections.append({"title": "Horário e custo", "bullets": bullets or ["Mercado fechado nas próximas horas."]})

    for direction, word in (("long", "compra"), ("short", "venda")):
        plan = plans[direction]
        if not plan.get("available"):
            continue
        t = plan["targets"]
        below, above = ("abaixo", "acima") if direction == "long" else ("acima", "abaixo")
        sections.append({"title": "Se você comprar" if direction == "long" else "Se você vender", "bullets": [
            f"Plano de {word}: stop {_br(plan['stop_distance'], dp)} {below} da sua entrada (1,5 ATR de 1 hora).",
            *[f"TP{int(x['target_r'])} {_br(x['distance'], dp)} {above} da entrada: bateu antes do stop em {_pct(x['p_target'])} das entradas medidas."
              for x in t],
        ]})

    tested = _evidence(key)
    sections.append({"title": "O que já testamos neste ativo", "bullets": [f"{x['title']}: {x['detail']}" for x in tested]})
    if price:
        sections[0]["bullets"].append("O preço acima é o do futuro (Yahoo). Na corretora o CFD tem outro preço: use as distâncias dos planos a partir da sua entrada no MT5.")
    disclaimer = ("Análise gerada a partir de dados medidos (Dukascopy 2019-2026, histórico diário e calendário oficial). "
                  "Mostra quanto o mercado costuma mexer, quanto custa e a chance real de cada alvo; não diz para onde o preço vai "
                  "e não é recomendação. A decisão é sua.")
    lines = [f"Análise OneB — {label} — {now.astimezone(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M')} (Brasília)", ""]
    for sec in sections:
        lines.append(sec["title"].upper())
        lines += [f"• {b}" for b in sec["bullets"]]
        lines.append("")
    lines.append(disclaimer)
    return {"key": key, "label": label, "generated_at": now.isoformat(), "sections": sections, "disclaimer": disclaimer,
            "text": "\n".join(lines)}


@router.get("/report/{key}")
def report(key: str, db: Session = Depends(get_db)):
    key = key.upper()
    if key not in ASSETS:
        raise HTTPException(404, f"Ativo sem estudo: {key}")
    return build_report(key, db, datetime.now(timezone.utc))


BRASILIA = ZoneInfo("America/Sao_Paulo")


def _br_offset(now: datetime) -> int:
    """Horas de Brasília menos Nova York hoje (1 no horário de verão americano, 2 fora dele)."""
    return (now.astimezone(BRASILIA).hour - now.astimezone(NEW_YORK).hour) % 24


def _span(w: list[int], offset: int) -> str:
    a, b = (w[0] + offset) % 24, (w[1] + offset) % 24
    return f"{a:02d}h às {b:02d}h"


def hours_digest(key: str, now: datetime) -> dict | None:
    """Guia de horários do ativo em frases prontas, no horário de Brasília de hoje."""
    guide = _result("hours_guide.json")
    if not guide or key not in guide["assets"]:
        return None
    g = guide["assets"][key]
    off = _br_offset(now)
    w = g["windows"]
    bullets = []
    if g.get("all_expensive"):
        bullets.append(f"No {g['broker_symbol']} o spread é caro em todas as horas (5% ou mais do movimento típico). "
                       "Para índice americano nessa corretora, o US100.s sai muito mais barato.")
    if w.get("principal"):
        bullets.append("Melhor janela para operar: " + " e ".join(_span(x, off) for x in w["principal"])
                       + " (Brasília). O mercado anda o bastante para stop e alvo fazerem sentido, com custo baixo.")
    if w.get("pico"):
        bullets.append("Horário de pico: " + " e ".join(_span(x, off) for x in w["pico"])
                       + ". É quando mais mexe (abertura de Nova York): alvo chega mais rápido, mas o stop também. Reduza o lote.")
    if w.get("evitar"):
        bullets.append("Evite: " + " e ".join(_span(x, off) for x in w["evitar"]) + " (spread caro ou pico de spread na virada do dia).")
    if w.get("parado"):
        bullets.append("Mercado parado: " + " e ".join(_span(x, off) for x in w["parado"])
                       + ". O custo pesa mais e o stop vira ruído.")
    days = g.get("weekday_ratio") or {}
    if days:
        busiest = max(days, key=days.get)
        calmest = min(days, key=days.get)
        bullets.append(f"Dia mais agitado: {busiest} ({_br(days[busiest], 2)}x a hora típica); mais calmo: {calmest} ({_br(days[calmest], 2)}x).")
    if g.get("plan_p2r_range"):
        lo, hi = g["plan_p2r_range"]
        bullets.append(f"A chance de o plano padrão bater 2R varia de {_br(lo * 100, 0)}% a {_br(hi * 100, 0)}% conforme a hora, "
                       f"mas o teste pré-registrado mostrou que essa diferença é ruído: {guide['direction_test']['summary']}")
    hours = []
    for h in g["hours"]:
        hours.append({**h, "br_hour": (h["ny_hour"] + off) % 24})
    return {"key": key, "label": g["label"], "broker_symbol": g.get("broker_symbol"), "bullets": bullets, "hours": hours,
            "windows": w, "br_offset": off, "period": g["period"], "criteria": guide["criteria"],
            "direction_test": guide["direction_test"]}


@router.get("/hours-guide")
def hours_guide_all():
    now = datetime.now(timezone.utc)
    return {"generated_at": now.isoformat(), "assets": {k: hours_digest(k, now) for k in ASSETS}}


def _last_session(now: datetime) -> pd.Timestamp:
    """Último pregão (dia de negociação 17h-17h de NY) já encerrado."""
    day = pd.Timestamp((now.astimezone(NEW_YORK) + timedelta(hours=7)).date()) - pd.offsets.BDay(1)
    return day.normalize()


def freshness(key: str, now: datetime) -> dict:
    """Idade e integridade dos dados ao vivo de um ativo (o que a tela e a IA mostram)."""
    sym = ASSETS[key]["symbol"]
    daily = response_cache.cached(f"brief:session_daily:{key}", 300, lambda: _daily(sym))
    intra = response_cache.cached(f"health:15m:{key}", 120, lambda: market_data.get_bars(sym, period="5d", interval="15m"))
    checks = []
    out: dict = {"key": key, "symbol": sym, "source": "Yahoo Finance (futuro/câmbio)", "checks": checks}
    if daily is None or daily.empty:
        checks.append({"name": "diário", "status": "fail", "detail": "Sem histórico diário."})
    else:
        last = pd.Timestamp(daily.index[-1]).tz_localize(None) if pd.Timestamp(daily.index[-1]).tzinfo else pd.Timestamp(daily.index[-1])
        out["daily_as_of"] = last.date().isoformat()
        behind = len(pd.bdate_range(last.normalize() + pd.Timedelta(days=1), _last_session(now))) if last.normalize() < _last_session(now) else 0
        stale = bool(daily.attrs.get("cache_fallback"))
        status = "fail" if stale or behind > 2 else "warn" if behind > 0 else "ok"
        detail = ("Fonte fora do ar: usando o último dado salvo." if stale else
                  f"{behind} pregão(ões) atrasado(s)." if behind else "Em dia.")
        checks.append({"name": "diário", "status": status, "detail": detail})
    if intra is None or intra.empty:
        checks.append({"name": "preço intradiário", "status": "fail", "detail": "Sem barras de 15 min."})
    else:
        last = pd.Timestamp(intra.index[-1])
        last_utc = last.tz_convert("UTC") if last.tzinfo else last.tz_localize("UTC")
        age = (pd.Timestamp(now) - (last_utc + pd.Timedelta(minutes=15))).total_seconds() / 60
        out["intraday_age_minutes"] = round(max(age, 0), 1)
        ny = now.astimezone(NEW_YORK)
        open_ = ny.weekday() < 5 and not (ny.weekday() == 4 and ny.hour >= 17) and not (17 <= ny.hour < 18)
        recent = intra[intra.index >= intra.index[-1] - pd.Timedelta(days=2)]
        flat = int((recent["high"] == recent["low"]).sum())
        status = "ok" if (not open_ or age <= 45) else "warn" if age <= 120 else "fail"
        checks.append({"name": "preço intradiário", "status": status,
                       "detail": f"Última barra há {round(max(age, 0))} min (o Yahoo atrasa ~15 min)." + ("" if open_ else " Mercado fechado agora.")})
        if flat > len(recent) * 0.2:
            checks.append({"name": "barras planas", "status": "warn", "detail": f"{flat} barras sem movimento nos últimos 2 dias (feed fraco)."})
    status_rank = {"ok": 0, "warn": 1, "fail": 2}
    out["status"] = max((c["status"] for c in checks), key=status_rank.get, default="ok")
    out["broker_note"] = BASIS_NOTE
    return out


@router.get("/data-health")
def data_health(db: Session = Depends(get_db)):
    """Saúde dos dados que a tela e a IA usam: idade, atraso, fonte fora do ar e calendário."""
    now = datetime.now(timezone.utc)
    assets = {k: freshness(k, now) for k in ASSETS}
    upcoming = (db.query(EconomicEvent).filter(EconomicEvent.event_date >= now)
                .filter(EconomicEvent.event_date <= now + timedelta(days=7)).all())
    fake_fomc = db.query(EconomicEvent).filter(EconomicEvent.event_name == "FOMC Press Release").count()
    cal_status = "fail" if fake_fomc else "warn" if not upcoming else "ok"
    calendar = {"status": cal_status, "upcoming_7d": len(upcoming), "fake_fomc_rows": fake_fomc,
                "detail": ("Há linhas de FOMC falso no banco: rode a atualização do calendário." if fake_fomc else
                           "Nenhum evento nos próximos 7 dias: a coleta do calendário pode estar parada." if not upcoming else
                           f"{len(upcoming)} evento(s) nos próximos 7 dias.")}
    rank = {"ok": 0, "warn": 1, "fail": 2}
    overall = max([a["status"] for a in assets.values()] + [cal_status], key=rank.get)
    return {"generated_at": now.isoformat(), "status": overall, "assets": assets, "calendar": calendar}


PROOF_ASSETS = ("NAS100", "XAUUSD")


def daily_diary(vol_boards: dict, plan_boards_: dict, days: int = 10) -> list[dict]:
    """Diário: por dia e ativo, o que o OneB disse (faixa prevista, plano das 10:30) e o que aconteceu.

    Só junta placares que já existem (volfc_v1 e plan_live_v1); nada é escolhido depois."""
    by_day: dict[str, dict] = {}
    for key, board in vol_boards.items():
        for r in board.get("rows", []):
            by_day.setdefault(r["date"], {}).setdefault(key, {})["range"] = {
                "expected_pct": r["expected_pct"], "low80_pct": r["low80_pct"], "high80_pct": r["high80_pct"],
                "realized_pct": r["realized_pct"], "inside80": r["inside80"], "event": r["event"]}
    for key, b in plan_boards_.items():
        for r in ((b.get("live") or {}).get("rows") or []):
            by_day.setdefault(r["date"], {}).setdefault(key, {}).setdefault("plans", {})[r["direction"]] = r["results"]
    out = []
    for day in sorted(by_day, reverse=True)[:days]:
        out.append({"date": day, "assets": [{"key": k, "label": ASSETS[k]["label"], **v} for k, v in sorted(by_day[day].items())]})
    return out
EVENT_LABEL = {"CPI": "CPI (inflação)", "NFP": "Payroll (emprego)", "FOMC": "FOMC (juros do Fed)", "GDP": "PIB", "PCE": "PCE"}


@router.get("/proof")
def proof(db: Session = Depends(get_db)):
    """'Por que confiar no OneB': o que é comprovado, o placar ao vivo, as chances reais e o teste das promessas."""
    now = datetime.now(timezone.utc)
    vf = _result("volfc_v1.json") or {}
    cal = _result("calendar_v1.json") or {}
    rates = _result("trade_plan_rates.json") or {"assets": {}}
    illusion = _result("win_rate_illusion.json") or {"assets": {}}
    lab = _result("lab_v1_summary.json") or {}
    forecast = []
    for key in PROOF_ASSETS + ("SPX500", "EURUSD"):
        a = (vf.get("assets") or {}).get(key)
        if a:
            forecast.append({"key": key, "label": ASSETS[key]["label"], "error_reduction": a["reduction_vs_baseline"],
                             "coverage80": a["coverage80"], "test_days": a["test_days"]})
    live, vol_boards = [], {}
    for key in PROOF_ASSETS:
        daily = response_cache.cached(f"brief:session_daily:{key}", 300, lambda s=ASSETS[key]["symbol"]: _daily(s))
        try:
            board = volfc_scoreboard(key, daily, db, now)
        except Exception:  # noqa: BLE001
            board = None
        if board:
            vol_boards[key] = board
            live.append({"key": key, "label": ASSETS[key]["label"], "since": board["start"], **board["summary"]})
    events = []
    for key in PROOF_ASSETS:
        vol = ((cal.get("assets") or {}).get(key) or {}).get("H1_volatility", {})
        for kind in ("CPI", "NFP", "FOMC"):
            v = vol.get(kind)
            if v and v.get("H1_passed"):
                events.append({"key": key, "label": ASSETS[key]["label"], "event": EVENT_LABEL[kind],
                               "post30": v["post30"]["median_ratio"], "events": v["post30"]["events"]})
    odds = []
    for key in PROOF_ASSETS:
        for r in (rates["assets"].get(key) or {}).get("recent", []):
            if r["ny_hour"] is None and r["stop_atr"] == 1.5:
                odds.append({"key": key, "label": ASSETS[key]["label"], "direction": r["direction"], "target_r": r["target_r"],
                             "p_target": r["p_target"], "n": r["n"]})
    promise = [{"key": k, "label": ASSETS[k]["label"], **row} for k, a in illusion["assets"].items() for row in a["rows"]]
    not_promised = [
        {"title": "Sinais de compra e venda por indicadores", "detail": f"{lab.get('candidates_total', 64)} regras clássicas testadas (médias, RSI, Bollinger, rompimentos, Duck): nenhuma sobreviveu depois de descontar o spread."},
        {"title": "Seguir a tendência de 1, 3 e 12 meses", "detail": "Sem vantagem em 17 a 23 mercados, de 2013 a 2026, depois de descontar spread e financiamento."},
        {"title": "Horário 'mágico' para comprar ou vender", "detail": "92 combinações de hora e direção testadas: nenhuma vantagem que se repetisse."},
        {"title": "Efeitos famosos (virada do mês, momentum da última hora)", "detail": "Existiam nos anos 80 e 2010; sumiram depois de publicados."},
    ]
    rp = _result("replay_v1.json") or {"assets": {}}
    replay = []
    for key in PROOF_ASSETS:
        a = rp["assets"].get(key)
        if not a:
            continue
        users = a["users"]["confirmation"]["segue_oneb"]
        for rule, label in (("aleatorio", "cara ou coroa"), ("acompanha_24h", "acompanhar as últimas 24 h"), ("contra_1h", "contrariar a última hora")):
            x = users.get(rule) or {}
            replay.append({"key": key, "label": ASSETS[key]["label"], "rule": rule, "rule_label": label, "trades": x.get("trades"),
                           "mean_r": x.get("mean_r"), "final_balance": x.get("final_balance"),
                           "passed": bool((a["direction_test"].get(rule) or {}).get("passed"))})
    plan_live = []
    boards = plan_boards(db)
    for key, b in boards.items():
        if not b.get("live"):
            continue
        for part in ("live", "retro"):
            for direction, v in b[part]["summary"].items():
                for t in v["targets"]:
                    plan_live.append({"key": key, "label": b["label"], "part": part, "direction": direction, "status": v["status"],
                                      "target_r": t["target_r"], "announced": t["announced"], "hits": t["hits"], "closed": t["closed"],
                                      "consistent": t["consistent"]})
    sres = _result("sessfc_v1.json")
    session_test = None
    if sres:
        session_test = {"passed_assets": sres.get("passed_assets", []), "assets": [
            {"key": k, "label": ASSETS[k]["label"], "error_reduction": a["reduction_vs_baseline"], "coverage80": a["coverage80"],
             "test_days": a["test_days"], "passed": a["passed"],
             "live": (sessfc_scoreboard(k, db, _m5(k)) or {}).get("summary") if a["passed"] else None}
            for k, a in (sres.get("assets") or {}).items()]}
    return {"generated_at": now.isoformat(), "forecast": forecast, "replay": replay, "plan_live": plan_live, "session_test": session_test,
            "diary": daily_diary(vol_boards, boards),
            "plan_live_start": "2026-10-15", "plan_live_retro_from": "2026-08-05", "replay_passed": rp.get("passed_rules", []), "forecast_pass": bool((vf.get("primary") or {}).get("passed")),
            "forecast_mean_reduction": (vf.get("primary") or {}).get("mean_reduction"), "live": live, "events": events,
            "odds": odds, "promise_test": promise, "promise_period": illusion.get("period"), "not_promised": not_promised}


PLAN_LIVE_ASSETS = ("NAS100", "XAUUSD")


def plan_scoreboard(key: str, m5: pd.DataFrame | None, db: Session | None = None, record: bool = False) -> dict | None:
    """Placar ao vivo do plano (plan_live_v1): chance anunciada de cada alvo contra planos registrados por regra fixa.

    Com `db`, grava os planos ao vivo (encerrado não muda mais) e soma o que já estava gravado,
    para o placar não perder os dias que saem da janela de ~60 dias das barras gratuitas."""
    from app import plan_live
    from app.setups import load_preregistered

    if (m5 is None or m5.empty) and db is None:
        return None
    m5 = m5 if m5 is not None else pd.DataFrame(columns=["open", "high", "low", "close"])
    rates = (_result("trade_plan_rates.json") or {"assets": {}})["assets"].get(key, {}).get("recent", [])
    announced = {(d, t): (r or {}).get("p_target") for d in ("long", "short") for t in plan_live.TARGETS
                 for r in [_rate(rates, d, plan_live.STOP_ATR, t, None)]}
    spread = BROKER[key].get("spread_points") or 0.0
    live = plan_live.build_plans(m5, spread, plan_live.LIVE_START) if not m5.empty else []
    retro = plan_live.build_plans(m5, spread, plan_live.RETRO_START, end=plan_live.LIVE_START) if not m5.empty else []
    stored_n = 0
    if db is not None:
        if record and (live or not m5.empty):  # só o job do agendador grava; a leitura nunca escreve
            plan_live.record(db, key, live, load_preregistered("plan_live_v1")[1], m5=m5 if not m5.empty else None)
        saved = plan_live.refresh_open(plan_live.stored(db, key, plan_live.LIVE_START), m5)
        stored_n = sum(r["recorded_live"] for r in saved)
        live = plan_live.merge(saved, live)
    return {"start": plan_live.LIVE_START.isoformat(), "entry_time_brasilia": "10:30", "stop_atr": plan_live.STOP_ATR,
            "live": {"summary": plan_live.summarize(live, announced), "rows": live[-20:], "stored": stored_n},
            "retro": {"from": plan_live.RETRO_START.isoformat(), "summary": plan_live.summarize(retro, announced)},
            "note": "Regra congelada em 14/10/2026 (plan_live_v1): todo dia útil às 10:30 de Brasília, um plano de compra e um de venda, "
                    "stop de 1,5 ATR do H1, alvos 1R, 2R e 3R, entrada já piorada pelo spread. Ninguém escolhe dia, direção ou resultado."}


def _m5(key: str) -> pd.DataFrame | None:
    try:
        return response_cache.cached(f"brief:m5:{key}", 300, lambda: market_data.get_bars(ASSETS[key]["symbol"], period="60d", interval="5m"))
    except Exception:  # noqa: BLE001
        logger.exception("Barras de 5 min indisponíveis para %s", key)
        return None


def plan_boards(db: Session) -> dict:
    """Placar do plano dos ativos: barras baixadas em paralelo (rede), banco usado em sequência (sessão não é thread-safe)."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=len(PLAN_LIVE_ASSETS)) as pool:
        bars = dict(zip(PLAN_LIVE_ASSETS, pool.map(_m5, PLAN_LIVE_ASSETS)))
    out = {}
    for key in PLAN_LIVE_ASSETS:
        try:
            board = plan_scoreboard(key, bars[key], db)
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("Placar do plano indisponível para %s", key)
            board = None
        out[key] = {"label": ASSETS[key]["label"], **(board or {"live": None, "retro": None})}
    return out


@router.get("/plan-scoreboard")
def plan_scoreboard_all(db: Session = Depends(get_db)):
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "assets": plan_boards(db)}


def sizing_table(balance: float, risk_pct: float, stop_atr: float, markets: dict[str, dict]) -> list[dict]:
    """Para cada ativo: lote para arriscar `risk_pct`% do saldo com stop de `stop_atr` ATR do H1, e se o lote mínimo cabe."""
    from app.oneb_ai.tools import position_size

    rows = []
    for key, m in markets.items():
        broker, atr_h1 = BROKER[key], (m or {}).get("atr_h1")
        if not atr_h1:
            rows.append({"key": key, "label": ASSETS[key]["label"], "symbol": broker["symbol"], "available": False})
            continue
        stop = atr_h1 * stop_atr
        ps = position_size(balance, risk_pct, stop, broker["contract_size"], broker["volume_min"], broker["volume_step"], broker["spread_points"])
        min_risk = ps["min_lot_risk"]
        rows.append({"key": key, "label": ASSETS[key]["label"], "symbol": broker["symbol"], "available": True,
                     "stop_distance": stop, "volume_min": broker["volume_min"], **ps,
                     "actual_risk_pct": ps["actual_risk"] / balance * 100 if balance else None,
                     "min_lot_risk_pct": min_risk / balance * 100 if balance else None,
                     "min_balance": min_risk / (risk_pct / 100),
                     # spread (ida e volta) como fração do stop: acima de ~10%, o custo come boa parte do 1R
                     "spread_share": broker["spread_points"] / stop if broker.get("spread_points") else None})
    rows.sort(key=lambda r: (not r["available"], r.get("min_balance") or 0))
    return rows


@router.get("/sizing")
def sizing(balance: float, risk_pct: float = 1.0, stop_atr: float = 1.5):
    """'Quanto operar': com o saldo e o risco do usuário, o lote de cada ativo e se o menor lote cabe."""
    from concurrent.futures import ThreadPoolExecutor

    if balance <= 0 or not 0 < risk_pct <= 10 or stop_atr not in PLAN_STOPS:
        raise HTTPException(422, "balance > 0, risk_pct entre 0 e 10, stop_atr 1.0, 1.5 ou 2.0")

    def market(key: str) -> dict:
        try:
            return response_cache.cached(f"brief:market:{key}", 120, lambda: _market(key))
        except Exception:  # noqa: BLE001
            logger.exception("Mercado indisponível para %s", key)
            return {}

    keys = list(ASSETS)
    with ThreadPoolExecutor(max_workers=len(keys)) as pool:
        markets = dict(zip(keys, pool.map(market, keys)))
    return {"balance": balance, "risk_pct": risk_pct, "stop_atr": stop_atr, "rows": sizing_table(balance, risk_pct, stop_atr, markets),
            "verified_at": BROKER_VERIFIED_AT,
            "note": f"Stop por ATR de 1 hora (o mesmo do plano de trade). Lote arredondado para baixo ao passo da corretora (HonorPro, conferido no MT5 em {BROKER_VERIFIED_AT[8:]}/{BROKER_VERIFIED_AT[5:7]}). "
                    "Quando o menor lote arrisca mais que o seu limite, o OneB recomenda não operar esse ativo com esse saldo."}



def _sessfc_model(key: str) -> tuple[dict | None, dict | None]:
    res = _result("sessfc_v1.json")
    if not res or key not in (res.get("app_model") or {}):
        return None, res
    return res["app_model"][key], res


def _event_days(db: Session, since: datetime) -> set:
    try:
        events = db.query(EconomicEvent).filter(EconomicEvent.event_date >= since).all()
    except Exception:  # noqa: BLE001
        return set()
    return {_as_utc(e.event_date).tz_convert(NEW_YORK).date() for e in events if calendar_risk.event_type(e.event_name) in FORECAST_EVENTS}


def session_forecast(key: str, db: Session, now: datetime, m5: pd.DataFrame | None = None, record: bool = False) -> dict | None:
    """Quanto o preço ainda deve andar das 10:30 de Brasília ao fechamento de NY (sessfc_v1), só para ativo aprovado.
    Gravada na primeira vez que é calculada (antes do fechamento) e nunca reescrita."""
    from app import sessfc

    model, _ = _sessfc_model(key)
    if model is None:
        return None
    m5 = m5 if m5 is not None else _m5(key)
    if m5 is None or m5.empty:
        return None
    fc = sessfc.forecast_today(m5, model, _event_days(db, now - timedelta(days=2)), now)
    if fc is None:
        return None
    _, entry, close = sessfc.window_bounds(date.fromisoformat(fc["date"]))
    if record and not fc["closed"]:
        record_forecast(db, key, fc["date"], fc["date"], fc["expected_pct"], fc["low80_pct"], fc["high80_pct"], fc["event"], now,
                        kind="sessfc", deadline=close)
    return {**fc, "entry_utc": entry.isoformat(), "test": "sessfc_v1"}


def sessfc_scoreboard(key: str, db: Session, m5: pd.DataFrame | None) -> dict | None:
    """Placar ao vivo da previsão até o fechamento: o gravado (ou a reconstrução, se não houver) contra o realizado."""
    from app import sessfc

    model, res = _sessfc_model(key)
    if model is None or m5 is None or m5.empty:
        return None
    start = (pd.Timestamp(res["generated_at"][:10]) + pd.offsets.BDay(1)).date()
    win = sessfc.windows(m5)
    if win.empty:
        return None
    feats = sessfc.features(win, _event_days(db, datetime.combine(start, time(0), tzinfo=timezone.utc) - timedelta(days=2)))
    stored = recorded_forecasts(db, key, kind="sessfc")
    rows = []
    for day, f in feats.iterrows():
        if day.date() < start or f[sessfc.FEATURES].isna().any():
            continue
        mid = float(sessfc.predict(model["coef"], f[sessfc.FEATURES].to_numpy()[None, :])[0])
        low, high = mid + model["q10"], mid + model["q90"]
        saved = stored.get(day.date().isoformat())
        if saved:
            mid, low, high = (float(np.log(saved[k] / 100)) for k in ("expected_pct", "low80_pct", "high80_pct"))
        real = float(f["target"])
        rows.append({"date": day.date().isoformat(), "expected_pct": float(np.exp(mid) * 100), "low80_pct": float(np.exp(low) * 100),
                     "high80_pct": float(np.exp(high) * 100), "realized_pct": float(np.exp(real) * 100),
                     "inside80": bool(low <= real <= high), "registered": "gravada" if saved else None})
    n = len(rows)
    inside = sum(r["inside80"] for r in rows)
    return {"start": start.isoformat(), "summary": {"days": n, "inside80": inside, "coverage80": inside / n if n else None},
            "rows": rows[-30:]}
