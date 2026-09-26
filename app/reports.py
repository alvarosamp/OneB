"""Builds a PDF snapshot of the monitoring dashboard: watchlist, alerts,
news and upcoming economic/earnings events. Pure function of a DB session so
it's usable both from the web route and from the Telegram /relatorio command.
"""
from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app import indicators
from app.market_data import service as market_data_service
from app.models import (
    AlertLog,
    EarningsEvent,
    EconomicEvent,
    GlobalNewsItem,
    MorningReport,
    NewsItem,
    PriceSnapshot,
    WatchlistItem,
)


def build_pdf_report(db: Session, user_id: int) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    muted = ParagraphStyle("muted", parent=styles["Normal"], textColor=colors.grey, fontSize=8)

    now = datetime.now(timezone.utc)
    story = []

    story.append(Paragraph("OneB — Relatório", styles["Title"]))
    story.append(Paragraph(f"Gerado em {now.strftime('%d/%m/%Y %H:%M UTC')}", muted))
    story.append(Spacer(1, 0.5 * cm))

    # Daily read: same scoring/bias engine behind "Resumo Diário" in the app,
    # just not previously wired into the PDF — headline, tone, opportunities,
    # risks, watch list and an action plan, not just a raw price/news dump.
    summary = build_daily_market_summary(db)
    story.append(Paragraph("Resumo do dia", styles["Heading2"]))
    story.append(Paragraph(f"<b>{summary['market_tone']}</b> — {summary['headline']}", styles["Normal"]))
    story.append(Spacer(1, 0.2 * cm))
    for takeaway in summary["key_takeaways"]:
        story.append(Paragraph(f"• {takeaway}", styles["Normal"]))
    story.append(Spacer(1, 0.4 * cm))

    def _asset_table(rows: list[dict]) -> Table:
        table_rows = [["Símbolo", "Preço", "Dia", "Score", "Viés", "RSI", "Vol.", "Dist. resist.", "Nota"]]
        for row in rows:
            table_rows.append(
                [
                    row["symbol"],
                    f"{row['price']:.2f}",
                    f"{row['change_pct']:+.2f}%",
                    str(row["score"]),
                    row["bias"],
                    f"{row['rsi']:.0f}" if row["rsi"] is not None else "-",
                    f"{row['volume_ratio']:.2f}x" if row["volume_ratio"] is not None else "-",
                    f"{row['distance_to_resistance_pct']:+.1f}%",
                    row["notes"][0] if row["notes"] else "-",
                ]
            )
        return _styled_table(
            table_rows, col_widths=[1.8 * cm, 1.8 * cm, 1.6 * cm, 1.4 * cm, 1.8 * cm, 1.2 * cm, 1.6 * cm, 1.9 * cm, 4 * cm]
        )

    if summary["opportunities"]:
        story.append(Paragraph("Oportunidades (score ≥ 65)", styles["Heading3"]))
        story.append(_asset_table(summary["opportunities"]))
        story.append(Spacer(1, 0.35 * cm))
    if summary["risks"]:
        story.append(Paragraph("Pontos de atenção", styles["Heading3"]))
        story.append(_asset_table(summary["risks"]))
        story.append(Spacer(1, 0.35 * cm))
    if summary["watch"]:
        story.append(Paragraph("Observação", styles["Heading3"]))
        story.append(_asset_table(summary["watch"]))
        story.append(Spacer(1, 0.35 * cm))

    story.append(Paragraph("Plano de ação sugerido", styles["Heading3"]))
    for step in summary["action_plan"]:
        story.append(Paragraph(f"• {step}", styles["Normal"]))
    story.append(Spacer(1, 0.6 * cm))

    # Watchlist
    story.append(Paragraph("Watchlist", styles["Heading2"]))
    items = (
        db.query(WatchlistItem)
        .filter(
            (WatchlistItem.user_id == user_id) | (WatchlistItem.user_id.is_(None)),
            WatchlistItem.active.is_(True),
        )
        .all()
    )
    rows = [["Símbolo", "Preço", "Variação", "Atualizado"]]
    for item in items:
        snap = (
            db.query(PriceSnapshot)
            .filter(PriceSnapshot.watchlist_item_id == item.id)
            .order_by(PriceSnapshot.taken_at.desc())
            .first()
        )
        if snap:
            rows.append(
                [
                    item.symbol,
                    f"{snap.price:.2f}",
                    f"{snap.change_pct:+.2f}%",
                    snap.taken_at.strftime("%d/%m %H:%M UTC"),
                ]
            )
        else:
            rows.append([item.symbol, "-", "-", "sem dados"])
    if len(rows) == 1:
        rows.append(["(watchlist vazia)", "", "", ""])
    story.append(_styled_table(rows))
    story.append(Spacer(1, 0.5 * cm))

    # Recent alerts
    story.append(Paragraph("Alertas recentes", styles["Heading2"]))
    alerts = (
        db.query(AlertLog)
        .filter((AlertLog.user_id == user_id) | (AlertLog.user_id.is_(None)))
        .order_by(AlertLog.triggered_at.desc())
        .limit(15)
        .all()
    )
    if alerts:
        alert_rows = [["Data", "Símbolo", "Mensagem"]]
        for a in alerts:
            alert_rows.append([a.triggered_at.strftime("%d/%m %H:%M"), a.symbol, a.message])
        story.append(_styled_table(alert_rows, col_widths=[2.5 * cm, 2 * cm, 11 * cm]))
    else:
        story.append(Paragraph("Nenhum alerta disparado ainda.", styles["Normal"]))
    story.append(Spacer(1, 0.5 * cm))

    # News
    story.append(Paragraph("Notícias recentes", styles["Heading2"]))
    since = now - timedelta(hours=48)
    news = (
        db.query(NewsItem)
        .filter(NewsItem.published_at >= since)
        .order_by(NewsItem.published_at.desc())
        .limit(15)
        .all()
    )
    if news:
        for n in news:
            story.append(
                Paragraph(
                    f"<b>{n.symbol}</b> ({n.published_at.strftime('%d/%m %H:%M')}) — {n.headline}",
                    styles["Normal"],
                )
            )
    else:
        story.append(Paragraph("Nenhuma notícia recente coletada.", styles["Normal"]))
    story.append(Spacer(1, 0.5 * cm))

    # Upcoming economic events
    story.append(Paragraph("Calendário econômico (próximos 7 dias)", styles["Heading2"]))
    econ = (
        db.query(EconomicEvent)
        .filter(EconomicEvent.event_date >= now, EconomicEvent.event_date <= now + timedelta(days=7))
        .order_by(EconomicEvent.event_date)
        .limit(20)
        .all()
    )
    if econ:
        econ_rows = [["Data", "Evento", "País", "Impacto"]]
        for e in econ:
            econ_rows.append([e.event_date.strftime("%d/%m %H:%M"), e.event_name, e.country, e.impact])
        story.append(_styled_table(econ_rows, col_widths=[2.5 * cm, 8 * cm, 2.5 * cm, 2.5 * cm]))
    else:
        story.append(Paragraph("Nenhum evento econômico carregado.", styles["Normal"]))
    story.append(Spacer(1, 0.5 * cm))

    # Upcoming earnings
    story.append(Paragraph("Earnings da watchlist (próximos 7 dias)", styles["Heading2"]))
    earnings = (
        db.query(EarningsEvent)
        .filter(EarningsEvent.event_date >= now, EarningsEvent.event_date <= now + timedelta(days=7))
        .order_by(EarningsEvent.event_date)
        .limit(20)
        .all()
    )
    if earnings:
        earn_rows = [["Data", "Símbolo", "EPS estimado"]]
        for e in earnings:
            eps = f"{e.eps_estimate:.2f}" if e.eps_estimate is not None else "-"
            earn_rows.append([e.event_date.strftime("%d/%m"), e.symbol, eps])
        story.append(_styled_table(earn_rows, col_widths=[2.5 * cm, 3 * cm, 3 * cm]))
    else:
        story.append(Paragraph("Nenhum earnings carregado.", styles["Normal"]))

    story.append(Spacer(1, 1 * cm))
    story.append(
        Paragraph(
            "Ferramenta apenas de monitoramento e sugestão. Não executa ordens e não constitui "
            "recomendação de investimento. Dados podem ter atraso. Valide qualquer sinal antes "
            "de decidir.",
            muted,
        )
    )

    doc.build(story)
    return buffer.getvalue()


