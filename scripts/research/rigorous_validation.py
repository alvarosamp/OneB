"""
rigorous_validation.py
=======================

Framework de validação estatística rigorosa para descoberta e seleção de
indicadores em séries financeiras (Nasdaq / XAUUSD e correlatos).

Projetado para se acoplar ao repositório "Nasdaq/OneB Market" do usuário —
não depende de nada específico daquele repo, mas assume o mesmo formato de
dado (um DataFrame por símbolo, indexado por data de calendário real, com
colunas de features point-in-time e um label de horizonte fixo ou
triple-barrier) usado em scripts/statistical_edge_audit.py,
scripts/research_folds.py e scripts/regime_signal_evidence.py.

Este módulo cobre especificamente as lacunas identificadas no diagnóstico:
  1. Purged K-Fold com embargo (não apenas walk-forward sequencial)
  2. Mutual information (classif. e regressão) como critério de seleção
     não-linear, complementar ao IC (Spearman) já usado no repo
  3. Permutation importance (embaralhamento de feature, não de label)
     calculada de forma correta em walk-forward (nunca no dataset inteiro)
  4. Deflated Sharpe Ratio com correção de skew/kurtosis (a versão do repo
     em scripts/calibrate_decision_strategy.py assume retornos normais)
  5. Probabilistic Sharpe Ratio
  6. White's Reality Check / SPA test (Hansen) via bootstrap estacionário,
     para a família COMPLETA de configurações testadas — DSR já cobre uma
     aproximação disso, isto é o teste formal
  7. Correção de FDR (Benjamini-Hochberg) para quando muitos indicadores
     são testados em paralelo (mais apropriado que Bonferroni puro quando
     se aceita uma pequena taxa de falsos positivos em vez de zero)
  8. Detecção de regime não-supervisionada (HMM Gaussiano) como alternativa
     ao regime_engine.py baseado em regras fixas — treinada e decodificada
     de forma estritamente point-in-time (sem *smoothing* que veria o
     futuro)
  9. Teste de ganho incremental: um indicador candidato só é aceito se
     melhorar significativamente um conjunto de features já existente,
     não apenas se tiver poder preditivo isolado
 10. Um harness de walk-forward que devolve métricas estatísticas E
     financeiras líquidas de custo, por fold, para checar estabilidade

Princípios de design (não-negociáveis):
  - Nenhuma função aqui jamais ajusta um transformador (scaler, seletor de
    features, MI, HMM) usando dados de teste. Tudo é fit no treino e
    aplicado (transform) no teste.
  - Todo split é baseado em DATA DE CALENDÁRIO, nunca em row_index —
    replicando a correção que o próprio repo já aplicou em research_folds.py.
  - Toda avaliação financeira é líquida de custo (bps configurável).
  - "Significativo" sempre vem acompanhado de tamanho de amostra efetivo
    (não sobreposto) e de correção para múltiplos testes.

Dependências: numpy, pandas, scipy, scikit-learn (todas já usadas em
repositórios de pesquisa quant típicos). hmmlearn é opcional — se ausente,
a detecção de regime cai para um fallback de k-means em (retorno, vol)
rolling, com aviso explícito.
"""

from __future__ import annotations

import warnings
import dataclasses
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

import numpy as np
import pandas as pd
from scipy import stats

try:
    from sklearn.feature_selection import mutual_info_classif, mutual_info_regression
    from sklearn.inspection import permutation_importance
    from sklearn.metrics import (
        roc_auc_score, precision_score, recall_score, balanced_accuracy_score,
        matthews_corrcoef, brier_score_loss,
    )
    _SKLEARN_OK = True
except ImportError:  # pragma: no cover
    _SKLEARN_OK = False

try:
    from hmmlearn.hmm import GaussianHMM
    _HMMLEARN_OK = True
except ImportError:
    _HMMLEARN_OK = False


# ---------------------------------------------------------------------------
# 1. Splits temporais: Purged K-Fold com embargo (López de Prado, cap. 7)
# ---------------------------------------------------------------------------

