"""Painel de risco por ativo: junta o que a pesquisa comprovou (regime, volatilidade, tamanho de
posição por risco, risco de resultado) com o contexto de notícias. Informa; não recomenda."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.research import earnings as earn
from app.research import regimes
from app.research.strategies import atr

TARGET_VOL = 0.15  # exposição reduzida acima de 15% a.a. (vol-alvo testado na pesquisa)
ATR_STOP_MULT = 3.0

EVIDENCE = (
    "Na pesquisa (30 ações + ETFs, 2014-2026, com custos) nenhum indicador de entrada superou comprar e "
    "segurar de forma estatisticamente significativa. O que se repetiu foi a redução de risco: volatilidade-alvo "
    "e filtro de tendência cortaram a queda máxima de ~-36% para ~-15% a -26%. Este painel serve para "
    "dimensionar e monitorar risco, não para prever preço."
)


def _pct(x) -> float | None:
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x) * 100, 2)


def _earnings_block(history, table, today) -> dict:
    nxt = earn.next_earnings(table, today)
    react = earn.reactions(history, table)
    normal = history["close"].pct_change().abs().median()
    block = {"next_date": None, "days_until": None, "soon": False, "history": None}
    if nxt is not None:
        days = int((nxt.normalize() - today.normalize()).days)
        block.update(next_date=nxt.date().isoformat(), days_until=days, soon=0 <= days <= 7)
    if len(react) >= 4:
        block["history"] = {
            "events": int(len(react)),
            "avg_abs_move_pct": _pct(react.abs().mean()),
            "typical_day_move_pct": _pct(normal),
            "p05_pct": _pct(react.quantile(0.05)),
            "p95_pct": _pct(react.quantile(0.95)),
            "worst_pct": _pct(react.min()),
            "up_share_pct": round(float((react > 0).mean() * 100), 0),
        }
    return block


def _news_block(symbol: str, archive: pd.DataFrame | None, today: pd.Timestamp) -> dict:
    block = {"count_7d": 0, "count_30d": 0, "latest": [], "archive_days": 0}
    if archive is None or archive.empty:
        return block
    a = archive[archive["symbol"] == symbol].copy()
    if a.empty:
        return block
    a["published_at"] = pd.to_datetime(a["published_at"], utc=True, errors="coerce").dt.tz_localize(None)
    a = a.dropna(subset=["published_at"]).sort_values("published_at", ascending=False)
    block["count_7d"] = int((a["published_at"] >= today - pd.Timedelta(days=7)).sum())
    block["count_30d"] = int((a["published_at"] >= today - pd.Timedelta(days=30)).sum())
    block["latest"] = [
        {"published_at": r.published_at.isoformat(), "source": r.source, "headline": r.headline}
        for r in a.head(6).itertuples()
    ]
    full = pd.to_datetime(archive["published_at"], utc=True, errors="coerce").dropna()
    block["archive_days"] = int((full.max() - full.min()).days) if len(full) else 0
    return block


def build(
    symbol: str,
    history: pd.DataFrame,
    earnings_table: pd.DataFrame | None = None,
    archive: pd.DataFrame | None = None,
    risk_pct: float = 1.0,
    today: pd.Timestamp | None = None,
) -> dict:
    """`risk_pct` = % do capital que você aceita perder se o stop de 3 ATR for atingido."""
    history = history.dropna(subset=["close"])
    if len(history) < 60:
        return {"symbol": symbol, "error": "Histórico insuficiente (mínimo 60 barras diárias)."}
    today = pd.Timestamp(today) if today is not None else pd.Timestamp.now()
    if today.tzinfo is not None:
        today = today.tz_localize(None)

    c = history["close"]
    price = float(c.iloc[-1])
    ret = np.log(c).diff()
    vol20 = float(ret.tail(20).std() * np.sqrt(252))
    atr_v = float(atr(history).iloc[-1])
    stop_dist = ATR_STOP_MULT * atr_v / price
    chandelier = float(history["high"].tail(22).max() - ATR_STOP_MULT * atr_v)
    exposure = min(1.0, TARGET_VOL / vol20) if vol20 > 0 else 1.0
    by_risk = min(100.0, risk_pct / (stop_dist * 100) * 100) if stop_dist > 0 else None

    sma = lambda n: float(c.tail(n).mean()) if len(c) >= n else None
    s50, s200 = sma(50), sma(200)
    high52 = float(history["high"].tail(252).max())

    regime = regimes.regime_summary(c) if len(c) >= 220 else {"trend": None, "trend_label": None, "volatility": None, "volatility_label": None, "trend_bars": 0, "volatility_bars": 0}
    earn_b = _earnings_block(history, earnings_table, today)
    news_b = _news_block(symbol, archive, today)

    alerts = []
    if regime["trend"] == "down":
        alerts.append("Tendência de baixa: preço e média de 50 dias abaixo da média de 200 dias.")
    elif regime["trend"] == "up":
        alerts.append("Tendência de alta: preço e média de 50 dias acima da média de 200 dias.")
    if regime["volatility"] == "high":
        alerts.append("Volatilidade alta frente ao próprio histórico: posições costumam exigir stops mais largos e tamanho menor.")
    if vol20 > TARGET_VOL:
        alerts.append(f"Volatilidade de {vol20*100:.0f}% a.a. acima do alvo de {TARGET_VOL*100:.0f}%: exposição relativa sugerida {exposure*100:.0f}%.")
    if earn_b["soon"]:
        h = earn_b["history"]
        extra = f" Movimento médio histórico no dia: ±{h['avg_abs_move_pct']}% (pior {h['worst_pct']}%)." if h else ""
        alerts.append(f"Resultado trimestral em {earn_b['days_until']} dia(s).{extra}")
    if news_b["archive_days"] >= 14 and news_b["count_30d"] > 0 and news_b["count_7d"] >= 2 * news_b["count_30d"] / 4:
        alerts.append("Fluxo de notícias acima do normal nos últimos 7 dias.")
    if price <= chandelier:
        alerts.append(f"Preço abaixo do stop móvel de {ATR_STOP_MULT:.0f} ATR ({chandelier:.2f}): o ativo já recuou mais que isso desde a máxima de 22 dias.")
    if price < (s200 or -1):
        alerts.append("Preço abaixo da média de 200 dias.")

    return {
        "symbol": symbol,
        "as_of": history.index[-1].date().isoformat(),
        "price": round(price, 2),
        "regime": regime,
        "volatility": {"realized_20d_pct": round(vol20 * 100, 1), "atr_pct": round(atr_v / price * 100, 2)},
        "levels": {
            "dist_sma50_pct": round((price / s50 - 1) * 100, 2) if s50 else None,
            "dist_sma200_pct": round((price / s200 - 1) * 100, 2) if s200 else None,
            "drawdown_from_52w_high_pct": round((price / high52 - 1) * 100, 2),
        },
        "sizing": {
            "target_vol_pct": TARGET_VOL * 100,
            "relative_exposure_pct": round(exposure * 100, 0),
            "stop_atr_mult": ATR_STOP_MULT,
            "stop_distance_pct": round(stop_dist * 100, 2),
            "trailing_stop_price": round(chandelier, 2),
            "stop_breached": price <= chandelier,
            "risk_pct": risk_pct,
            "position_pct_of_capital": round(by_risk, 1) if by_risk is not None else None,
        },
        "earnings": earn_b,
        "news": news_b,
        "alerts": alerts,
        "evidence": EVIDENCE,
    }
