"""Laboratório de backtest: motor sem look-ahead, custos e métricas.

Convenção de execução (conservadora): o sinal é calculado com o fechamento da barra t, a ordem
é executada na ABERTURA de t+1 e o retorno é medido de abertura a abertura. Custo cobrado a
cada mudança de posição (por lado). Tudo é long-only (0 ou 1).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252
DEFAULT_COST = 0.0010  # 10 bps por lado (comissão + slippage), conservador para large caps


def open_to_open(ohlcv: pd.DataFrame) -> pd.Series:
    """Retorno de abrir em t e abrir em t+1 (indexado em t)."""
    o = ohlcv["open"]
    return o.shift(-1) / o - 1


def strategy_returns(pos: pd.Series, ohlcv: pd.DataFrame, cost: float = DEFAULT_COST) -> pd.Series:
    """`pos[t]` = posição desejada após o fechamento de t. Entra em t+1 (abertura)."""
    held = pos.shift(1).fillna(0.0)  # posição vigente durante a barra t (decidida em t-1)
    gross = held * open_to_open(ohlcv)
    turnover = held.diff().abs().fillna(held.abs())
    return (gross - turnover * cost).dropna()


def simulate_position(
    entry: np.ndarray,
    exit_: np.ndarray | None,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    trail_mult: float | None = None,
    max_hold: int | None = None,
    stop_pct: float | None = None,
) -> np.ndarray:
    """Máquina de estados de posição a partir de sinais de entrada/saída (decididos no fechamento).

    Saídas possíveis: sinal de saída, tempo máximo, stop fixo (% sobre a entrada) e stop
    móvel de `trail_mult` × ATR abaixo da máxima de fechamento desde a entrada.
    """
    n = len(close)
    pos = np.zeros(n)
    in_pos = False
    bars = 0
    entry_px = peak = 0.0
    for i in range(n):
        if in_pos:
            bars += 1
            peak = max(peak, close[i])
            out = bool(exit_[i]) if exit_ is not None else False
            if max_hold is not None and bars >= max_hold:
                out = True
            if stop_pct is not None and close[i] <= entry_px * (1 - stop_pct):
                out = True
            if trail_mult is not None and atr is not None and not np.isnan(atr[i]) and close[i] <= peak - trail_mult * atr[i]:
                out = True
            if out:
                in_pos = False
            else:
                pos[i] = 1.0
        elif entry[i]:
            in_pos = True
            bars = 0
            entry_px = peak = close[i]
            pos[i] = 1.0
    return pos


def trade_returns(pos: pd.Series, strat_ret: pd.Series) -> list[float]:
    """Retorno composto de cada operação (sequência contínua de posição=1), já líquido de custos."""
    held = pos.shift(1).fillna(0.0).reindex(strat_ret.index).fillna(0.0).to_numpy() > 0
    r = strat_ret.to_numpy()
    out, acc, active = [], 1.0, False
    for h, x in zip(held, r):
        if h:
            acc *= 1 + x
            active = True
        elif active:
            out.append(acc - 1)
            acc, active = 1.0, False
    if active:
        out.append(acc - 1)
    return out


def metrics(ret: pd.Series, trades: list[float] | None = None, exposure: float | None = None) -> dict:
    ret = ret.dropna()
    if len(ret) < 20:
        return {}
    equity = (1 + ret).cumprod()
    years = len(ret) / TRADING_DAYS
    cagr = equity.iloc[-1] ** (1 / years) - 1
    vol = ret.std() * np.sqrt(TRADING_DAYS)
    sharpe = ret.mean() / ret.std() * np.sqrt(TRADING_DAYS) if ret.std() > 0 else 0.0
    dd = (equity / equity.cummax() - 1).min()
    out = {
        "cagr_pct": round(cagr * 100, 2),
        "vol_pct": round(vol * 100, 2),
        "sharpe": round(float(sharpe), 2),
        "max_dd_pct": round(dd * 100, 2),
        "total_pct": round((equity.iloc[-1] - 1) * 100, 1),
    }
    if exposure is not None:
        out["exposure_pct"] = round(exposure * 100, 1)
    if trades is not None:
        t = np.array(trades)
        out["trades"] = int(len(t))
        if len(t):
            wins, losses = t[t > 0], t[t <= 0]
            out["win_rate_pct"] = round(float((t > 0).mean() * 100), 1)
            out["avg_trade_pct"] = round(float(t.mean() * 100), 2)
            out["profit_factor"] = round(float(wins.sum() / -losses.sum()), 2) if losses.sum() < 0 else None
    return out


def equal_weight(returns: pd.DataFrame) -> pd.Series:
    """Carteira igual-peso (cada ativo 1/N do capital; caixa rende 0)."""
    return returns.mean(axis=1, skipna=True)


def slice_period(obj, start: str | None, end: str | None):
    return obj.loc[start:end] if (start or end) else obj