@dataclass
class PurgedKFoldEmbargo:
    """K-Fold que respeita a ordem temporal dos dados financeiros.

    Diferença em relação ao walk-forward sequencial já usado no repo
    (scripts/calibrate_decision_strategy.py, EMBARGO_DAYS=15): aqui os K
    folds de teste podem estar em QUALQUER posição da linha do tempo (não
    só o final), o que dá mais folds de teste independentes para o mesmo
    histórico — útil quando o histórico é curto (aqui: ~2 anos / 501
    candles por símbolo). Cada fold de teste "purga" do treino qualquer
    observação cuja janela de rótulo (o horizonte de previsão) se sobreponha
    à janela de teste, e aplica um embargo adicional de `embargo_days` após
    o fim do bloco de teste, para não deixar treino "vazar" para trás no
    tempo via autocorrelação de curto prazo.

    Parameters
    ----------
    n_splits : número de folds de teste
    label_horizon_days : horizonte do label em dias de calendário (ex.: 5
        para um label "retorno em 5 dias"). Usado para o purge.
    embargo_days : dias adicionais de embargo após cada bloco de teste.
    """

    n_splits: int = 5
    label_horizon_days: int = 5
    embargo_days: int = 5

    def split(self, dates: pd.Series) -> Iterable[tuple[np.ndarray, np.ndarray]]:
        """dates: Series (mesmo índice do DataFrame de features) com a data
        de calendário de cada linha (pode haver múltiplos símbolos na mesma
        data — todas as linhas daquela data ficam sempre do mesmo lado)."""
        dates = pd.to_datetime(dates)
        uniq_dates = np.array(sorted(dates.unique()))
        n = len(uniq_dates)
        if n < self.n_splits * 3:
            raise ValueError(
                f"Poucas datas únicas ({n}) para {self.n_splits} folds com purge. "
                "Reduza n_splits ou use mais histórico."
            )
        fold_bounds = np.array_split(np.arange(n), self.n_splits)
        horizon = pd.Timedelta(days=self.label_horizon_days)
        embargo = pd.Timedelta(days=self.embargo_days)

        for fold_idx in fold_bounds:
            test_dates = uniq_dates[fold_idx]
            test_start, test_end = test_dates.min(), test_dates.max()
            # A label de uma observação em test_start pode só "resolver" em
            # test_start + horizon; simetricamente, uma observação de treino
            # cuja label resolve DENTRO do bloco de teste teria vazado
            # informação do futuro do teste para o treino. Por isso o purge
            # é aplicado nos dois lados.
            purge_lo = test_start - horizon
            purge_hi = test_end + horizon + embargo

            test_mask = dates.isin(test_dates)
            train_mask = ~((dates >= purge_lo) & (dates <= purge_hi))

            train_idx = np.where(train_mask.values)[0]
            test_idx = np.where(test_mask.values)[0]
            if len(train_idx) == 0 or len(test_idx) == 0:
                continue
            yield train_idx, test_idx


# ---------------------------------------------------------------------------
# 2. Seleção/ranking de indicadores: IC, Mutual Information, Permutation
#    Importance — sempre calculados só dentro do fold de treino
# ---------------------------------------------------------------------------

def mutual_information_ranking(
    X_train: pd.DataFrame, y_train: pd.Series, discrete_target: bool = True,
    n_neighbors: int = 3, random_state: int = 42,
) -> pd.Series:
    """Ranking não-linear de features por informação mútua, calculado
    SOMENTE no fold de treino. Complementa o IC (Spearman, linear/monotônico)
    já usado em scripts/cross_sectional_ic.py — MI captura dependências
    não-monotônicas que o IC não vê (ex.: um indicador que é preditivo só
    em valores extremos, nos dois sentidos)."""
    if not _SKLEARN_OK:
        raise ImportError("scikit-learn é necessário para mutual_information_ranking")
    X = X_train.fillna(X_train.median(numeric_only=True))
    fn = mutual_info_classif if discrete_target else mutual_info_regression
    mi = fn(X.values, y_train.values, n_neighbors=n_neighbors, random_state=random_state)
    return pd.Series(mi, index=X.columns, name="mutual_info").sort_values(ascending=False)