def _last(series):
    clean = series.dropna()
    return float(clean.iloc[-1]) if not clean.empty else None


def _daily_asset_row(item: WatchlistItem) -> dict | None:
    history = market_data_service.get_bars(item.symbol, period="3mo", interval="1d")
    if history.empty or len(history) < 35:
        return None

    close = history["close"]
    price = _last(close)
    previous = float(close.iloc[-2]) if len(close) > 1 else None
    if price is None or previous in (None, 0):
        return None

    ema9 = _last(indicators.ema(close, 9))
    ema21 = _last(indicators.ema(close, 21))
    rsi = _last(indicators.rsi(close))
    macd_df = indicators.macd(close)
    macd = _last(macd_df["macd"])
    macd_signal = _last(macd_df["signal"])
    volume_ratio = _last(indicators.volume_ratio(history["volume"]))
    atr = _last(indicators.atr(history["high"], history["low"], close))
    support = float(history["low"].tail(80).min())
    resistance = float(history["high"].tail(80).max())

    change_pct = ((price - previous) / previous) * 100
    atr_pct = (atr / price) * 100 if atr else None
    distance_to_resistance_pct = ((resistance - price) / price) * 100
    distance_to_support_pct = ((support - price) / price) * 100

    score = 50
    notes = []
    if ema9 and ema21:
        if price > ema9 > ema21:
            score += 16
            notes.append("Preco acima da EMA9 e EMA21.")
        elif price < ema9 < ema21:
            score -= 16
            notes.append("Preco abaixo da EMA9 e EMA21.")
    if rsi is not None:
        if 45 <= rsi <= 68:
            score += 8
            notes.append(f"RSI saudavel em {rsi:.1f}.")
        elif rsi > 72:
            score -= 8
            notes.append(f"RSI esticado em {rsi:.1f}.")
        elif rsi < 35:
            score -= 6
            notes.append(f"RSI fraco em {rsi:.1f}.")
    if macd is not None and macd_signal is not None:
        if macd > macd_signal:
            score += 8
            notes.append("MACD acima do sinal.")
        else:
            score -= 8
            notes.append("MACD abaixo do sinal.")
    if volume_ratio is not None:
        if volume_ratio >= 1.25:
            score += 6
            notes.append(f"Volume {volume_ratio:.2f}x a media.")
        elif volume_ratio < 0.7:
            score -= 4
            notes.append(f"Volume baixo: {volume_ratio:.2f}x a media.")
    if atr_pct is not None:
        if atr_pct >= 6:
            score -= 10
            volatility_label = "Muito alta"
        elif atr_pct >= 3:
            score -= 4
            volatility_label = "Alta"
        elif atr_pct >= 1.5:
            volatility_label = "Media"
        else:
            volatility_label = "Baixa"
    else:
        volatility_label = "Sem leitura"
    if distance_to_resistance_pct < 3:
        score -= 5
        notes.append("Perto da resistencia recente.")
    if distance_to_support_pct > -3:
        score -= 5
        notes.append("Perto do suporte recente.")

    score = max(0, min(100, round(score)))
    if score >= 65:
        bias = "ALTISTA"
        trend = "Tendencia construtiva"
    elif score <= 40:
        bias = "BAIXISTA"
        trend = "Pressao ou risco elevado"
    else:
        bias = "NEUTRO"
        trend = "Aguardar confirmacao"

    return {
        "symbol": item.symbol,
        "label": item.label,
        "price": round(price, 2),
        "change_pct": round(change_pct, 2),
        "trend": trend,
        "bias": bias,
        "volatility_label": volatility_label,
        "atr_pct": round(atr_pct, 2) if atr_pct is not None else None,
        "rsi": round(rsi, 2) if rsi is not None else None,
        "volume_ratio": round(volume_ratio, 2) if volume_ratio is not None else None,
        "distance_to_resistance_pct": round(distance_to_resistance_pct, 2),
        "distance_to_support_pct": round(distance_to_support_pct, 2),
        "score": score,
        "notes": notes[:5],
    }


