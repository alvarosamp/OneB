"""Medicao honesta de edge preditivo.

Este script responde a UNICA pergunta que importa antes de qualquer discussao
sobre deploy, monitoramento ou kill switch: **existe sinal preditivo real neste
dataset?**

Ele foi escrito para ser dificil de enganar a si mesmo. Cada etapa desliga um
mecanismo classico de auto-ilusao:

1. ``amostra efetiva``      - conta informacao, nao linhas. Labels de 5 dias em
                              dias consecutivos compartilham 4/5 da janela, e 24
                              acoes de tecnologia nao sao 24 observacoes
                              independentes.
2. ``IC corrigido``         - t-stat com Newey-West e bootstrap em blocos, em vez
                              de assumir dias independentes.
3. ``multiplos testes``     - Benjamini-Hochberg sobre TODAS as features
                              testadas, porque testar 33 hipoteses e achar 2
                              "significativas" e o resultado esperado do acaso.
4. ``execucao next-bar``    - sinal formado no fechamento de ``i`` so pode ser
                              executado na abertura de ``i+1``. Preencher no
                              proprio fechamento e look-ahead operacional.
5. ``controle aleatorio``   - a estrategia bate uma selecao ALEATORIA de mesmo
                              tamanho? Em mercado de alta, quase tudo ganha
                              dinheiro; a pergunta e se ganha mais que a sorte.
6. ``beta vs alfa``         - selecionar por volatilidade e comprar beta
                              alavancado, nao ter habilidade preditiva. O alfa e
                              o que sobra apos descontar a exposicao ao mercado.
7. ``walk-forward honesto`` - a feature e escolhida SO com dados de treino e
                              medida no bloco seguinte, nunca escolhida e
                              avaliada no mesmo periodo.

Uso::

    python -m scripts.honest_edge_measurement \\
        --dataset data/research/research_dataset_v1.csv \\
        --out data/honest_edge_measurement.json

Codigo de saida 1 quando nenhum sinal sobrevive a todas as correcoes, para que
o script possa ser usado como gate em CI.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

try:  # pragma: no cover - conveniencia de import
    from app.temporal_validation import effective_sample_size
except ImportError:  # execucao direta fora do pacote
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.temporal_validation import effective_sample_size


# ---------------------------------------------------------------------------
# configuracao
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EdgeConfig:
    label_horizon: int = 5
    top_quantile: float = 0.20
    cost_bps: float = 2.0
    slippage_bps: float = 5.0
    min_symbols_per_day: int = 10
    bootstrap_iterations: int = 4000
    random_control_repeats: int = 200
    fdr_alpha: float = 0.05
    n_stability_blocks: int = 4
    n_walk_forward_folds: int = 5
    seed: int = 7

    @property
    def round_trip_cost_pct(self) -> float:
        """Custo de ida e volta em pontos percentuais."""
        return (self.cost_bps + self.slippage_bps) * 2 / 100.0


EXCLUDED_COLUMNS = {
    "symbol",
    "date",
    "split",
    "provider",
    "data_quality_status",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "label_5d",
}


# ---------------------------------------------------------------------------
# estatistica
# ---------------------------------------------------------------------------


def newey_west_t(values: np.ndarray, lag: int) -> float:
    """t-stat com correcao de Newey-West para autocorrelacao ate ``lag``."""
    x = np.asarray(values, dtype=float)
    n = len(x)
    if n < 3:
        return float("nan")
    mean = x.mean()
    err = x - mean
    variance = (err @ err) / n
    for l in range(1, max(1, lag) + 1):
        if l >= n:
            break
        weight = 1.0 - l / (lag + 1)
        variance += 2.0 * weight * (err[l:] @ err[:-l]) / n
    se = np.sqrt(max(variance, 1e-18) / n)
    return float(mean / se)


def block_bootstrap_ci(
    values: np.ndarray, block: int, iterations: int, seed: int
) -> tuple[float, float]:
    """IC 95% da media via bootstrap em blocos circulares.

    Blocos de tamanho ``block`` preservam a autocorrelacao que a sobreposicao
    dos labels cria; um bootstrap i.i.d. a destruiria e devolveria um intervalo
    otimista demais.
    """
    rng = np.random.default_rng(seed)
    x = np.asarray(values, dtype=float)
    n = len(x)
    if n < block * 2:
        return (float("nan"), float("nan"))
    n_blocks = int(np.ceil(n / block))
    means = np.empty(iterations)
    for i in range(iterations):
        starts = rng.integers(0, n, n_blocks)
        idx = np.concatenate([np.arange(s, s + block) % n for s in starts])[:n]
        means[i] = x[idx].mean()
    lo, hi = np.percentile(means, [2.5, 97.5])
    return (float(lo), float(hi))


def benjamini_hochberg(p_values: pd.Series, alpha: float) -> pd.Series:
    """Retorna mascara booleana das hipoteses que sobrevivem ao FDR."""
    order = p_values.sort_values()
    m = len(order)
    critical = (np.arange(1, m + 1) / m) * alpha
    passing = order.to_numpy() <= critical
    result = pd.Series(False, index=p_values.index)
    if passing.any():
        cutoff = np.where(passing)[0].max()
        result.loc[order.index[: cutoff + 1]] = True
    return result


# ---------------------------------------------------------------------------
# preparacao
# ---------------------------------------------------------------------------


def prepare_panel(frame: pd.DataFrame, config: EdgeConfig) -> pd.DataFrame:
    """Adiciona precos de execucao next-bar e o retorno realmente alcancavel."""
    out = frame.sort_values(["symbol", "date"]).reset_index(drop=True).copy()
    h = config.label_horizon
    grouped = out.groupby("symbol", sort=False)
    # sinal formado no fechamento de i -> ordem executada na ABERTURA de i+1
    out["entry_price"] = grouped["open"].shift(-1)
    # saida h barras depois da entrada, tambem na abertura
    out["exit_price"] = grouped["open"].shift(-(h + 1))
    out["tradeable_return_pct"] = (out["exit_price"] / out["entry_price"] - 1) * 100
    return out


def feature_columns(frame: pd.DataFrame) -> list[str]:
    return [
        c
        for c in frame.columns
        if c not in EXCLUDED_COLUMNS
        and not c.startswith("fwd_")
        and c not in {"entry_price", "exit_price", "tradeable_return_pct"}
        and pd.api.types.is_numeric_dtype(frame[c])
    ]


def _daily_groups(frame: pd.DataFrame, config: EdgeConfig):
    groups = []
    for day, group in frame.groupby("date", sort=True):
        clean = group.dropna(subset=["tradeable_return_pct"])
        if len(clean) >= config.min_symbols_per_day:
            groups.append((day, clean))
    return groups


# ---------------------------------------------------------------------------
# etapas de analise
# ---------------------------------------------------------------------------


def analyse_information_coefficient(
    frame: pd.DataFrame, features: list[str], config: EdgeConfig
) -> pd.DataFrame:
    """IC cross-seccional diario por feature, com significancia corrigida."""
    label = f"fwd_return_{config.label_horizon}d"
    records = []
    for feature in features:
        ics = []
        for _, group in frame.groupby("date", sort=True):
            sub = group[[feature, label]].dropna()
            if len(sub) < 5 or sub[feature].nunique() < 2:
                continue
            ic = stats.spearmanr(sub[feature], sub[label]).statistic
            if np.isfinite(ic):
                ics.append(ic)
        if len(ics) < 30:
            continue
        arr = np.asarray(ics)
        naive_t = float(arr.mean() / (arr.std(ddof=1) / np.sqrt(len(arr))))
        nw_t = newey_west_t(arr, config.label_horizon - 1)
        lo, hi = block_bootstrap_ci(
            arr, config.label_horizon, config.bootstrap_iterations, config.seed
        )
        records.append(
            {
                "feature": feature,
                "ic_mean": float(arr.mean()),
                "ic_std": float(arr.std(ddof=1)),
                "n_days": len(arr),
                "t_naive": naive_t,
                "t_newey_west": nw_t,
                "p_newey_west": float(2 * (1 - stats.norm.cdf(abs(nw_t)))),
                "bootstrap_ci_low": lo,
                "bootstrap_ci_high": hi,
                "bootstrap_significant": bool(lo > 0 or hi < 0),
            }
        )

    result = pd.DataFrame(records)
    if result.empty:
        return result
    result["survives_fdr"] = benjamini_hochberg(
        result.set_index("feature")["p_newey_west"], config.fdr_alpha
    ).reindex(result["feature"]).to_numpy()
    return result.sort_values("p_newey_west").reset_index(drop=True)


def _portfolio_daily_returns(
    groups, feature: str | None, config: EdgeConfig, rng: np.random.Generator | None = None
) -> pd.Series:
    """Serie diaria do retorno medio da carteira selecionada.

    ``feature=None`` com ``rng`` devolve selecao aleatoria (controle);
    ``feature=None`` sem ``rng`` devolve o universo inteiro (proxy de mercado).
    """
    out: dict = {}
    for day, group in groups:
        if feature is None and rng is None:
            selected = group
        elif feature is None:
            k = max(1, int(len(group) * config.top_quantile))
            selected = group.iloc[rng.choice(len(group), k, replace=False)]
        else:
            clean = group.dropna(subset=[feature])
            if len(clean) < config.min_symbols_per_day:
                continue
            k = max(1, int(len(clean) * config.top_quantile))
            selected = clean.nlargest(k, feature)
        if len(selected) == 0:
            continue
        out[day] = float(
            (selected["tradeable_return_pct"] - config.round_trip_cost_pct).mean()
        )
    return pd.Series(out).sort_index()


def _alpha_beta(strategy: pd.Series, market: pd.Series) -> dict | None:
    """Regressao strategy = alpha + beta*market. Alfa e o que sobra do beta."""
    joined = pd.concat([strategy.rename("s"), market.rename("m")], axis=1).dropna()
    if len(joined) < 30:
        return None
    beta, alpha = np.polyfit(joined["m"], joined["s"], 1)
    residual = joined["s"] - (alpha + beta * joined["m"])
    se = residual.std(ddof=2) / np.sqrt(len(joined))
    return {
        "n_days": len(joined),
        "beta": float(beta),
        "alpha_pct": float(alpha),
        "t_alpha_naive": float(alpha / se) if se > 0 else float("nan"),
        "sharpe_per_period": float(joined["s"].mean() / joined["s"].std())
        if joined["s"].std() > 0
        else 0.0,
    }


def analyse_strategy_vs_random(
    frame: pd.DataFrame, features: list[str], config: EdgeConfig
) -> dict:
    """Compara cada sinal contra selecao aleatoria e contra o mercado."""
    groups = _daily_groups(frame, config)
    rng = np.random.default_rng(config.seed)

    market = _portfolio_daily_returns(groups, None, config)
    random_means = []
    for _ in range(config.random_control_repeats):
        series = _portfolio_daily_returns(groups, None, config, rng=rng)
        random_means.append(series.mean())
    random_means = np.asarray(random_means)

    signals = []
    for feature in features:
        series = _portfolio_daily_returns(groups, feature, config)
        if len(series) < 30:
            continue
        model = _alpha_beta(series, market)
        if model is None:
            continue
        signals.append(
            {
                "feature": feature,
                "mean_return_pct": float(series.mean()),
                "volatility_pct": float(series.std()),
                "percentile_vs_random": float((random_means < series.mean()).mean()),
                **model,
                # ajuste grosseiro pela sobreposicao: janelas de h barras em dias
                # consecutivos reduzem o n efetivo por ~sqrt(h/2)
                "t_alpha_overlap_adjusted": float(
                    model["t_alpha_naive"] / np.sqrt(max(1.0, config.label_horizon / 2.0))
                ),
            }
        )

    return {
        "market_mean_return_pct": float(market.mean()),
        "market_sharpe": float(market.mean() / market.std()) if market.std() > 0 else 0.0,
        "random_control": {
            "repeats": config.random_control_repeats,
            "mean_return_pct": float(random_means.mean()),
            "p2_5": float(np.percentile(random_means, 2.5)),
            "p97_5": float(np.percentile(random_means, 97.5)),
        },
        "signals": sorted(signals, key=lambda r: r["alpha_pct"], reverse=True),
    }


def analyse_alpha_stability(
    frame: pd.DataFrame, features: list[str], config: EdgeConfig
) -> dict:
    """O alfa e persistente ou concentrado num unico periodo de sorte?"""
    groups = _daily_groups(frame, config)
    market = _portfolio_daily_returns(groups, None, config)
    out = {}
    for feature in features:
        series = _portfolio_daily_returns(groups, feature, config)
        if len(series) < 60:
            continue
        blocks = np.array_split(series.index, config.n_stability_blocks)
        block_results = []
        for i, block in enumerate(blocks):
            model = _alpha_beta(series.loc[block], market.loc[market.index.isin(block)])
            if model:
                block_results.append(
                    {
                        "block": i + 1,
                        "start": str(pd.Timestamp(block[0]).date()),
                        "end": str(pd.Timestamp(block[-1]).date()),
                        **model,
                    }
                )
        if block_results:
            positive = sum(1 for b in block_results if b["alpha_pct"] > 0)
            out[feature] = {
                "blocks": block_results,
                "positive_blocks": positive,
                "total_blocks": len(block_results),
            }
    return out


def analyse_walk_forward(
    frame: pd.DataFrame, features: list[str], config: EdgeConfig
) -> dict:
    """Escolhe a feature SO no treino e mede no bloco seguinte.

    Esta e a unica medida honesta de "qual e o edge esperado", porque replica a
    decisao que se tomaria na vida real: nao se sabe qual feature sera a melhor
    no futuro, escolhe-se com o passado.
    """
    groups = _daily_groups(frame, config)
    market = _portfolio_daily_returns(groups, None, config)
    series_by_feature = {f: _portfolio_daily_returns(groups, f, config) for f in features}
    series_by_feature = {f: s for f, s in series_by_feature.items() if len(s) >= 60}
    if not series_by_feature:
        return {"folds": [], "mean_oos_alpha_pct": None}

    index = market.index
    folds = np.array_split(index, config.n_walk_forward_folds)
    results = []
    for k in range(1, len(folds)):
        train_idx = pd.Index(np.concatenate(folds[:k]))
        test_idx = pd.Index(folds[k])
        best_feature, best_alpha = None, -np.inf
        for feature, series in series_by_feature.items():
            model = _alpha_beta(
                series.loc[series.index.isin(train_idx)],
                market.loc[market.index.isin(train_idx)],
            )
            if model and model["alpha_pct"] > best_alpha:
                best_feature, best_alpha = feature, model["alpha_pct"]
        if best_feature is None:
            continue
        test_model = _alpha_beta(
            series_by_feature[best_feature].loc[
                series_by_feature[best_feature].index.isin(test_idx)
            ],
            market.loc[market.index.isin(test_idx)],
        )
        if test_model:
            results.append(
                {
                    "fold": k,
                    "selected_feature": best_feature,
                    "train_alpha_pct": float(best_alpha),
                    "test_start": str(pd.Timestamp(test_idx[0]).date()),
                    "test_end": str(pd.Timestamp(test_idx[-1]).date()),
                    "test_alpha_pct": test_model["alpha_pct"],
                    "test_t_alpha_naive": test_model["t_alpha_naive"],
                    "test_sharpe": test_model["sharpe_per_period"],
                }
            )

    if not results:
        return {"folds": [], "mean_oos_alpha_pct": None}

    alphas = np.array([r["test_alpha_pct"] for r in results])
    se = alphas.std(ddof=1) / np.sqrt(len(alphas)) if len(alphas) > 1 else float("nan")
    return {
        "folds": results,
        "mean_oos_alpha_pct": float(alphas.mean()),
        "std_oos_alpha_pct": float(alphas.std(ddof=1)) if len(alphas) > 1 else None,
        "t_stat_oos": float(alphas.mean() / se) if se and se > 0 else None,
        "positive_folds": int((alphas > 0).sum()),
        "total_folds": len(alphas),
    }


# ---------------------------------------------------------------------------
# orquestracao
# ---------------------------------------------------------------------------


def run(dataset_path: Path, config: EdgeConfig) -> dict:
    raw = pd.read_csv(dataset_path, parse_dates=["date"])
    panel = prepare_panel(raw, config)
    features = feature_columns(raw)

    sample = effective_sample_size(
        raw,
        label_col=f"fwd_return_{config.label_horizon}d",
        label_horizon=config.label_horizon,
    )
    ic = analyse_information_coefficient(panel, features, config)
    strategy = analyse_strategy_vs_random(panel, features, config)

    top_features = [s["feature"] for s in strategy["signals"][:6]]
    stability = analyse_alpha_stability(panel, top_features, config)
    walk_forward = analyse_walk_forward(panel, features, config)

    survivors = (
        ic.loc[ic["survives_fdr"], "feature"].tolist() if not ic.empty else []
    )
    wf_significant = bool(
        walk_forward.get("t_stat_oos") is not None
        and abs(walk_forward["t_stat_oos"]) > 1.96
        and walk_forward.get("mean_oos_alpha_pct", 0) > 0
    )
    edge_found = bool(survivors) or wf_significant

    return {
        "schema_version": "honest-edge-measurement-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(dataset_path),
        "config": {
            "label_horizon": config.label_horizon,
            "top_quantile": config.top_quantile,
            "cost_bps": config.cost_bps,
            "slippage_bps": config.slippage_bps,
            "round_trip_cost_pct": config.round_trip_cost_pct,
            "execution": "sinal no fechamento de i, entrada na abertura de i+1",
        },
        "effective_sample": sample,
        "information_coefficient": ic.to_dict(orient="records") if not ic.empty else [],
        "ic_summary": {
            "features_tested": int(len(ic)),
            "significant_naive": int((ic["t_naive"].abs() > 1.96).sum()) if not ic.empty else 0,
            "significant_newey_west": int((ic["t_newey_west"].abs() > 1.96).sum())
            if not ic.empty
            else 0,
            "significant_bootstrap": int(ic["bootstrap_significant"].sum())
            if not ic.empty
            else 0,
            "surviving_fdr": len(survivors),
            "survivors": survivors,
        },
        "strategy_vs_random": strategy,
        "alpha_stability": stability,
        "walk_forward": walk_forward,
        "verdict": {
            "edge_demonstrated": edge_found,
            "conclusion": (
                "Sinal sobreviveu a todas as correcoes."
                if edge_found
                else "Nenhum sinal sobrevive a correcao de sobreposicao e multiplos testes."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="data/research/research_dataset_v1.csv")
    parser.add_argument("--out", default="data/honest_edge_measurement.json")
    parser.add_argument("--label-horizon", type=int, default=5)
    parser.add_argument("--top-quantile", type=float, default=0.20)
    parser.add_argument(
        "--allow-no-edge",
        action="store_true",
        help="retorna 0 mesmo sem edge (util para gerar o relatorio sem falhar o CI)",
    )
    args = parser.parse_args()

    config = EdgeConfig(
        label_horizon=args.label_horizon, top_quantile=args.top_quantile
    )
    dataset = Path(args.dataset)
    if not dataset.exists():
        print(f"ERRO: dataset nao encontrado: {dataset}", file=sys.stderr)
        return 2

    report = run(dataset, config)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    sample = report["effective_sample"]
    ic = report["ic_summary"]
    wf = report["walk_forward"]

    print("=" * 78)
    print("MEDICAO HONESTA DE EDGE")
    print("=" * 78)
    print(f"  linhas do dataset          : {sample['rows']}")
    print(f"  AMOSTRA EFETIVA            : {sample['effective_sample_size']}")
    print(f"  fator de superestimacao    : {sample['naive_over_effective_ratio']}x")
    print()
    print(f"  features testadas          : {ic['features_tested']}")
    print(f"  'significativas' (ingenuo) : {ic['significant_naive']}")
    print(f"  significativas Newey-West  : {ic['significant_newey_west']}")
    print(f"  sobrevivem ao FDR          : {ic['surviving_fdr']}  {ic['survivors']}")
    print()
    if wf.get("mean_oos_alpha_pct") is not None:
        print(f"  alfa medio fora da amostra : {wf['mean_oos_alpha_pct']:.4f}%")
        print(f"  t-stat fora da amostra     : {wf.get('t_stat_oos')}")
        print(f"  folds positivos            : {wf['positive_folds']}/{wf['total_folds']}")
    print()
    print(f"  VEREDITO: {report['verdict']['conclusion']}")
    print(f"  relatorio salvo em: {out_path}")

    if not report["verdict"]["edge_demonstrated"] and not args.allow_no_edge:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
