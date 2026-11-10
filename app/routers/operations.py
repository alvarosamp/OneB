from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.data_quality import validate_watchlist_data
from app.db import get_db
from app.market_data import service as market_data_service
from app.market_data import tiingo_client, yfinance_client
from app.models import AlertLog, AlertRule, AuditLog, PriceSnapshot, WatchlistItem

router = APIRouter(prefix="/api/operations", tags=["operations"], dependencies=[Depends(get_current_user)])


def _read_json(path: str) -> dict | list | None:
    target = Path(path)
    if not target.exists():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_jsonl_tail(path: str, limit: int = 20) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = target.read_text(encoding="utf-8").splitlines()[-limit:]
    except Exception:
        return rows
    for line in lines:
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _file_info(path: str) -> dict:
    target = Path(path)
    if not target.exists():
        return {"exists": False, "bytes": 0, "modified_at": None}
    modified = datetime.fromtimestamp(target.stat().st_mtime, tz=timezone.utc)
    return {"exists": True, "bytes": target.stat().st_size, "modified_at": modified.isoformat()}


def _count_cache_rows(symbol: str) -> dict:
    history = market_data_service.get_bars(symbol, period="2y", interval="1d", cache_only=True)
    return {
        "symbol": symbol,
        "rows": int(len(history)),
        "has_ohlcv": bool(
            not history.empty
            and {"open", "high", "low", "close", "volume"}.issubset(set(history.columns))
            and history[["open", "high", "low", "close", "volume"]].dropna().shape[0] >= 90
        ),
        "last_close": None if history.empty else round(float(history["close"].dropna().iloc[-1]), 2),
    }


def _load_paper_state() -> dict:
    state = _read_json("data/paper_simulator_state.json")
    if not isinstance(state, dict):
        return {
            "initial_capital": None,
            "cash": None,
            "portfolio_value": None,
            "open_positions": 0,
            "closed_trades": 0,
            "status": "missing",
        }
    positions = state.get("positions") or {}
    closed_trades = state.get("closed_trades") or []
    cash = float(state.get("cash", 0.0))
    return {
        "initial_capital": float(state.get("initial_capital", 0.0)),
        "cash": cash,
        "portfolio_value": cash,
        "open_positions": len(positions),
        "closed_trades": len(closed_trades),
        "status": "ready" if state else "missing",
    }


def _position_rows(state: dict) -> list[dict[str, Any]]:
    positions = state.get("positions") or {}
    rows = []
    for symbol, position in positions.items():
        if not isinstance(position, dict):
            continue
        entry_price = float(position.get("entry_price", 0.0) or 0.0)
        shares = int(position.get("shares", 0) or 0)
        stop = position.get("stop")
        target = position.get("target")
        rows.append(
            {
                "symbol": symbol,
                "entry_at": position.get("entry_at"),
                "entry_price": round(entry_price, 2),
                "shares": shares,
                "notional": round(entry_price * shares, 2),
                "stop": round(float(stop), 2) if stop is not None else None,
                "target": round(float(target), 2) if target is not None else None,
                "score": position.get("score"),
                "partial_taken": bool(position.get("partial_taken")),
                "lesson": "Acompanhe se o preco respeita o stop, busca o alvo ou perde a tendencia.",
            }
        )
    return sorted(rows, key=lambda row: row["symbol"])


def _event_lesson(event: dict[str, Any]) -> str:
    event_type = event.get("type")
    if event_type == "buy":
        return "Entrada simulada: revise tese, tamanho, stop e alvo antes de copiar qualquer ideia."
    if event_type == "sell":
        reason = event.get("reason")
        if reason == "stop_hit":
            return "Saida por stop: a aula aqui e respeitar invalidacao sem improvisar."
        if reason == "target_hit":
            return "Saida por alvo: compare o ganho planejado com o risco assumido."
        return "Saida por mudanca de contexto: observe como o plano reage a tendencia."
    if event_type == "partial_sell":
        return "Parcial no alvo: protege parte do resultado e ajusta o risco restante."
    if event_type == "decision":
        return "Ficar fora tambem e uma decisao operacional quando o sinal nao confirma."
    if event_type == "calibration":
        return "Calibracao: o laboratorio mede se os filtros ainda fazem sentido no historico."
    if event_type == "symbol_skipped":
        return "Dado insuficiente: sem historico confiavel, o laboratorio nao forca leitura."
    return "Use este evento para revisar processo, risco e disciplina."


