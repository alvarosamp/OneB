"""Testes de regressao contra vazamento temporal.

Cada teste aqui corresponde a um bug real encontrado na auditoria de
2026-09-10. Eles existem para que o bug nao volte silenciosamente.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.temporal_validation import (
    assert_no_label_leakage,
    effective_sample_size,
    purged_three_way_split,
    purged_walk_forward,
)


def _panel(n_dates: int = 400, n_symbols: int = 8, seed: int = 3) -> pd.DataFrame:
    """Painel sintetico com estrutura igual a do research_dataset."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2024-01-01", periods=n_dates)
    symbols = [f"SYM{i}" for i in range(n_symbols)]
    rows = []
    for symbol in symbols:
        price = 100.0
        for date in dates:
            price *= 1 + rng.normal(0, 0.01)
            rows.append({"symbol": symbol, "date": date, "close": price})
    frame = pd.DataFrame(rows)
    frame["fwd_return_5d"] = (
        frame.groupby("symbol")["close"].shift(-5) / frame["close"] - 1
    ) * 100
    return frame


# ---------------------------------------------------------------------------
# purge
# ---------------------------------------------------------------------------


def test_purged_split_creates_required_gap():
    """O gap entre blocos deve ser >= horizonte do label + embargo."""
    panel = _panel()
    result = purged_three_way_split(
        panel["date"], label_horizon=5, embargo=20, train_pct=0.7, validation_pct=0.15
    )
    panel = panel.assign(split=result.split.to_numpy())
    kept = panel[panel["split"] != "purged"]

    # o painel completo ainda carrega as linhas 'purged', entao o calendario
    # esta intacto e o gap pode ser medido direto
    report = assert_no_label_leakage(panel, label_horizon=5, embargo=20)
    assert report["ok"] is True
    assert set(kept["split"]) == {"train", "validation", "test"}
    assert result.dropped_rows > 0, "purge deveria remover alguma coisa"

    # e se o chamador ja filtrou, precisa passar o calendario original
    report_filtered = assert_no_label_leakage(
        kept, label_horizon=5, embargo=20, calendar=panel["date"]
    )
    assert report_filtered["ok"] is True


def test_naive_contiguous_split_is_rejected():
    """Regressao do bug original: split contiguo por data DEVE falhar.

    Este era exatamente o comportamento de ``_assign_splits`` antes da
    correcao -- train terminava num dia e validation comecava no dia util
    seguinte, entao os labels de 5 dias do fim do treino usavam precos de
    dentro da validacao.
    """
    panel = _panel()
    dates = pd.Index(sorted(panel["date"].unique()))
    train_end = dates[int(len(dates) * 0.70) - 1]
    validation_end = dates[int(len(dates) * 0.85) - 1]
    panel["split"] = np.where(
        panel["date"] <= train_end,
        "train",
        np.where(panel["date"] <= validation_end, "validation", "test"),
    )

    with pytest.raises(AssertionError, match="leakage de label"):
        assert_no_label_leakage(panel, label_horizon=5, embargo=0)


@pytest.mark.parametrize("horizon", [1, 5, 10, 20])
def test_purge_scales_with_horizon(horizon: int):
    """Quanto maior o horizonte do label, maior o gap exigido."""
    panel = _panel()
    result = purged_three_way_split(
        panel["date"], label_horizon=horizon, embargo=0, train_pct=0.7, validation_pct=0.15
    )
    full = panel.assign(split=result.split.to_numpy())
    assert_no_label_leakage(full, label_horizon=horizon, embargo=0)


def test_purge_rejects_series_too_short():
    """Serie curta demais deve falhar explicitamente, nao devolver split vazado."""
    short = pd.Series(pd.bdate_range("2024-01-01", periods=20))
    with pytest.raises(ValueError, match="curta demais"):
        purged_three_way_split(short, label_horizon=20, embargo=20)


# ---------------------------------------------------------------------------
# walk-forward
# ---------------------------------------------------------------------------


def test_walk_forward_train_always_precedes_test():
    """Nenhum fold pode ter data de treino >= data de teste."""
    panel = _panel()
    folds = list(
        purged_walk_forward(
            panel["date"], label_horizon=5, n_folds=4, embargo=10, min_train_bars=100
        )
    )
    assert len(folds) >= 2

    for split, info in folds:
        frame = panel.assign(split=split.to_numpy())
        train_dates = frame.loc[frame["split"] == "train", "date"]
        test_dates = frame.loc[frame["split"] == "test", "date"]
        if train_dates.empty or test_dates.empty:
            continue
        assert train_dates.max() < test_dates.min(), (
            f"fold {info['fold']}: treino invade o teste"
        )
        # o gap precisa existir de fato
        gap_days = np.busday_count(
            train_dates.max().date(), test_dates.min().date()
        )
        assert gap_days > 5, f"fold {info['fold']}: gap de apenas {gap_days} barras"


# ---------------------------------------------------------------------------
# amostra efetiva
# ---------------------------------------------------------------------------


def test_effective_sample_is_much_smaller_than_row_count():
    """Contar linhas superestima a informacao disponivel.

    Com labels sobrepostos e simbolos correlacionados, a amostra efetiva tem
    de ser uma fracao pequena do numero de linhas.
    """
    panel = _panel(n_dates=400, n_symbols=8)
    result = effective_sample_size(panel, label_horizon=5)
    assert result["effective_sample_size"] < result["rows"]
    assert result["naive_over_effective_ratio"] > 1.5
    # a sobreposicao sozinha ja divide as datas por ~horizonte
    assert result["temporal_effective_dates"] == pytest.approx(
        result["unique_dates"] / 5, rel=0.01
    )


def test_correlated_symbols_reduce_effective_sample():
    """Simbolos perfeitamente correlacionados nao valem N observacoes."""
    dates = pd.bdate_range("2024-01-01", periods=200)
    shared = np.random.default_rng(1).normal(0, 1, len(dates))
    rows = []
    for symbol in ["A", "B", "C", "D"]:
        for date, value in zip(dates, shared, strict=True):
            rows.append({"symbol": symbol, "date": date, "fwd_return_5d": value})
    identical = pd.DataFrame(rows)

    result = effective_sample_size(identical, label_horizon=5)
    # 4 simbolos identicos devem colapsar para perto de 1
    assert result["cross_sectional_effective_symbols"] < 1.5
    assert result["mean_pairwise_label_corr"] > 0.95
