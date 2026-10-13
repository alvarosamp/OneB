"""Execução simulada sobre barras do broker (shadow/replay). Nunca envia ordem.

Convenções (mesmas de scripts/entry_quality.py, agora em barras):
- Barras MT5 são bid. ask = bid + spread_pontos * point.
- Compra entra no ask + slippage e sai no bid - slippage; venda espelhada.
- Risco líquido = distância até o stop + slippage de saída + comissão ida/volta.
- Stop e alvo na mesma barra: assume stop (conservador).
- Gap acima do limite durante a posição: trade CENSURADO, sem PnL inventado.
- R = PnL líquido / risco líquido inicial.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd


@dataclass(frozen=True)
class CostModel:
    point: float = 0.01
    slippage: float = 0.05
    commission_roundtrip: float = 0.1
    max_gap_minutes: int = 60

    @classmethod
    def from_config(cls, cfg: dict) -> "CostModel":
        return cls(
            point=float(cfg.get("point", 0.01)),
            slippage=float(cfg.get("slippage_price_per_side", 0.05)),
            commission_roundtrip=float(cfg.get("commission_roundtrip_per_unit", 0.1)),
            max_gap_minutes=int(cfg.get("max_gap_minutes_in_position", 60)),
        )


@dataclass
class SimTrade:
    opportunity_id: str
    direction: str
    signal_at: str
    entry_at: str
    entry: float
    stop: float
    target: float
    exit_at: str | None
    exit: float | None
    outcome: str  # TARGET | STOP | TIME_EXIT | CENSORED | SKIPPED
    reason: str
    net_risk: float
    pnl: float | None
    r: float | None
    mae_r: float | None
    mfe_r: float | None
    spread_at_entry: float
    brt_hour: int | None = None
    features: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def simulate_entry(
    bars: pd.DataFrame,
    *,
    opportunity_id: str,
    direction: str,
    signal_at: pd.Timestamp,
    stop: float,
    target_r: float | None,
    max_hold_minutes: int,
    costs: CostModel,
    brt_hour: int | None = None,
    features: dict | None = None,
    target: float | None = None,
) -> SimTrade | None:
    """Entra na abertura da primeira barra com abertura >= signal_at e gerencia até a saída.

    `signal_at` deve ser o FECHAMENTO da barra que gerou o sinal.

    `bars` são barras M5 (índice = abertura). Retorna None se não houver barra seguinte.
    """
    # Só as barras que podem importar: até o prazo máximo (+ folga). Evita varrer o histórico todo.
    start = bars.index.searchsorted(signal_at, side="left")
    after = bars.iloc[start : start + max_hold_minutes // 5 + 5]
    if after.empty:
        return None
    side = 1 if direction == "long" else -1
    first_at = after.index[0]
    first = after.iloc[0]
    spread = float(first["spread"]) * costs.point
    bid_open = float(first["open"])
    entry = (bid_open + spread if side == 1 else bid_open) + side * costs.slippage
    gross_risk = side * (entry - stop)
    base = dict(
        opportunity_id=opportunity_id, direction=direction, signal_at=signal_at.isoformat(),
        entry_at=first_at.isoformat(), entry=round(entry, 5), stop=stop, spread_at_entry=round(spread, 5),
        brt_hour=brt_hour, features=features,
    )
    if gross_risk <= 0:
        return SimTrade(**base, target=stop, exit_at=None, exit=None, outcome="SKIPPED",
                        reason="levels_already_crossed", net_risk=0.0, pnl=None, r=None, mae_r=None, mfe_r=None)
    if target is None:
        target = entry + side * target_r * gross_risk
    elif side * (target - entry) <= 0:
        # Alvo absoluto (ex.: do vendedor) já ultrapassado na entrada: não há trade.
        return SimTrade(**base, target=target, exit_at=None, exit=None, outcome="SKIPPED",
                        reason="target_already_crossed", net_risk=0.0, pnl=None, r=None, mae_r=None, mfe_r=None)
    net_risk = gross_risk + costs.slippage + costs.commission_roundtrip
    deadline = first_at + pd.Timedelta(minutes=max_hold_minutes)
    worst = best = 0.0
    prev_at = first_at
    exit_at = exit_price = None
    outcome = reason = None
    for at, bar in after.iterrows():
        if at - prev_at > pd.Timedelta(minutes=costs.max_gap_minutes):
            return SimTrade(**base, target=round(target, 5), exit_at=None, exit=None, outcome="CENSORED",
                            reason=f"gap_{int((at - prev_at).total_seconds() // 60)}min_in_position",
                            net_risk=net_risk, pnl=None, r=None, mae_r=None, mfe_r=None)
        prev_at = at
        spread_now = float(bar["spread"]) * costs.point
        # Lado executável de saída: compra sai no bid; venda sai no ask.
        exit_high = float(bar["high"]) + (0 if side == 1 else spread_now)
        exit_low = float(bar["low"]) + (0 if side == 1 else spread_now)
        exit_open = float(bar["open"]) + (0 if side == 1 else spread_now)
        adverse = exit_low if side == 1 else exit_high
        favorable = exit_high if side == 1 else exit_low
        worst = min(worst, side * (adverse - entry))
        best = max(best, side * (favorable - entry))
        hit_stop = side * (adverse - stop) <= 0
        hit_target = side * (favorable - target) >= 0
        if hit_stop:
            # Gap através do stop executa no preço observado (pior), nunca no nível.
            fill = min(stop, exit_open) if side == 1 else max(stop, exit_open)
            exit_at, exit_price, outcome, reason = at, fill - side * costs.slippage, "STOP", "stop"
            break
        if hit_target:
            exit_at, exit_price, outcome, reason = at, target - side * costs.slippage, "TARGET", "target"
            break
        if at + pd.Timedelta(minutes=5) >= deadline:
            close = float(bar["close"]) + (0 if side == 1 else spread_now)
            exit_at, exit_price, outcome, reason = at, close - side * costs.slippage, "TIME_EXIT", "max_hold"
            break
    if outcome is None:
        return SimTrade(**base, target=round(target, 5), exit_at=None, exit=None, outcome="CENSORED",
                        reason="data_ended_in_position", net_risk=net_risk, pnl=None, r=None, mae_r=None, mfe_r=None)
    pnl = side * (exit_price - entry) - costs.commission_roundtrip
    return SimTrade(
        **base, target=round(target, 5), exit_at=exit_at.isoformat(), exit=round(exit_price, 5), outcome=outcome,
        reason=reason, net_risk=round(net_risk, 5), pnl=round(pnl, 5), r=round(pnl / net_risk, 4),
        mae_r=round(worst / net_risk, 4), mfe_r=round(best / net_risk, 4),
    )


def replay_ready_signals(bars: pd.DataFrame, ready: list[dict], costs: CostModel) -> tuple[list[SimTrade], list[dict]]:
    """Executa sinais READY em ordem, uma posição por vez. Devolve (trades, ignorados)."""
    trades: list[SimTrade] = []
    ignored: list[dict] = []
    busy_until: pd.Timestamp | None = None
    for signal in ready:
        signal_at = pd.Timestamp(signal["at"])
        # A posição só libera quando a barra de saída FECHA (é quando a saída é conhecida).
        if busy_until is not None and signal_at < busy_until:
            ignored.append({"opportunity_id": signal["opportunity_id"], "reason": "position_already_open"})
            continue
        trade = simulate_entry(
            bars, opportunity_id=signal["opportunity_id"], direction=signal["direction"], signal_at=signal_at,
            stop=float(signal["stop"]), target_r=float(signal["target_r"]) if signal.get("target_r") is not None else None,
            target=float(signal["target"]) if signal.get("target") is not None else None,
            max_hold_minutes=int(signal["max_hold_minutes"]), costs=costs, brt_hour=signal.get("brt_hour"),
            features=signal.get("features"),
        )
        if trade is None:
            ignored.append({"opportunity_id": signal["opportunity_id"], "reason": "no_bar_after_signal"})
            continue
        trades.append(trade)
        if trade.exit_at is not None:
            busy_until = pd.Timestamp(trade.exit_at) + pd.Timedelta(minutes=5)
        elif trade.outcome == "CENSORED":
            busy_until = pd.Timestamp(trade.entry_at) + pd.Timedelta(minutes=int(signal["max_hold_minutes"]))
    return trades, ignored