def _format_lab_event(event: dict[str, Any]) -> dict[str, Any]:
    event_type = event.get("type", "event")
    title = str(event_type).replace("_", " ").title()
    if event_type == "decision":
        title = str(event.get("decision", "Decisao"))
    if event_type in {"buy", "sell", "partial_sell"} and event.get("symbol"):
        title = f"{str(event_type).replace('_', ' ').title()} {event['symbol']}"
    if event_type == "calibration":
        calibration = event.get("calibration") or {}
        title = f"Calibracao {calibration.get('precision_pct', '-')}%"
    return {
        "at": event.get("at"),
        "type": event_type,
        "title": title,
        "symbol": event.get("symbol"),
        "decision": event.get("decision"),
        "reason": event.get("reason") or (event.get("calibration") or {}).get("reason"),
        "price": event.get("price"),
        "shares": event.get("shares"),
        "pnl": event.get("pnl"),
        "score": event.get("score"),
        "lesson": _event_lesson(event),
    }


def _model_status() -> dict:
    model = _read_json("data/probability_model.json")
    history = _read_json("data/probability_model_history.json")
    latest = history[-1] if isinstance(history, list) and history else {}
    holdout = latest.get("holdout_accuracy")
    baseline = latest.get("holdout_baseline_accuracy")
    if baseline is None:
        audit = _read_json("data/feature_quality_audit.json")
        if isinstance(audit, dict):
            baseline = (audit.get("probability_model") or {}).get("holdout_baseline_accuracy")
    status = "missing"
    recommendation = "Modelo ausente; usar apenas regras e quality gate."
    if isinstance(model, dict):
        status = "research_only"
        recommendation = "Usar como veto/sinal auxiliar; nao aprovar trade sozinho."
        if holdout is not None and baseline is not None and holdout >= baseline:
            status = "candidate"
            recommendation = "Candidato a pesquisa; ainda exige validacao por regime, custos e slippage."
    return {
        "available": isinstance(model, dict),
        "status": status,
        "train_samples": model.get("train_samples") if isinstance(model, dict) else None,
        "holdout_accuracy": holdout,
        "holdout_baseline_accuracy": baseline,
        "recommendation": recommendation,
    }


def _automation_status() -> dict:
    report = _read_json("data/automation_readiness_report.json")
    if not isinstance(report, dict):
        return {"verdict": "UNKNOWN", "recommendation": "Relatorio de prontidao ausente."}
    return {
        "verdict": report.get("verdict", "UNKNOWN"),
        "long_ready": bool((report.get("long") or {}).get("ready_for_automation")),
        "short_ready": bool((report.get("short") or {}).get("ready_for_automation")),
        "recommendation": report.get("recommendation", ""),
    }