def build_daily_market_summary(db: Session) -> dict:
    now = datetime.now(timezone.utc)
    items = db.query(WatchlistItem).filter(WatchlistItem.active.is_(True)).order_by(WatchlistItem.symbol).all()
    rows = [row for item in items if (row := _daily_asset_row(item)) is not None]
    rows.sort(key=lambda row: row["score"], reverse=True)

    opportunities = [row for row in rows if row["score"] >= 65][:5]
    risks = sorted([row for row in rows if row["score"] <= 45 or row["volatility_label"] in {"Alta", "Muito alta"}], key=lambda row: row["score"])[:5]
    watch = [row for row in rows if 46 <= row["score"] < 65][:6]

    bullish = len([row for row in rows if row["bias"] == "ALTISTA"])
    bearish = len([row for row in rows if row["bias"] == "BAIXISTA"])
    high_vol = len([row for row in rows if row["volatility_label"] in {"Alta", "Muito alta"}])
    if not rows:
        tone = "Sem dados suficientes"
        headline = "Resumo diario indisponivel: adicione ativos na watchlist ou aguarde coleta de dados."
    elif bullish > bearish and high_vol <= max(1, len(rows) // 2):
        tone = "Construtivo com seletividade"
        headline = "Mercado monitorado com mais sinais altistas do que baixistas, mas ainda exige filtro de risco."
    elif high_vol > len(rows) // 2:
        tone = "Volatilidade elevada"
        headline = "Volatilidade domina a watchlist; priorize tamanho menor, stop claro e menos trades."
    elif bearish >= bullish:
        tone = "Defensivo"
        headline = "Pressao e sinais mistos pedem paciencia antes de novas entradas."
    else:
        tone = "Misto"
        headline = "Sinais divididos; foco em confirmacao e qualidade dos dados."

    key_takeaways = [
        f"{bullish} ativo(s) com vies altista, {bearish} com vies baixista.",
        f"{high_vol} ativo(s) com volatilidade alta ou muito alta.",
        "Evite transformar sinal tecnico em ordem sem plano de entrada, stop e alvo.",
    ]
    if opportunities:
        key_takeaways.append(
            "Melhores leituras tecnicas: " + ", ".join(f"{row['symbol']} ({row['score']})" for row in opportunities[:3]) + "."
        )
    if risks:
        key_takeaways.append(
            "Maiores pontos de atencao: " + ", ".join(f"{row['symbol']} ({row['volatility_label']})" for row in risks[:3]) + "."
        )

    econ = (
        db.query(EconomicEvent)
        .filter(EconomicEvent.event_date >= now, EconomicEvent.event_date <= now + timedelta(days=7))
        .order_by(EconomicEvent.event_date)
        .limit(6)
        .all()
    )
    macro_events = [
        {
            "date": event.event_date.isoformat(),
            "name": event.event_name,
            "country": event.country,
            "impact": event.impact,
            "forecast": event.forecast,
            "previous": event.previous,
        }
        for event in econ
    ]

    news = (
        db.query(GlobalNewsItem)
        .order_by(GlobalNewsItem.impact_score.desc(), GlobalNewsItem.published_at.desc())
        .limit(6)
        .all()
    )
    top_news = [
        {
            "headline": item.headline,
            "source": item.source,
            "category": item.category,
            "impact_score": item.impact_score,
            "published_at": item.published_at.isoformat(),
            "url": item.url,
        }
        for item in news
    ]

    action_plan = [
        "Comece pelos ativos com score alto, mas descarte os que estiverem perto demais da resistencia.",
        "Em ativos com volatilidade alta, reduza lote e prefira operar somente com stop previamente definido.",
        "Se nao houver oportunidade com score alto e risco aceitavel, o plano do dia e observar.",
        "Registre no diario a tese, gatilho, invalidacao e resultado esperado antes de qualquer ordem manual.",
    ]

    return {
        "generated_at": now,
        "headline": headline,
        "market_tone": tone,
        "key_takeaways": key_takeaways,
        "opportunities": opportunities,
        "risks": risks,
        "watch": watch,
        "macro_events": macro_events,
        "top_news": top_news,
        "action_plan": action_plan,
    }


def _levels_text(levels: dict | None) -> str:
    if not levels:
        return "-"
    p = levels["pivots"]
    return f"P {p['pivot']} | R1 {p['r1']} R2 {p['r2']} | S1 {p['s1']} S2 {p['s2']}"


def build_morning_report_pdf(report: MorningReport) -> bytes:
    """PDF snapshot of a single stored MorningReport (indices/watchlist levels,
    narrative, overnight news and today's calendar) — mirrors build_pdf_report's
    layout so it's usable both from the web route and the Telegram /matinal flow.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    muted = ParagraphStyle("muted", parent=styles["Normal"], textColor=colors.grey, fontSize=8)
    data = report.data or {}
    story = []

    story.append(Paragraph("OneB — Análise Matinal", styles["Title"]))
    story.append(Paragraph(f"Gerado em {report.generated_at.strftime('%d/%m/%Y %H:%M UTC')}", muted))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("Índices", styles["Heading2"]))
    idx_rows = [["Ativo", "Preço", "Variação", "Níveis (pivot)"]]
    for idx in data.get("indices", []):
        idx_rows.append(
            [idx["name"], f"{idx['price']:.2f}", f"{idx['change_pct']:+.2f}%", _levels_text(idx["levels"])]
        )
    if len(idx_rows) == 1:
        idx_rows.append(["(sem dados)", "", "", ""])
    story.append(_styled_table(idx_rows, col_widths=[3.5 * cm, 2.5 * cm, 2.5 * cm, 8.5 * cm]))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("Watchlist", styles["Heading2"]))
    wl_rows = [["Símbolo", "Preço", "Variação", "Níveis (pivot)"]]
    for w in data.get("watchlist", []):
        price = f"{w['price']:.2f}" if w["price"] is not None else "-"
        change = f"{w['change_pct']:+.2f}%" if w["change_pct"] is not None else "-"
        wl_rows.append([w["symbol"], price, change, _levels_text(w["levels"])])
    if len(wl_rows) == 1:
        wl_rows.append(["(watchlist vazia)", "", "", ""])
    story.append(_styled_table(wl_rows, col_widths=[3.5 * cm, 2.5 * cm, 2.5 * cm, 8.5 * cm]))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("Análise", styles["Heading2"]))
    for line in report.narrative.split("\n"):
        story.append(Paragraph(line if line.strip() else "&nbsp;", styles["Normal"]))
    story.append(Spacer(1, 0.5 * cm))

    econ = data.get("economic_events_today", [])
    story.append(Paragraph("Eventos econômicos de alto impacto hoje", styles["Heading2"]))
    if econ:
        for e in econ:
            story.append(Paragraph(f"• {e['event_name']} ({e['country']})", styles["Normal"]))
    else:
        story.append(Paragraph("Nenhum evento de alto impacto hoje.", styles["Normal"]))

    story.append(Spacer(1, 1 * cm))
    story.append(
        Paragraph(
            "Ferramenta apenas de monitoramento e sugestão. Não executa ordens e não constitui "
            "recomendação de investimento. Dados podem ter atraso. Valide qualquer sinal antes "
            "de decidir.",
            muted,
        )
    )

    doc.build(story)
    return buffer.getvalue()


def _styled_table(rows: list[list[str]], col_widths: list[float] | None = None) -> Table:
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
            ]
        )
    )
    return table
