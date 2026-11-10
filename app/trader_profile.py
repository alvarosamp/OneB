from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import mean

from sqlalchemy.orm import Session

from app.models import Transaction, TransactionSide

TECH_SYMBOLS = {"NVDA", "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "TSLA", "AMD", "AVGO", "NFLX"}


@dataclass
class ClosedTrade:
    symbol: str
    entry_at: datetime
    exit_at: datetime
    quantity: float
    avg_entry: float
    exit_price: float
    pnl: float
    return_pct: float
    holding_hours: float


def build_closed_trades(transactions: list[Transaction]) -> list[ClosedTrade]:
    lots: dict[str, list[dict]] = {}
    closed: list[ClosedTrade] = []

    for tx in sorted(transactions, key=lambda t: t.executed_at):
        if tx.side == TransactionSide.BUY:
            lots.setdefault(tx.symbol, []).append(
                {"qty": tx.quantity, "price": tx.price, "entry_at": tx.executed_at}
            )
            continue

        remaining = tx.quantity
        symbol_lots = lots.setdefault(tx.symbol, [])
        while remaining > 1e-9 and symbol_lots:
            lot = symbol_lots[0]
            qty = min(remaining, lot["qty"])
            pnl = (tx.price - lot["price"]) * qty
            return_pct = ((tx.price - lot["price"]) / lot["price"] * 100) if lot["price"] else 0.0
            holding_hours = max(0.0, (tx.executed_at - lot["entry_at"]).total_seconds() / 3600)
            closed.append(
                ClosedTrade(
                    symbol=tx.symbol,
                    entry_at=lot["entry_at"],
                    exit_at=tx.executed_at,
                    quantity=round(qty, 6),
                    avg_entry=round(lot["price"], 4),
                    exit_price=round(tx.price, 4),
                    pnl=round(pnl, 2),
                    return_pct=round(return_pct, 2),
                    holding_hours=round(holding_hours, 2),
                )
            )
            lot["qty"] -= qty
            remaining -= qty
            if lot["qty"] <= 1e-9:
                symbol_lots.pop(0)

    return closed


def _group_pnl(trades: list[ClosedTrade], key_fn) -> list[dict]:
    groups: dict[str, list[ClosedTrade]] = {}
    for trade in trades:
        groups.setdefault(key_fn(trade), []).append(trade)
    rows = []
    for key, items in groups.items():
        pnl = sum(t.pnl for t in items)
        rows.append(
            {
                "key": key,
                "trades": len(items),
                "pnl": round(pnl, 2),
                "win_rate": round(sum(1 for t in items if t.pnl > 0) / len(items) * 100, 2),
                "avg_return_pct": round(mean(t.return_pct for t in items), 2),
            }
        )
    return sorted(rows, key=lambda row: row["pnl"], reverse=True)


def analyze_trader_profile(db: Session, user_id: int) -> dict:
    transactions = (
        db.query(Transaction).filter(Transaction.user_id == user_id).order_by(Transaction.executed_at).all()
    )
    closed = build_closed_trades(transactions)
    open_symbols = sorted({t.symbol for t in transactions if t.side == TransactionSide.BUY})

    total_pnl = round(sum(t.pnl for t in closed), 2)
    wins = [t for t in closed if t.pnl > 0]
    losses = [t for t in closed if t.pnl < 0]
    win_rate = round(len(wins) / len(closed) * 100, 2) if closed else 0.0
    avg_win = round(mean(t.pnl for t in wins), 2) if wins else 0.0
    avg_loss = round(mean(t.pnl for t in losses), 2) if losses else 0.0
    expectancy = round((win_rate / 100) * avg_win + (1 - win_rate / 100) * avg_loss, 2) if closed else 0.0
    profit_factor = round(sum(t.pnl for t in wins) / abs(sum(t.pnl for t in losses)), 2) if losses else (999 if wins else 0)
    avg_holding_hours = round(mean(t.holding_hours for t in closed), 2) if closed else 0.0

    by_symbol = _group_pnl(closed, lambda t: t.symbol)
    by_hour = _group_pnl(closed, lambda t: f"{t.entry_at.hour:02d}:00")
    by_style = _group_pnl(
        closed,
        lambda t: "intraday" if t.holding_hours < 24 else "swing curto" if t.holding_hours < 24 * 7 else "swing longo",
    )

    insights = []
    if len(closed) < 5:
        insights.append("Ainda ha poucas operacoes fechadas; registre mais saidas para o perfil ficar confiavel.")
    if by_symbol:
        best = by_symbol[0]
        worst = by_symbol[-1]
        insights.append(f"Melhor simbolo ate agora: {best['key']} com P&L de US$ {best['pnl']:.2f}.")
        if worst["pnl"] < 0:
            insights.append(f"Pior simbolo ate agora: {worst['key']} com P&L de US$ {worst['pnl']:.2f}.")
    tech_trades = [t for t in closed if t.symbol in TECH_SYMBOLS]
    if closed and len(tech_trades) / len(closed) > 0.6:
        insights.append("Seu diario esta concentrado em tecnologia; cuidado com correlacao em quedas do Nasdaq.")
    if avg_loss < 0 and avg_win > 0 and abs(avg_loss) > avg_win:
        insights.append("Sua perda media esta maior que o ganho medio; melhorar stop/entrada pode ter impacto alto.")
    if profit_factor and profit_factor < 1:
        insights.append("Profit factor abaixo de 1: as perdas fechadas superam os ganhos fechados.")
    if by_hour and len(by_hour) > 1:
        best_hour = by_hour[0]
        worst_hour = by_hour[-1]
        insights.append(f"Melhor horario de entrada registrado: {best_hour['key']}. Pior horario: {worst_hour['key']}.")

    journal = [
        {
            "symbol": t.symbol,
            "entry_at": t.entry_at.isoformat(),
            "exit_at": t.exit_at.isoformat(),
            "quantity": t.quantity,
            "avg_entry": t.avg_entry,
            "exit_price": t.exit_price,
            "pnl": t.pnl,
            "return_pct": t.return_pct,
            "holding_hours": t.holding_hours,
            "lesson": _trade_lesson(t),
        }
        for t in sorted(closed, key=lambda trade: trade.exit_at, reverse=True)[:30]
    ]

    return {
        "summary": {
            "transactions": len(transactions),
            "closed_trades": len(closed),
            "open_symbols": open_symbols,
            "total_pnl": total_pnl,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "expectancy": expectancy,
            "profit_factor": profit_factor,
            "avg_holding_hours": avg_holding_hours,
        },
        "by_symbol": by_symbol[:12],
        "by_hour": by_hour[:12],
        "by_style": by_style,
        "insights": insights,
        "journal": journal,
    }


def _trade_lesson(trade: ClosedTrade) -> str:
    if trade.pnl > 0 and trade.holding_hours < 1:
        return "Operacao vencedora muito curta; avalie se saiu cedo demais ou se foi scalping planejado."
    if trade.pnl > 0:
        return "Operacao vencedora; compare entrada e saida com noticias/alertas do periodo."
    if trade.return_pct < -5:
        return "Perda relevante; revise se o stop estava definido antes da entrada."
    if trade.holding_hours < 1:
        return "Perda rapida; cuidado com entrada impulsiva ou volatilidade logo apos o sinal."
    return "Operacao perdedora; revise tese contraria, tamanho da posicao e criterio de saida."