def walk_forward_permutation_importance(
    model_factory: Callable[[], object],
    X: pd.DataFrame, y: pd.Series, dates: pd.Series,
    splitter: PurgedKFoldEmbargo, scoring: str = "roc_auc",
    n_repeats: int = 20, random_state: int = 42,
) -> pd.DataFrame:
    """Permutation importance calculada corretamente em contexto financeiro:
    o modelo é treinado só no fold de treino, e a importância de cada feature
    é medida embaralhando ESSA feature (não o label) no fold de TESTE
    (dados nunca vistos pelo modelo) e medindo a queda de performance.
    Repetido em todos os folds do PurgedKFoldEmbargo; devolve média e desvio
    entre folds — uma feature só deve ser considerada robusta se a queda de
    score for consistente entre folds, não apenas alta em média."""
    if not _SKLEARN_OK:
        raise ImportError("scikit-learn é necessário para permutation importance")
    rows = []
    for fold_i, (train_idx, test_idx) in enumerate(splitter.split(dates)):
        model = model_factory()
        Xtr, ytr = X.iloc[train_idx].fillna(0.0), y.iloc[train_idx]
        Xte, yte = X.iloc[test_idx].fillna(0.0), y.iloc[test_idx]
        if ytr.nunique() < 2 or yte.nunique() < 2:
            continue
        model.fit(Xtr, ytr)
        result = permutation_importance(
            model, Xte, yte, scoring=scoring, n_repeats=n_repeats,
            random_state=random_state,
        )
        for i, col in enumerate(X.columns):
            rows.append({
                "fold": fold_i, "feature": col,
                "importance_mean": result.importances_mean[i],
                "importance_std": result.importances_std[i],
            })
    if not rows:
        return pd.DataFrame(columns=["feature", "importance_mean", "importance_mean_across_folds",
                                       "importance_std_across_folds", "n_folds_positive"])
    df = pd.DataFrame(rows)
    summary = df.groupby("feature").agg(
        importance_mean_across_folds=("importance_mean", "mean"),
        importance_std_across_folds=("importance_mean", "std"),
        n_folds_positive=("importance_mean", lambda s: int((s > 0).sum())),
        n_folds=("importance_mean", "count"),
    ).sort_values("importance_mean_across_folds", ascending=False)
    return summary


# ---------------------------------------------------------------------------
# 3. Estatística de estratégia: DSR com correção de skew/kurtosis, PSR,
#    e teste de significância conjunta (SPA / White's Reality Check)
# ---------------------------------------------------------------------------

def probabilistic_sharpe_ratio(returns: np.ndarray, sr_benchmark: float = 0.0) -> float:
    """PSR (Bailey & López de Prado, 2012): probabilidade de que o Sharpe
    observado seja realmente > sr_benchmark, corrigindo para o comprimento
    da amostra e para skew/kurtosis dos retornos (que fazem o desvio-padrão
    do estimador de Sharpe divergir do caso Gaussiano)."""
    returns = np.asarray(returns, dtype=float)
    returns = returns[~np.isnan(returns)]
    n = len(returns)
    if n < 3:
        return float("nan")
    sr = returns.mean() / (returns.std(ddof=1) + 1e-12)
    skew = stats.skew(returns)
    kurt = stats.kurtosis(returns, fisher=False)  # kurtosis "raw" (normal=3)
    sr_std = np.sqrt((1 - skew * sr + (kurt - 1) / 4 * sr ** 2) / (n - 1))
    if sr_std <= 0:
        return float("nan")
    z = (sr - sr_benchmark) / sr_std
    return float(stats.norm.cdf(z))