@router.get("/lab")
def paper_lab_status():
    now = datetime.now(timezone.utc)
    state = _read_json("data/paper_simulator_state.json")
    state = state if isinstance(state, dict) else {}
    validation = _read_json("data/simulation_validation_report.json")
    validation = validation if isinstance(validation, dict) else None
    replay = _read_json("data/paper_simulator_deep_replay.json")
    replay = replay if isinstance(replay, dict) else None
    readiness = _automation_status()
    events = _read_jsonl_tail("data/paper_simulator_events.jsonl", limit=60)
    formatted_events = [_format_lab_event(event) for event in events][-12:]
    last_decision = next((event for event in reversed(events) if event.get("type") in {"decision", "buy", "sell", "partial_sell"}), None)
    last_calibration = next((event for event in reversed(events) if event.get("type") == "calibration"), None)
    positions = _position_rows(state)
    cash = float(state.get("cash", 0.0) or 0.0) if state else None
    initial_capital = float(state.get("initial_capital", 0.0) or 0.0) if state else None
    closed_trades = state.get("closed_trades") if isinstance(state.get("closed_trades"), list) else []
    replay_summary = None
    if replay:
        replay_summary = {
            "status": replay.get("status"),
            "initial_capital": replay.get("initial_capital"),
            "final_value": replay.get("final_value"),
            "return_pct": replay.get("return_pct"),
            "buys": replay.get("buys"),
            "sells": replay.get("sells"),
            "closed_trades": replay.get("closed_trades"),
            "win_rate_pct": replay.get("win_rate_pct"),
            "profit_factor": replay.get("profit_factor"),
            "max_drawdown_pct": replay.get("max_drawdown_pct"),
        }
    return {
        "generated_at": now.isoformat(),
        "mode": "paper_trading",
        "status": "running" if events else "waiting_for_events",
        "headline": "Laboratorio ao vivo em paper trading",
        "disclaimer": "Carteira ficticia para ensino; nao executa ordens e nao e recomendacao de investimento.",
        "state": {
            "initial_capital": initial_capital,
            "cash": cash,
            "open_positions": len(positions),
            "closed_trades": len(closed_trades),
            "positions": positions,
        },
        "latest_decision": _format_lab_event(last_decision) if last_decision else None,
        "latest_calibration": last_calibration.get("calibration") if isinstance(last_calibration, dict) else None,
        "recent_events": formatted_events,
        "validation": {
            "generated_at": validation.get("generated_at") if validation else None,
            "can_trade_now": bool(validation.get("can_trade_now")) if validation else False,
            "decision_rule": validation.get("decision_rule") if validation else "Aguardando validacao do simulador.",
            "risk_rule": validation.get("risk_rule") if validation else "Aguardando regra de risco.",
            "market_data": validation.get("market_data") if validation else [],
        },
        "replay": replay_summary,
        "readiness": {
            "verdict": readiness.get("verdict"),
            "recommendation": readiness.get("recommendation"),
            "trade_automation_allowed": False,
        },
        "lesson_cards": [
            {
                "title": "Comprar",
                "body": "A entrada so aparece quando filtro historico, sinal atual e controle de risco passam juntos.",
            },
            {
                "title": "Vender",
                "body": "A saida nasce de stop, alvo parcial/final ou virada de tendencia, sem improviso no meio do caminho.",
            },
            {
                "title": "Nao operar",
                "body": "NO_TRADE e parte do laboratorio: ensina a preservar caixa quando o mercado nao confirma.",
            },
        ],
    }


