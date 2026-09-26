"""Testes de causalidade: nada no presente pode depender do futuro.

Dois tipos de look-ahead sao cobertos aqui:

causalidade de feature
    Alterar um preco FUTURO nao pode mudar o valor de uma feature calculada no
    passado. Se mudar, a feature esta olhando para frente.

causalidade de execucao
    Um sinal formado no fechamento da barra ``i`` so pode ser executado a partir
    da abertura da barra ``i+1``. Preencher no proprio ``close[i]`` assume que a
    ordem foi enviada antes de existir a informacao que a gerou.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app import indicators
from scripts.honest_edge_measurement import EdgeConfig, prepare_panel

# funcoes que recebem apenas a serie de fechamento
CLOSE_ONLY_INDICATORS = {
    "sma": lambda s: indicators.sma(s, 20),
    "ema": lambda s: indicators.ema(s, 20),
    "rsi": lambda s: indicators.rsi(s, 14),
    "annualized_volatility": lambda s: indicators.annualized_volatility(s, window=20),
    "pct_change_over_window": lambda s: indicators.pct_change_over_window(s, 5),
}


def _prices(n: int = 200, seed: int = 11) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.01, n)))


@pytest.mark.parametrize("name", sorted(CLOSE_ONLY_INDICATORS))
def test_indicator_does_not_look_ahead(name: str):
    """Perturbar o futuro nao pode alterar o passado.

    Recalcula o indicador com a ultima metade da serie multiplicada por 10. Os
    valores da primeira metade tem de permanecer identicos.
    """
    func = CLOSE_ONLY_INDICATORS[name]
    close = _prices()
    cut = len(close) // 2

    baseline = func(close)
    tampered = close.copy()
    tampered.iloc[cut:] *= 10.0
    perturbed = func(tampered)

    pd.testing.assert_series_equal(
        baseline.iloc[:cut],
        perturbed.iloc[:cut],
        check_names=False,
        obj=f"{name} vazou informacao do futuro para o passado",
    )


def test_macd_does_not_look_ahead():
    close = _prices()
    cut = len(close) // 2
    baseline = indicators.macd(close)
    tampered = close.copy()
    tampered.iloc[cut:] *= 10.0
    perturbed = indicators.macd(tampered)
    pd.testing.assert_frame_equal(
        baseline.iloc[:cut], perturbed.iloc[:cut], obj="macd vazou o futuro"
    )


def test_atr_and_adx_do_not_look_ahead():
    close = _prices()
    high = close * 1.01
    low = close * 0.99
    cut = len(close) // 2

    atr_base = indicators.atr(high, low, close, 14)
    adx_base = indicators.adx(high, low, close, 14)

    h2, l2, c2 = high.copy(), low.copy(), close.copy()
    h2.iloc[cut:] *= 10.0
    l2.iloc[cut:] *= 10.0
    c2.iloc[cut:] *= 10.0

    pd.testing.assert_series_equal(
        atr_base.iloc[:cut],
        indicators.atr(h2, l2, c2, 14).iloc[:cut],
        check_names=False,
        obj="atr vazou o futuro",
    )
    pd.testing.assert_frame_equal(
        adx_base.iloc[:cut],
        indicators.adx(h2, l2, c2, 14).iloc[:cut],
        obj="adx vazou o futuro",
    )


# ---------------------------------------------------------------------------
# execucao
# ---------------------------------------------------------------------------


def _ohlc_panel(n_dates: int = 40) -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-01", periods=n_dates)
    rows = []
    for symbol in ("AAA", "BBB"):
        for i, date in enumerate(dates):
            base = 100 + i
            rows.append(
                {
                    "symbol": symbol,
                    "date": date,
                    "open": base + 0.5,
                    "high": base + 1.0,
                    "low": base - 1.0,
                    "close": base,
                    "volume": 1_000,
                    "fwd_return_5d": 0.0,
                }
            )
    return pd.DataFrame(rows)


def test_entry_price_is_next_open_never_current_close():
    """A entrada tem de ser a abertura seguinte, nunca o fechamento do sinal."""
    panel = _ohlc_panel()
    prepared = prepare_panel(panel, EdgeConfig(label_horizon=5))

    for symbol, group in prepared.groupby("symbol"):
        group = group.sort_values("date").reset_index(drop=True)
        for i in range(len(group) - 6):
            assert group.loc[i, "entry_price"] == group.loc[i + 1, "open"], (
                f"{symbol}: entrada na barra {i} nao usou a abertura de i+1"
            )
            assert group.loc[i, "entry_price"] != group.loc[i, "close"], (
                f"{symbol}: entrada na barra {i} usou o fechamento do proprio sinal"
            )


def test_exit_price_respects_holding_horizon():
    """A saida acontece h barras apos a entrada, tambem na abertura."""
    horizon = 5
    panel = _ohlc_panel()
    prepared = prepare_panel(panel, EdgeConfig(label_horizon=horizon))

    for _, group in prepared.groupby("symbol"):
        group = group.sort_values("date").reset_index(drop=True)
        for i in range(len(group) - horizon - 2):
            assert group.loc[i, "exit_price"] == group.loc[i + horizon + 1, "open"]


def test_last_bars_have_no_tradeable_return():
    """As ultimas barras nao tem saida conhecida e devem ficar NaN, nao 0."""
    panel = _ohlc_panel()
    prepared = prepare_panel(panel, EdgeConfig(label_horizon=5))
    for _, group in prepared.groupby("symbol"):
        tail = group.sort_values("date").tail(6)
        assert tail["tradeable_return_pct"].isna().all(), (
            "barras finais sem saida conhecida deveriam ser NaN"
        )