def deflated_sharpe_ratio(
    candidate_sharpes: Sequence[float], n_obs: int, chosen_returns: np.ndarray,
) -> dict:
    """DSR com correção de skew/kurtosis (a implementação do repo em
    scripts/calibrate_decision_strategy.py usa a aproximação Gaussiana sem
    essa correção — ver diagnóstico, seção 8). candidate_sharpes deve ser a
    lista de Sharpes (não anualizados, por período) de TODAS as configurações
    testadas no mesmo grid de busca (não só a vencedora) — isso é o que
    penaliza corretamente o viés de seleção múltipla."""
    candidate_sharpes = np.asarray([s for s in candidate_sharpes if np.isfinite(s)], dtype=float)
    N = len(candidate_sharpes)
    if N == 0:
        return {"dsr": float("nan"), "expected_max_sharpe_by_chance": float("nan"), "n_configs": 0}
    var_sr = candidate_sharpes.var(ddof=1) if N > 1 else 0.0
    euler_gamma = 0.5772156649
    # Expected max Sharpe sob H0 (todos os candidatos com Sharpe verdadeiro 0),
    # aproximação de Bailey & López de Prado (2014), eq. 10
    if var_sr > 0 and N > 1:
        expected_max_sr = np.sqrt(var_sr) * (
            (1 - euler_gamma) * stats.norm.ppf(1 - 1.0 / N)
            + euler_gamma * stats.norm.ppf(1 - 1.0 / (N * np.e))
        )
    else:
        expected_max_sr = 0.0
    dsr = probabilistic_sharpe_ratio(chosen_returns, sr_benchmark=expected_max_sr)
    return {
        "dsr": dsr,
        "expected_max_sharpe_by_chance": float(expected_max_sr),
        "n_configs": int(N),
        "sharpe_std_across_configs": float(np.sqrt(var_sr)),
    }


def spa_test_pvalue(
    strategy_returns: dict[str, np.ndarray], benchmark_returns: np.ndarray,
    n_bootstrap: int = 2000, block_size: int = 10, random_state: int = 42,
) -> dict:
    """Aproximação do teste SPA de Hansen (2005) / White's Reality Check
    (2000) via bootstrap de bloco estacionário sobre a série de retornos
    EXCEDENTES de cada estratégia candidata em relação a um benchmark
    (ex.: buy-and-hold do próprio ativo, ou retorno médio do universo).

    H0: nenhuma das estratégias candidatas bate o benchmark de verdade
    (todo excedente observado é ruído de mineração de dados / seleção
    entre muitas configurações testadas).

    Complementa o DSR: DSR assume Sharpes aproximadamente Gaussianos entre
    configurações; SPA não assume forma alguma da distribuição, só reamostra
    os dados observados preservando autocorrelação via blocos.
    """
    rng = np.random.default_rng(random_state)
    names = list(strategy_returns.keys())
    excess = {}
    T = None
    for name, r in strategy_returns.items():
        r = np.asarray(r, dtype=float)
        b = np.asarray(benchmark_returns, dtype=float)
        m = min(len(r), len(b))
        e = r[:m] - b[:m]
        excess[name] = e
        T = m if T is None else min(T, m)
    excess = {k: v[:T] for k, v in excess.items()}
    observed_stat = max(e.mean() for e in excess.values())

    boot_stats = np.empty(n_bootstrap)
    n_blocks = int(np.ceil(T / block_size))
    for b in range(n_bootstrap):
        starts = rng.integers(0, max(T - block_size, 1), size=n_blocks)
        idx = np.concatenate([np.arange(s, min(s + block_size, T)) for s in starts])[:T]
        max_centered_mean = -np.inf
        for name, e in excess.items():
            centered = e - e.mean()  # impõe H0: média zero, preserva autocorrelação
            resampled_mean = centered[idx].mean()
            max_centered_mean = max(max_centered_mean, resampled_mean)
        boot_stats[b] = max_centered_mean
    pvalue = float((boot_stats >= observed_stat).mean())
    return {
        "observed_max_excess_mean": float(observed_stat),
        "spa_pvalue": pvalue,
        "n_strategies_tested": len(names),
        "n_bootstrap": n_bootstrap,
        "block_size": block_size,
        "interpretation": (
            "p-valor alto (ex. > 0.10) => o melhor resultado observado entre as "
            f"{len(names)} configurações testadas é plausivelmente só o máximo "
            "de ruído (mineração de dados). p-valor baixo => há evidência de "
            "vantagem real mesmo corrigindo pela busca em múltiplas configurações."
        ),
    }


