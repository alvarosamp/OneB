"""Reconstructs the NASDAQ local-regime score (same formula as
app.regime_engine.local_regime) as a full time series across the price
window used in every experiment this session, instead of just the latest
snapshot regime_engine normally returns — this is what lets us SEE where
the regime shift that broke every feature/label in the prior experiments
actually happened.

Also pulls VIX (FRED) over the same window, since a regime break driven by
a volatility-regime change should show up there independently of anything
computed from price alone — a second, differently-sourced signal agreeing
on the same break date is much stronger evidence than one series alone.

Run: python -m scripts.regime_timeline
"""
from __future__ import annotations

import pandas as pd

from app import indicators
from app.market_data import fred_client
from app.market_data import service as market_data_service
from app.paper_simulator import MARKET_HISTORY_PERIOD

pd.set_option("display.width", 140)


def _regime_score_series(history: pd.DataFrame) -> pd.DataFrame:
    """Vectorized version of app.regime_engine.local_regime's score formula
    — computed at every bar instead of only the last one. Swing-structure
    term omitted (it's a small, discrete +/-15 bonus in the original; not
    worth the vectorization complexity for a descriptive timeline).
    """
    close, high, low = history["close"], history["high"], history["low"]
    ema20 = indicators.ema(close, 20)
    ema50 = indicators.ema(close, 50)
    rsi = indicators.rsi(close, 14)
    adx_df = indicators.adx(high, low, close, 14)

    trend_score = (ema20 > ema50).astype(float) * 30 - (ema20 <= ema50).astype(float) * 30
    momentum_score = (rsi - 50).clip(-35.7, 35.7) * 0.7
    score = trend_score + momentum_score

    strong_trend = adx_df["adx"] >= 25
    multiplier = strong_trend.map({True: 1.25, False: 0.7})
    score = score * multiplier
    score = score.clip(-100, 100)

    return pd.DataFrame({"regime_score": score, "adx": adx_df["adx"], "rsi": rsi})


def main() -> None:
    nasdaq = market_data_service.get_bars("NQ=F", period=MARKET_HISTORY_PERIOD, interval="1d")
    if nasdaq.empty:
        # NQ=F daily history via yfinance can be thin; fall back to the cash index.
        nasdaq = market_data_service.get_bars("^NDX", period=MARKET_HISTORY_PERIOD, interval="1d")
    regime = _regime_score_series(nasdaq)

    vix = fred_client.get_series("VIXCLS")["close"]
    vix.index = pd.to_datetime(vix.index)
    if vix.index.tz is not None:
        vix.index = vix.index.tz_localize(None)

    idx = pd.to_datetime(regime.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    regime.index = idx
    regime["vix"] = vix.reindex(idx, method="ffill")
    regime["nasdaq_close"] = nasdaq["close"].to_numpy()

    monthly = regime.resample("MS").agg(
        regime_score_medio=("regime_score", "mean"),
        vix_medio=("vix", "mean"),
        adx_medio=("adx", "mean"),
    )
    monthly["retorno_mes_pct"] = regime["nasdaq_close"].resample("MS").apply(lambda s: (s.iloc[-1] / s.iloc[0] - 1) * 100 if len(s) > 1 else None)

    def _label(score: float) -> str:
        if score >= 15:
            return "BULL"
        if score <= -15:
            return "BEAR"
        return "NEUTRO/MISTO"

    monthly["regime"] = monthly["regime_score_medio"].apply(_label)

    print("=" * 100)
    print("LINHA DO TEMPO DE REGIME — NASDAQ, mensal (score medio, VIX medio, ADX medio, retorno do mes)")
    print("=" * 100)
    print(monthly.round(2).to_string())

    # Marca o ponto medio usado nos experimentos anteriores (row_index ~223 de ~447)
    n = len(regime)
    midpoint_date = regime.index[n // 2]
    print(f"\nPonto medio da janela usada nos experimentos anteriores (metade dos dias): {midpoint_date.date()}")

    print("\n" + "=" * 100)
    print("LEITURA")
    print("=" * 100)
    first_half = monthly[monthly.index < midpoint_date]
    second_half = monthly[monthly.index >= midpoint_date]
    print(f"Regime medio ANTES de {midpoint_date.date()}: score={first_half['regime_score_medio'].mean():.1f}, vix={first_half['vix_medio'].mean():.1f}")
    print(f"Regime medio DEPOIS de {midpoint_date.date()}: score={second_half['regime_score_medio'].mean():.1f}, vix={second_half['vix_medio'].mean():.1f}")


if __name__ == "__main__":
    main()
