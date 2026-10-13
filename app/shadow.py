"""Executor shadow (plano Fase 1.2): roda a máquina de estados ao vivo e abre
"posições fantasma" com a MESMA lógica de execução do replay. Zero acesso a ordens.

O núcleo não faz I/O: recebe barras M5 já fechadas e o instante atual; quem
busca dados (MT5, CSV) é o adaptador em scripts/run_shadow.py.
"""
from __future__ import annotations

import pandas as pd

from app.execution_sim import CostModel, simulate_entry
from app.opportunity import SetupState, Transition
from app.setups import build_setup
from app.setups.base import resample_bars

EXIT_STATES = {"TARGET": SetupState.TARGET, "STOP": SetupState.STOP, "TIME_EXIT": SetupState.TIME_EXIT}


class ShadowEngine:
    def __init__(self, config: dict, *, open_position: dict | None = None):
        self.config = config
        self.setup = build_setup(config)
        self.costs = CostModel.from_config(config)
        self.timeframe = int(config["timeframe_minutes"])
        self.last_bar_open: pd.Timestamp | None = None
        self.warmed_up = False
        # {opportunity_id, direction, signal_at, stop, target_r, max_hold_minutes, opened}
        self.position = open_position

    @property
    def min_history_m5_bars(self) -> int:
        """Barras M5 necessárias para a MM longa existir na barra mais recente."""
        return int(self.config["trend_sma"]) * (self.timeframe // 5) + 200

    def on_bars(self, m5: pd.DataFrame, now: pd.Timestamp) -> list[Transition]:
        """Processa as barras M10 fechadas desde a última chamada.

        Na primeira chamada a máquina é aquecida em silêncio sobre o histórico:
        estados passados não viram eventos "ao vivo".
        """
        m10 = resample_bars(m5, self.timeframe, closed_before=now)
        if m10.empty:
            return []
        frame = self.setup.features(m10)
        out: list[Transition] = []
        if not self.warmed_up:
            for opened_at, row in frame.iterrows():
                self.setup.step(self.setup.bar_close(opened_at), row)
            self.last_bar_open = frame.index[-1]
            self.warmed_up = True
            return self._manage_position(m5, now)
        new_rows = frame[frame.index > self.last_bar_open] if self.last_bar_open is not None else frame
        for opened_at, row in new_rows.iterrows():
            for transition in self.setup.step(self.setup.bar_close(opened_at), row):
                out.append(transition)
                if transition.to_state == SetupState.READY_TO_ENTER:
                    if self.position is not None:
                        # A posição anterior pode ter saído antes deste sinal: confere só com barras já fechadas.
                        ready_at = pd.Timestamp(transition.at)
                        out.extend(self._manage_position(m5[m5.index + pd.Timedelta(minutes=5) <= ready_at], ready_at))
                    if self.position is None:
                        self.position = {
                            "opportunity_id": transition.payload["opportunity_id"], "direction": transition.direction,
                            "signal_at": transition.at, "stop": float(transition.payload["stop"]),
                            "target_r": float(transition.payload["target_r"]),
                            "max_hold_minutes": int(transition.payload["max_hold_minutes"]), "opened": False,
                        }
                    else:
                        out.append(Transition(
                            at=transition.at, from_state=SetupState.READY_TO_ENTER, to_state=SetupState.EXPIRED,
                            reason="Posição shadow já aberta; sinal registrado e ignorado (uma posição por vez).",
                            direction=transition.direction, payload={"opportunity_id": transition.payload["opportunity_id"]},
                        ))
            self.last_bar_open = opened_at
        out.extend(self._manage_position(m5, now))
        return out

    def _manage_position(self, m5: pd.DataFrame, now: pd.Timestamp) -> list[Transition]:
        if self.position is None:
            return []
        pos = self.position
        trade = simulate_entry(
            m5, opportunity_id=pos["opportunity_id"], direction=pos["direction"],
            signal_at=pd.Timestamp(pos["signal_at"]), stop=pos["stop"], target_r=pos["target_r"],
            max_hold_minutes=pos["max_hold_minutes"], costs=self.costs,
        )
        if trade is None:
            return []
        out: list[Transition] = []
        if not pos["opened"]:
            pos["opened"] = True
            if trade.outcome == "SKIPPED":
                self.position = None
                return [Transition(at=trade.entry_at, from_state=SetupState.READY_TO_ENTER, to_state=SetupState.INVALIDATED,
                                   reason="Preço de entrada já além do stop na abertura seguinte.", direction=trade.direction,
                                   payload={"opportunity_id": trade.opportunity_id, "entry": trade.entry})]
            out.append(Transition(
                at=trade.entry_at, from_state=SetupState.READY_TO_ENTER, to_state=SetupState.POSITION_OPEN,
                reason="Posição shadow aberta na cotação executável (nenhuma ordem enviada).", direction=trade.direction,
                payload={"opportunity_id": trade.opportunity_id, "entry": trade.entry, "stop": trade.stop,
                         "target": trade.target, "spread": trade.spread_at_entry, "net_risk": trade.net_risk,
                         "max_hold_minutes": pos["max_hold_minutes"]},
            ))
        if trade.outcome in EXIT_STATES:
            out.append(Transition(
                at=trade.exit_at, from_state=SetupState.POSITION_OPEN, to_state=EXIT_STATES[trade.outcome],
                reason=f"Saída shadow por {trade.reason}: {trade.r:+.2f}R líquido.", direction=trade.direction,
                payload={"opportunity_id": trade.opportunity_id, "exit": trade.exit, "r": trade.r, "pnl": trade.pnl,
                         "mae_r": trade.mae_r, "mfe_r": trade.mfe_r},
            ))
            self.position = None
        elif trade.outcome == "CENSORED" and trade.reason != "data_ended_in_position":
            out.append(Transition(
                at=now.isoformat(), from_state=SetupState.POSITION_OPEN, to_state=SetupState.EXPIRED,
                reason=f"Posição shadow censurada ({trade.reason}); sem PnL atribuído.", direction=trade.direction,
                payload={"opportunity_id": trade.opportunity_id, "censored": True},
            ))
            self.position = None
        return out