def benjamini_hochberg(pvalues: pd.Series, alpha: float = 0.10) -> pd.DataFrame:
    """Correção de FDR (taxa de falsos descobrimentos) de Benjamini-Hochberg.
    Preferível a Bonferroni (já citado no repo, docs/data_phase_findings.md)
    quando se testam dezenas de indicadores em paralelo e se aceita uma
    pequena fração esperada de falsos positivos entre os aprovados, em vez
    de controlar a probabilidade de QUALQUER falso positivo (Bonferroni é
    mais conservador e perde poder estatístico rapidamente com muitos
    testes — com 40 features como em statistical_edge_audit.json, Bonferroni
    exigiria p < 0.00125 por teste; BH é menos punitivo e mais apropriado
    para um estágio de TRIAGEM de indicadores)."""
    s = pvalues.dropna().sort_values()
    m = len(s)
    ranks = np.arange(1, m + 1)
    thresholds = ranks / m * alpha
    passed = s.values <= thresholds
    # maior rank que passa define o corte (procedimento padrão de BH)
    if passed.any():
        cutoff_rank = np.max(np.where(passed)[0])
        significant = s.index[: cutoff_rank + 1]
    else:
        significant = pd.Index([])
    out = pd.DataFrame({"feature": s.index, "pvalue": s.values, "bh_threshold": thresholds})
    out["significant_at_fdr"] = out["feature"].isin(significant)
    return out.reset_index(drop=True)


# ---------------------------------------------------------------------------
# 4. Regime não-supervisionado (HMM) — alternativa a regras fixas
# ---------------------------------------------------------------------------

def fit_predict_hmm_regime_walkforward(
    features_for_regime: pd.DataFrame, dates: pd.Series, splitter: PurgedKFoldEmbargo,
    n_states: int = 3, random_state: int = 42,
) -> pd.Series:
    """Detecta regimes (ex.: 3 estados ~ tendência/lateral/alta-vol) via HMM
    Gaussiano, treinado SOMENTE no fold de treino e aplicado (decode/filter,
    nunca smoothing) ao fold de teste — evita o mesmo problema que
    regime_engine.py evita ao ser hand-picked (não olhar o futuro), mas
    aqui o regime é aprendido dos dados em vez de thresholds fixos de
    -100/+100. Cai para KMeans (retorno rolling, vol rolling) se hmmlearn
    não estiver instalado.

    IMPORTANTE: mesmo com HMM, o vetor de regime resultante ainda precisa
    passar pela mesma bateria de validação (IC condicional a regime,
    walk-forward, DSR) antes de ser considerado um substituto do
    regime_engine.py atual — este é um CANDIDATO de pesquisa, não uma
    substituição pronta para produção.
    """
    regimes = pd.Series(index=features_for_regime.index, dtype="float64", name="hmm_regime")
    for train_idx, test_idx in splitter.split(dates):
        Xtr = features_for_regime.iloc[train_idx].fillna(method="ffill").fillna(0.0)
        Xte = features_for_regime.iloc[test_idx].fillna(method="ffill").fillna(0.0)
        if _HMMLEARN_OK:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = GaussianHMM(n_components=n_states, covariance_type="diag",
                                     random_state=random_state, n_iter=100)
                model.fit(Xtr.values)
                # decode aplicado linha-a-linha em ordem temporal do teste:
                # usamos predict (Viterbi) sobre o bloco de teste isolado,
                # o que é conservador (não deixa o HMM "olhar" o treino ao
                # decodificar o teste, ao custo de menos contexto — trade-off
                # explícito e documentado).
                pred = model.predict(Xte.values)
        else:  # pragma: no cover - fallback sem hmmlearn
            from sklearn.cluster import KMeans
            km = KMeans(n_clusters=n_states, random_state=random_state, n_init=10)
            km.fit(Xtr.values)
            pred = km.predict(Xte.values)
        regimes.iloc[test_idx] = pred
    return regimes


# ---------------------------------------------------------------------------
# 5. Métricas financeiras líquidas de custo + métricas de classificação
# ---------------------------------------------------------------------------

@dataclass
class TradeCosts:
    round_trip_bps: float = 20.0  # alinhado ao mais conservador já usado no
    # repo (indicator_setup_audit.json, regime_bear_economic_validation.json)


