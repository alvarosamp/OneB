"""Gold Fakeout — reimplementação aberta v1 (hipótese, não o EX5 original).

Descrição de origem (do próprio trader): M10, MM1000, rompimento de ~20 barras,
duas confirmações, janela 07:00–11:00 BRT. O que NÃO sabemos do original:
se "fakeout" significa seguir o rompimento confirmado ou operar contra o
rompimento falho; como o stop/alvo são calculados. A v1 registra uma leitura
explícita (`direction_mode="continuation"`) e o fakeout é justamente o evento
de invalidação: a barra volta para dentro do nível rompido antes de confirmar.

Toda a regra está em configs/preregistration/gold_fakeout_open_v1.json e foi
congelada antes do primeiro replay. Mudou parâmetro = nova versão.
"""
from __future__ import annotations

import pandas as pd

from app.opportunity import SetupState, Transition
from app.setups.base import BarSetup


class GoldFakeoutOpen(BarSetup):
    name = "gold_fakeout_open"

    def features(self, bars: pd.DataFrame) -> pd.DataFrame:
        cfg = self.config
        frame = bars.copy()
        sma_n = int(cfg["trend_sma"])
        look = int(cfg["break_lookback"])
        frame["sma"] = frame["close"].rolling(sma_n, min_periods=sma_n).mean()
        # Máxima/mínima das N barras ANTERIORES: shift(1) garante que a barra atual não entra.
        frame["prior_high"] = frame["high"].shift(1).rolling(look, min_periods=look).max()
        frame["prior_low"] = frame["low"].shift(1).rolling(look, min_periods=look).min()
        offset = pd.Timedelta(hours=float(cfg["server_utc_offset_hours"]) + 3.0)  # servidor -> UTC -> BRT
        brt = frame.index - offset
        minutes = brt.hour * 60 + brt.minute
        start_h, start_m = (int(x) for x in cfg["session_window_brt"][0].split(":"))
        end_h, end_m = (int(x) for x in cfg["session_window_brt"][1].split(":"))
        frame["in_window"] = (minutes >= start_h * 60 + start_m) & (minutes < end_h * 60 + end_m)
        frame["brt_hour"] = brt.hour
        return frame

    def _max_gap(self) -> pd.Timedelta:
        return pd.Timedelta(minutes=int(self.config["timeframe_minutes"]) * 2)

    def step(self, at: pd.Timestamp, row: pd.Series) -> list[Transition]:
        out: list[Transition] = []
        ctx = self.context

        # Estado terminal ou pronto da barra anterior: volta a vigiar.
        if self.state in (SetupState.READY_TO_ENTER, SetupState.INVALIDATED, SetupState.EXPIRED):
            self.state = SetupState.IDLE
            self.context = ctx = {}

        if self.state in (SetupState.WAITING_CONFIRMATION_1, SetupState.WAITING_CONFIRMATION_2):
            if at - ctx["last_at"] > self._max_gap():
                out.append(self._move(at, SetupState.EXPIRED, "Lacuna de dados entre o rompimento e a confirmação.",
                                      ctx["direction"], opportunity_id=ctx["opportunity_id"]))
                return out
            side = 1 if ctx["direction"] == "long" else -1
            holds = side * (float(row["close"]) - ctx["level"]) > 0
            ctx["extreme"] = min(ctx["extreme"], float(row["low"])) if side == 1 else max(ctx["extreme"], float(row["high"]))
            ctx["last_at"] = at
            if not holds:
                out.append(self._move(
                    at, SetupState.INVALIDATED,
                    f"Fakeout: fechou de volta {'abaixo' if side == 1 else 'acima'} do nível rompido {ctx['level']:.2f}.",
                    ctx["direction"], opportunity_id=ctx["opportunity_id"], level=ctx["level"], close=float(row["close"]),
                ))
                return out
            if self.state == SetupState.WAITING_CONFIRMATION_1:
                out.append(self._move(at, SetupState.WAITING_CONFIRMATION_2, "Confirmação 1: fechamento manteve o rompimento.",
                                      ctx["direction"], opportunity_id=ctx["opportunity_id"], close=float(row["close"])))
                return out
            out.append(self._move(
                at, SetupState.READY_TO_ENTER, "Confirmação 2: setup formado; entrada na abertura da próxima barra.",
                ctx["direction"], opportunity_id=ctx["opportunity_id"], level=ctx["level"],
                reference_close=float(row["close"]), stop=ctx["extreme"], target_r=float(self.config["target_r"]),
                max_hold_minutes=int(self.config["max_hold_minutes"]), break_at=ctx["break_at"],
                brt_hour=int(ctx["brt_hour"]),
            ))
            return out

        # IDLE: procura rompimento dentro da janela, a favor da MM longa.
        if any(pd.isna(row[c]) for c in ("sma", "prior_high", "prior_low")) or not bool(row["in_window"]):
            return out
        close = float(row["close"])
        direction = None
        if close > float(row["sma"]) and close > float(row["prior_high"]):
            direction, level, extreme = "long", float(row["prior_high"]), float(row["low"])
        elif close < float(row["sma"]) and close < float(row["prior_low"]):
            direction, level, extreme = "short", float(row["prior_low"]), float(row["high"])
        if direction is None:
            return out
        opportunity_id = f"{self.name}:{self.config['symbol']}:{at.isoformat()}"
        self.context = {
            "direction": direction, "level": level, "extreme": extreme, "last_at": at,
            "break_at": at.isoformat(), "opportunity_id": opportunity_id, "brt_hour": int(row["brt_hour"]),
        }
        out.append(self._move(at, SetupState.BREAK_DETECTED,
                              f"Rompimento das {self.config['break_lookback']} barras anteriores ({level:.2f}) a favor da MM{self.config['trend_sma']}.",
                              direction, opportunity_id=opportunity_id, level=level, close=close, sma=float(row["sma"])))
        out.append(self._move(at, SetupState.WAITING_CONFIRMATION_1, "Aguardando a primeira confirmação.",
                              direction, opportunity_id=opportunity_id))
        return out
