"""Máquina de estados de setup (plano §1.2).

Regras de construção, verificadas por teste:
- `features()` é causal: a linha t só depende de barras <= t.
- `step()` recebe uma linha por vez, em ordem; nunca olha adiante.
- O mesmo código roda em replay histórico e ao vivo (shadow), então não há
  "versão de backtest" diferente da "versão de produção".

A máquina vai até READY_TO_ENTER. Abrir/fechar posição (mesmo shadow) é papel
do executor (app.execution_sim / app.shadow), que precisa de cotação executável.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from app.opportunity import SetupState, Transition, config_hash


def resample_bars(bars: pd.DataFrame, minutes: int, *, closed_before: pd.Timestamp | None = None) -> pd.DataFrame:
    """Agrega barras (índice = abertura) em `minutes`, mantendo só barras já fechadas.

    `closed_before`: instante atual; barras cuja janela termina depois dele são
    descartadas (num replay, use o fim dos dados; ao vivo, o relógio).
    """
    rule = f"{minutes}min"
    agg = bars.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "spread": "max", "tick_volume": "sum"}
    )
    agg = agg.dropna(subset=["open", "close"])
    if closed_before is not None:
        agg = agg[agg.index + pd.Timedelta(minutes=minutes) <= closed_before]
    return agg


class BarSetup(ABC):
    """Base para setups de barra fechada."""

    name: str = "base"

    def __init__(self, config: dict):
        self.config = config
        self.version = config_hash(config)
        self.state = SetupState.IDLE
        self.context: dict = {}

    @abstractmethod
    def features(self, bars: pd.DataFrame) -> pd.DataFrame:
        """Indicadores causais; mesma linha = mesma informação disponível no fechamento."""

    @abstractmethod
    def step(self, at: pd.Timestamp, row: pd.Series) -> list[Transition]:
        """Avança uma barra fechada e devolve as transições emitidas."""

    def reset(self) -> None:
        self.state = SetupState.IDLE
        self.context = {}

    def _move(self, at: pd.Timestamp, to: SetupState, reason: str, direction: str | None = None, **payload) -> Transition:
        transition = Transition(
            at=at.isoformat(), from_state=self.state, to_state=to, reason=reason,
            direction=direction, payload=payload,
        )
        self.state = to
        return transition

    def bar_close(self, opened_at: pd.Timestamp) -> pd.Timestamp:
        """Instante em que a barra fecha: só então sua informação existe."""
        return opened_at + pd.Timedelta(minutes=int(self.config["timeframe_minutes"]))

    def run(self, bars: pd.DataFrame) -> list[Transition]:
        """Replay completo; reinicia o estado antes de começar.

        O índice das barras é a ABERTURA; cada passo é carimbado no FECHAMENTO,
        que é quando o executor pode agir. Carimbar na abertura vazaria o
        futuro (entrada no meio de uma barra ainda em formação).
        """
        self.reset()
        frame = self.features(bars)
        out: list[Transition] = []
        for opened_at, row in frame.iterrows():
            out.extend(self.step(self.bar_close(opened_at), row))
        return out