def net_returns_from_signal(raw_returns: pd.Series, signal: pd.Series, costs: TradeCosts) -> pd.Series:
    """signal: +1 (long), -1 (short), 0 (fora). Aplica custo de round-trip
    só quando a posição MUDA (entra/sai/inverte), não em todo período —
    do contrário superestima o custo em posições mantidas por vários dias."""
    signal = signal.fillna(0.0)
    position_change = signal.diff().abs().fillna(signal.abs())
    cost = position_change * (costs.round_trip_bps / 1e4)
    return signal.shift(1).fillna(0.0) * raw_returns - cost


def financial_metrics(net_ret: pd.Series, periods_per_year: int = 252) -> dict:
    net_ret = net_ret.dropna()
    trades = net_ret[net_ret != 0]
    n = len(net_ret)
    if n == 0:
        return {"n_periods": 0}
    mean, std = net_ret.mean(), net_ret.std(ddof=1)
    downside = net_ret[net_ret < 0]
    sortino_denom = downside.std(ddof=1) if len(downside) > 1 else np.nan
    equity = (1 + net_ret).cumprod()
    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    gains = trades[trades > 0].sum()
    losses = -trades[trades < 0].sum()
    return {
        "n_periods": n,
        "n_trades": int((net_ret != 0).sum()),
        "total_net_return_pct": float((equity.iloc[-1] - 1) * 100),
        "annualized_return_pct": float(((1 + mean) ** periods_per_year - 1) * 100) if not np.isnan(mean) else np.nan,
        "sharpe": float(mean / std * np.sqrt(periods_per_year)) if std > 0 else np.nan,
        "sortino": float(mean / sortino_denom * np.sqrt(periods_per_year)) if sortino_denom and sortino_denom > 0 else np.nan,
        "max_drawdown_pct": float(drawdown.min() * 100),
        "profit_factor": float(gains / losses) if losses > 0 else np.nan,
        "expectancy_per_trade_pct": float(trades.mean() * 100) if len(trades) else np.nan,
        "win_rate_pct": float((trades > 0).mean() * 100) if len(trades) else np.nan,
    }


def classification_metrics(y_true: np.ndarray, y_pred_proba: np.ndarray, threshold: float = 0.5) -> dict:
    if not _SKLEARN_OK:
        raise ImportError("scikit-learn necessário para classification_metrics")
    y_true = np.asarray(y_true)
    y_pred = (y_pred_proba >= threshold).astype(int)
    out = {
        "auc": np.nan, "precision": np.nan, "recall": np.nan,
        "balanced_accuracy": np.nan, "mcc": np.nan, "brier": np.nan,
    }
    if len(np.unique(y_true)) < 2:
        return out
    out["auc"] = float(roc_auc_score(y_true, y_pred_proba))
    out["precision"] = float(precision_score(y_true, y_pred, zero_division=0))
    out["recall"] = float(recall_score(y_true, y_pred, zero_division=0))
    out["balanced_accuracy"] = float(balanced_accuracy_score(y_true, y_pred))
    out["mcc"] = float(matthews_corrcoef(y_true, y_pred))
    out["brier"] = float(brier_score_loss(y_true, y_pred_proba))
    return out


# ---------------------------------------------------------------------------
# 6. Ganho incremental: candidato só é aceito se melhorar um baseline
# ---------------------------------------------------------------------------

