"""Validacao temporal correta para dados financeiros com labels sobrepostos.

Este modulo existe porque splits ingenuos por data vazam informacao quando o
label olha para frente. Se a amostra do dia ``t`` tem label que depende dos
precos ate ``t + h``, entao ela NAO pode ficar no treino quando o teste comeca
em qualquer dia <= ``t + h``: os precos que definem o label de treino sao os
mesmos que o modelo deveria estar prevendo no teste.

Referencia conceitual: Lopez de Prado, "Advances in Financial Machine
Learning" (2018), cap. 7 - purging e embargo.

Dois mecanismos distintos, frequentemente confundidos:

purge
    Remove do treino as amostras cuja JANELA DE LABEL invade o bloco de teste.
    Depende do horizonte do label (``label_horizon``).

embargo
    Remove do treino as amostras imediatamente POSTERIORES ao bloco de teste.
    Nao tem a ver com o label, e sim com a autocorrelacao serial das features
    (uma media movel de 20 dias calculada logo apos o teste ainda carrega
    precos de dentro do teste).

Ambos sao medidos em BARRAS DE PREGAO (posicoes no indice de datas unicas), nao
em dias corridos: 5 dias corridos podem ser 3 pregoes.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

__all__ = [
    "SplitBoundaries",
    "PurgedSplit",
    "purged_three_way_split",
    "purged_walk_forward",
    "effective_sample_size",
    "assert_no_label_leakage",
]


# ---------------------------------------------------------------------------
# estruturas
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SplitBoundaries:
    """Fronteiras de um split de tres blocos, em datas reais."""

    train_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    purged_bars: int
    embargo_bars: int

    def as_dict(self) -> dict[str, object]:
        return {
            "train_end": str(self.train_end.date()),
            "validation_start": str(self.validation_start.date()),
            "validation_end": str(self.validation_end.date()),
            "test_start": str(self.test_start.date()),
            "test_end": str(self.test_end.date()),
            "purged_bars": self.purged_bars,
            "embargo_bars": self.embargo_bars,
        }


@dataclass
class PurgedSplit:
    """Resultado de um split purgado.

    ``split`` usa os rotulos ``train``/``validation``/``test``/``purged``.
    Linhas marcadas como ``purged`` foram removidas de proposito e NAO devem
    ser usadas em nenhum dos tres conjuntos.
    """

    split: pd.Series
    boundaries: SplitBoundaries
    dropped_rows: int
    dropped_pct: float
    report: dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# nucleo
# ---------------------------------------------------------------------------


def _unique_sorted_dates(dates: Sequence | pd.Series) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(pd.to_datetime(pd.Series(list(dates)).dropna().unique()))
    return idx.sort_values()


def purged_three_way_split(
    dates: pd.Series,
    *,
    label_horizon: int,
    train_pct: float = 0.70,
    validation_pct: float = 0.15,
    embargo: int = 0,
) -> PurgedSplit:
    """Divide um painel em train/validation/test com purge nas duas fronteiras.

    Parameters
    ----------
    dates:
        Coluna de datas do painel (uma linha por simbolo/data; pode repetir).
    label_horizon:
        Maior horizonte de label em BARRAS. Todas as amostras de treino cuja
        janela de label alcance o bloco seguinte sao purgadas.
    train_pct, validation_pct:
        Fracao das datas unicas destinada a cada bloco antes do purge. O teste
        recebe o restante.
    embargo:
        Barras adicionais removidas apos cada fronteira, para cobrir
        autocorrelacao das features. Use >= a maior janela de lookback.

    Returns
    -------
    PurgedSplit
        ``split`` alinhado ao indice de ``dates``.
    """

    if label_horizon < 0:
        raise ValueError("label_horizon deve ser >= 0")
    if embargo < 0:
        raise ValueError("embargo deve ser >= 0")
    if not 0 < train_pct < 1 or not 0 < validation_pct < 1:
        raise ValueError("train_pct e validation_pct devem estar em (0, 1)")
    if train_pct + validation_pct >= 1:
        raise ValueError("train_pct + validation_pct deve ser < 1")

    series = pd.to_datetime(pd.Series(dates).reset_index(drop=True))
    unique_dates = _unique_sorted_dates(series)
    n = len(unique_dates)

    # gap total que precisa existir entre o fim de um bloco e o inicio do
    # proximo: o label precisa ter terminado (horizon) e a autocorrelacao das
    # features precisa ter decaido (embargo).
    gap = int(label_horizon) + int(embargo)

    # precisamos de pelo menos 1 barra util por bloco depois de dois gaps
    if n < 2 * gap + 3:
        raise ValueError(
            f"serie curta demais: {n} datas nao suportam 2 gaps de {gap} barras "
            "mais tres blocos nao vazios"
        )

    train_last = int(np.floor(n * train_pct)) - 1
    validation_last = int(np.floor(n * (train_pct + validation_pct))) - 1
    train_last = max(0, min(train_last, n - 1))
    validation_last = max(train_last + 1, min(validation_last, n - 1))

    # aplica o gap consumindo o FIM de cada bloco, preservando o inicio do
    # bloco seguinte. Assim os conjuntos de avaliacao mantem seu tamanho.
    train_end_idx = train_last - gap
    validation_start_idx = train_last + 1
    validation_end_idx = validation_last - gap
    test_start_idx = validation_last + 1
    test_end_idx = n - 1

    if train_end_idx < 0 or validation_end_idx <= validation_start_idx:
        raise ValueError(
            "purge consumiu blocos inteiros; reduza label_horizon/embargo ou "
            "use uma serie mais longa"
        )

    date_to_pos = pd.Series(np.arange(n), index=unique_dates)
    pos = series.map(date_to_pos).astype("int64")

    split = pd.Series("purged", index=series.index, dtype="object")
    split[(pos >= 0) & (pos <= train_end_idx)] = "train"
    split[(pos >= validation_start_idx) & (pos <= validation_end_idx)] = "validation"
    split[(pos >= test_start_idx) & (pos <= test_end_idx)] = "test"

    dropped = int((split == "purged").sum())
    boundaries = SplitBoundaries(
        train_end=unique_dates[train_end_idx],
        validation_start=unique_dates[validation_start_idx],
        validation_end=unique_dates[validation_end_idx],
        test_start=unique_dates[test_start_idx],
        test_end=unique_dates[test_end_idx],
        purged_bars=int(label_horizon),
        embargo_bars=int(embargo),
    )

    report = {
        "total_dates": n,
        "gap_bars_each_boundary": gap,
        "rows_per_split": split.value_counts().to_dict(),
        "boundaries": boundaries.as_dict(),
    }

    return PurgedSplit(
        split=split,
        boundaries=boundaries,
        dropped_rows=dropped,
        dropped_pct=round(100.0 * dropped / max(1, len(split)), 3),
        report=report,
    )


def purged_walk_forward(
    dates: pd.Series,
    *,
    label_horizon: int,
    n_folds: int = 5,
    embargo: int = 0,
    min_train_bars: int = 60,
    expanding: bool = True,
) -> Iterator[tuple[pd.Series, dict[str, object]]]:
    """Gera folds walk-forward com purge e embargo.

    Cada iteracao devolve ``(split, info)`` onde ``split`` marca
    ``train``/``test``/``purged`` para as linhas do painel.

    O teste caminha para frente no tempo; o treino e sempre estritamente
    anterior. Amostras cuja janela de label invade o teste sao purgadas, e as
    ``embargo`` barras seguintes ao teste nunca entram em treinos futuros do
    mesmo fold.
    """

    series = pd.to_datetime(pd.Series(dates).reset_index(drop=True))
    unique_dates = _unique_sorted_dates(series)
    n = len(unique_dates)
    gap = int(label_horizon) + int(embargo)

    usable = n - min_train_bars - gap
    if usable <= 0:
        raise ValueError("serie curta demais para walk-forward com esse purge")

    fold_size = usable // n_folds
    if fold_size < 1:
        raise ValueError(f"n_folds={n_folds} grande demais para {n} datas")

    date_to_pos = pd.Series(np.arange(n), index=unique_dates)
    pos = series.map(date_to_pos).astype("int64")

    for fold in range(n_folds):
        test_start_idx = min_train_bars + gap + fold * fold_size
        test_end_idx = test_start_idx + fold_size - 1
        if fold == n_folds - 1:
            test_end_idx = n - 1
        if test_start_idx > n - 1:
            break

        train_end_idx = test_start_idx - gap - 1
        train_start_idx = 0 if expanding else max(0, train_end_idx - min_train_bars + 1)
        if train_end_idx < train_start_idx:
            continue

        split = pd.Series("purged", index=series.index, dtype="object")
        split[(pos >= train_start_idx) & (pos <= train_end_idx)] = "train"
        split[(pos >= test_start_idx) & (pos <= test_end_idx)] = "test"

        info = {
            "fold": fold,
            "train_start": str(unique_dates[train_start_idx].date()),
            "train_end": str(unique_dates[train_end_idx].date()),
            "test_start": str(unique_dates[test_start_idx].date()),
            "test_end": str(unique_dates[test_end_idx].date()),
            "gap_bars": gap,
            "train_rows": int((split == "train").sum()),
            "test_rows": int((split == "test").sum()),
        }
        yield split, info


# ---------------------------------------------------------------------------
# diagnostico de amostra
# ---------------------------------------------------------------------------


def effective_sample_size(
    panel: pd.DataFrame,
    *,
    date_col: str = "date",
    symbol_col: str = "symbol",
    label_col: str = "fwd_return_5d",
    label_horizon: int = 5,
) -> dict[str, object]:
    """Estima o tamanho de amostra REAL de um painel com labels sobrepostos.

    Contar linhas superestima brutalmente a informacao disponivel por dois
    motivos combinados:

    1. labels de ``h`` barras em dias consecutivos compartilham ``h-1`` barras
       de janela, entao dias vizinhos nao sao independentes;
    2. num painel de acoes do mesmo setor, os simbolos se movem juntos, entao
       N simbolos nao valem N observacoes independentes.

    O ajuste cross-seccional usa a correlacao media par a par dos labels entre
    simbolos na mesma data, via a formula do tamanho efetivo de um bloco
    correlacionado: ``n_eff = n / (1 + (n - 1) * rho_medio)``.
    """

    frame = panel[[date_col, symbol_col, label_col]].dropna()
    n_rows = len(frame)
    n_dates = frame[date_col].nunique()
    n_symbols = frame[symbol_col].nunique()

    wide = frame.pivot_table(index=date_col, columns=symbol_col, values=label_col)
    corr = wide.corr()
    mask = ~np.eye(len(corr), dtype=bool)
    mean_pairwise_corr = float(np.nanmean(corr.to_numpy()[mask])) if len(corr) > 1 else 0.0

    k = max(1, n_symbols)
    denom = 1.0 + (k - 1) * max(0.0, mean_pairwise_corr)
    cross_sectional_eff = k / denom

    # sobreposicao temporal: dias consecutivos compartilham h-1 barras
    temporal_eff_dates = n_dates / max(1, label_horizon)

    n_eff = temporal_eff_dates * cross_sectional_eff

    return {
        "rows": n_rows,
        "unique_dates": int(n_dates),
        "symbols": int(n_symbols),
        "mean_pairwise_label_corr": round(mean_pairwise_corr, 4),
        "cross_sectional_effective_symbols": round(cross_sectional_eff, 2),
        "temporal_effective_dates": round(temporal_eff_dates, 1),
        "effective_sample_size": round(n_eff, 1),
        "naive_over_effective_ratio": round(n_rows / max(1e-9, n_eff), 1),
    }


def assert_no_label_leakage(
    panel: pd.DataFrame,
    *,
    date_col: str = "date",
    split_col: str = "split",
    label_horizon: int,
    embargo: int = 0,
    calendar: pd.DatetimeIndex | Sequence | None = None,
) -> dict[str, object]:
    """Verifica que nenhum bloco invade o seguinte, em barras de pregao.

    Levanta ``AssertionError`` quando o gap entre blocos e menor que
    ``label_horizon + embargo``. Devolve o relatorio quando esta correto.

    Parameters
    ----------
    calendar:
        Calendario de referencia para medir distancias. **Obrigatorio quando
        ``panel`` ja teve as linhas purgadas removidas**: sem as datas
        purgadas presentes, os blocos voltam a parecer contiguos e o gap
        medido seria 0 mesmo num split correto. Quando ``panel`` ainda contem
        as linhas marcadas como ``purged`` (saida natural de
        ``purged_three_way_split``), pode ser omitido.
    """

    frame = panel[[date_col, split_col]].copy()
    frame[date_col] = pd.to_datetime(frame[date_col])
    if calendar is not None:
        unique_dates = _unique_sorted_dates(calendar)
    else:
        unique_dates = _unique_sorted_dates(frame[date_col])
    date_to_pos = pd.Series(np.arange(len(unique_dates)), index=unique_dates)

    required = int(label_horizon) + int(embargo)
    order = ["train", "validation", "test"]
    present = [s for s in order if s in set(frame[split_col])]

    bounds: dict[str, tuple[int, int]] = {}
    for name in present:
        sub = frame.loc[frame[split_col] == name, date_col]
        positions = sub.map(date_to_pos)
        bounds[name] = (int(positions.min()), int(positions.max()))

    violations = []
    for left, right in zip(present, present[1:], strict=False):
        gap_bars = bounds[right][0] - bounds[left][1] - 1
        if gap_bars < required:
            violations.append(
                {
                    "boundary": f"{left}->{right}",
                    "gap_bars": gap_bars,
                    "required_minimum": required,
                }
            )

    if violations:
        raise AssertionError(
            "leakage de label nas fronteiras de split: "
            + "; ".join(
                f"{v['boundary']} tem gap de {v['gap_bars']} barras, "
                f"exige {v['required_minimum']}"
                for v in violations
            )
        )

    return {
        "ok": True,
        "required_gap_bars": required,
        "splits_present": present,
        "bounds": {k: {"start_pos": v[0], "end_pos": v[1]} for k, v in bounds.items()},
    }