@router.get("/health")
def operational_health(db: Session = Depends(get_db)):
    latest_snapshot = db.query(PriceSnapshot).order_by(PriceSnapshot.taken_at.desc()).first()
    now = datetime.now(timezone.utc)
    latest_at = latest_snapshot.taken_at if latest_snapshot else None
    if latest_at and latest_at.tzinfo is None:
        latest_at = latest_at.replace(tzinfo=timezone.utc)
    snapshot_age_minutes = ((now - latest_at).total_seconds() / 60) if latest_at else None
    alerts = db.query(AlertLog).order_by(AlertLog.triggered_at.desc()).limit(10).all()
    audits = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(20).all()
    data_quality = validate_watchlist_data(db)
    market_data_probe = market_data_service.get_bars("AAPL", period="2y", interval="1d", cache_only=True)
    watchlist_count = db.query(WatchlistItem).filter(WatchlistItem.active.is_(True)).count()
    alert_rule_count = db.query(AlertRule).filter(AlertRule.active.is_(True)).count()
    cache_symbols = ["AAPL", "MSFT", "NVDA", "SNAP"]
    cache_rows = [_count_cache_rows(symbol) for symbol in cache_symbols]
    cache_ready = all(row["has_ohlcv"] for row in cache_rows)
    paper = _load_paper_state()
    model = _model_status()
    automation = _automation_status()
    simulation_report = _read_json("data/simulation_validation_report.json")
    db_counts = {
        "watchlist_items": watchlist_count,
        "active_alert_rules": alert_rule_count,
        "price_snapshots": db.query(PriceSnapshot).count(),
        "alert_logs": db.query(AlertLog).count(),
        "audit_logs": db.query(AuditLog).count(),
    }
    readiness_blockers = []
    if not cache_ready:
        readiness_blockers.append("CACHE_INCOMPLETE")
    if automation.get("verdict") != "READY":
        readiness_blockers.append("HUMAN_APPROVAL_REQUIRED")
    if model.get("status") != "candidate":
        readiness_blockers.append("MODEL_NOT_APPROVED")
    if not settings.telegram_bot_token:
        readiness_blockers.append("TELEGRAM_NOT_CONFIGURED")
    status = "ok" if cache_ready else "attention"
    return {
        "status": status,
        "generated_at": now.isoformat(),
        "latest_snapshot_at": latest_at.isoformat() if latest_at else None,
        "snapshot_age_minutes": round(snapshot_age_minutes, 1) if snapshot_age_minutes is not None else None,
        "db": {
            "available": True,
            "counts": db_counts,
        },
        "providers": {
            "finnhub_configured": bool(settings.finnhub_api_key),
            "fmp_configured": bool(settings.fmp_api_key),
            "fred_configured": bool(settings.fred_api_key),
            "telegram_configured": bool(settings.telegram_bot_token),
            "market_data_provider": settings.market_data_provider,
            "active_price_provider": market_data_service.default_service.provider.name,
            "tiingo_configured": bool(settings.tiingo_api_key),
            "tiingo_role": tiingo_client.PROVIDER_ROLE,
            "yfinance_enabled": True,
            "yfinance_required_for_technical_analysis": yfinance_client.REQUIRED_FOR_TECHNICAL_ANALYSIS,
            "market_data_cache_available": not market_data_probe.empty,
            "yfinance_available": not market_data_probe.empty,
            "yfinance_role": yfinance_client.PROVIDER_ROLE,
        },
        "jobs": {
            "quote_poll_seconds": settings.quote_poll_seconds,
            "indicator_refresh_seconds": settings.indicator_refresh_seconds,
            "news_refresh_seconds": settings.news_refresh_seconds,
            "radar_bot_hour_utc": settings.radar_bot_hour_utc,
            "weekly_review_bot": f"{settings.weekly_review_bot_day_of_week} {settings.weekly_review_bot_hour_utc}:00 UTC",
        },
        "data_quality": data_quality["confidence_counts"],
        "market_cache": {
            "ready": cache_ready,
            "rows": cache_rows,
            "files": {
                "simulation_validation_report": _file_info("data/simulation_validation_report.json"),
                "probability_model": _file_info("data/probability_model.json"),
                "automation_readiness_report": _file_info("data/automation_readiness_report.json"),
            },
        },
        "paper_simulator": paper,
        "probability_model": model,
        "automation": automation,
        "last_simulation_validation": simulation_report if isinstance(simulation_report, dict) else None,
        "readiness": {
            "level": "monitoring_ready" if cache_ready else "needs_data",
            "trade_automation_allowed": False,
            "blockers": readiness_blockers,
            "recommendation": "Monitoramento, alertas, relatorios e paper trading; manter aprovacao humana para qualquer trade.",
        },
        "recent_alerts": [
            {"symbol": a.symbol, "message": a.message, "triggered_at": a.triggered_at.isoformat()} for a in alerts
        ],
        "recent_audit_logs": [
            {
                "action": a.action,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "created_at": a.created_at.isoformat(),
            }
            for a in audits
        ],
    }