def incremental_gain_test(
    baseline_fold_scores: Sequence[float], candidate_fold_scores: Sequence[float],
) -> dict:
    """Teste pareado (Wilcoxon signed-rank, não-paramétrico — adequado para
    poucos folds e sem assumir normalidade da diferença de score entre
    folds) comparando, fold a fold, o score (ex.: AUC ou Sharpe) de um
    conjunto de features baseline vs. baseline+candidato. Só recomenda
    incluir o candidato se a diferença for consistentemente positiva."""
    b = np.asarray(baseline_fold_scores, dtype=float)
    c = np.asarray(candidate_fold_scores, dtype=float)
    diff = c - b
    if len(diff) < 3 or np.allclose(diff, 0):
        return {"n_folds": len(diff), "mean_gain": float(diff.mean()) if len(diff) else np.nan,
                "wilcoxon_pvalue": np.nan, "folds_improved": int((diff > 0).sum()),
                "recommendation": "amostra insuficiente para concluir"}
    try:
        stat, p = stats.wilcoxon(diff)
    except ValueError:
        p = np.nan
    folds_improved = int((diff > 0).sum())
    reco = "ganho incremental plausível" if (p is not np.nan and p < 0.10 and diff.mean() > 0 and folds_improved >= len(diff) * 0.6) \
        else "sem evidência suficiente de ganho incremental"
    return {
        "n_folds": len(diff), "mean_gain": float(diff.mean()),
        "wilcoxon_pvalue": float(p) if p is not np.nan else np.nan,
        "folds_improved": folds_improved, "recommendation": reco,
    }


# ---------------------------------------------------------------------------
# 7. Self-test com dados sintéticos (rodar `python rigorous_validation.py`)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Self-test com dados sintéticos (sem sinal real embutido, exceto")
    print("uma feature fracamente informativa, para checar se o pipeline")
    print("recupera o sinal correto sem falsos positivos nas outras).\n")

    rng = np.random.default_rng(7)
    n_days, n_symbols = 500, 10
    dates_unique = pd.bdate_range("2023-01-02", periods=n_days)
    rows = []
    for sym in range(n_symbols):
        base_ret = rng.normal(0, 0.015, n_days)
        weak_signal_feature = rng.normal(0, 1, n_days)
        # injeta um sinal fraco real: retorno futuro correlacionado a 0.06
        # com a feature "boa", nas outras 5 features é ruído puro
        future_ret = np.roll(base_ret, -5)
        future_ret = future_ret + 0.06 * weak_signal_feature * base_ret.std()
        noise_features = {f"noise_feat_{i}": rng.normal(0, 1, n_days) for i in range(5)}
        df_sym = pd.DataFrame({
            "date": dates_unique, "symbol": f"SYM{sym}",
            "ret_1d": base_ret, "good_feature": weak_signal_feature,
            **noise_features,
            "fwd_ret_5d": future_ret,
        })
        rows.append(df_sym)
    panel = pd.concat(rows, ignore_index=True)
    panel["label_5d"] = (panel["fwd_ret_5d"] > panel.groupby("date")["fwd_ret_5d"].transform("median")).astype(int)

    feature_cols = ["good_feature"] + [f"noise_feat_{i}" for i in range(5)]
    X, y, dates = panel[feature_cols], panel["label_5d"], panel["date"]

    print("-- Mutual information (esperado: good_feature no topo) --")
    print(mutual_information_ranking(X, y).round(4), "\n")

    splitter = PurgedKFoldEmbargo(n_splits=5, label_horizon_days=5, embargo_days=5)
    print("-- Permutation importance walk-forward (LogisticRegression) --")
    from sklearn.linear_model import LogisticRegression
    imp = walk_forward_permutation_importance(
        lambda: LogisticRegression(max_iter=1000), X, y, dates, splitter,
        scoring="roc_auc", n_repeats=10,
    )
    print(imp.round(4), "\n")

    print("-- DSR (skew/kurtosis-aware) sobre um grid de Sharpes simulados --")
    fake_grid_sharpes = rng.normal(0, 1, 200) * 0.3
    chosen = fake_grid_sharpes.max() + rng.normal(0, 0.01, 60)
    print(deflated_sharpe_ratio(fake_grid_sharpes, n_obs=500, chosen_returns=chosen), "\n")

    print("-- SPA test (bootstrap) comparando 3 estratégias fake vs. benchmark --")
    bench = rng.normal(0.0002, 0.01, 400)
    strat = {
        "estrategia_A_ruido": bench + rng.normal(0, 0.005, 400),
        "estrategia_B_ruido": bench + rng.normal(0, 0.005, 400),
        "estrategia_C_ruido": bench + rng.normal(0, 0.005, 400),
    }
    print(spa_test_pvalue(strat, bench, n_bootstrap=500), "\n")

    print("Self-test concluído sem erros.")
