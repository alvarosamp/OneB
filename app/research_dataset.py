from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from app import indicators
from app import research_provenance
from app.market_data import service as market_data_service
from app.temporal_validation import purged_three_way_split

DEFAULT_SYMBOLS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMD",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "AVGO",
    "NFLX",
    "COST",
    "ADBE",
    "CSCO",
    "QCOM",
    "PLTR",
    "SNAP",
    "REGN",
    "VRTX",
    "GILD",
    "AMGN",
    "MDLZ",
    "HON",
    "PYPL",
    "CMCSA",
]

HORIZONS_DAYS = [1, 5, 10, 20]
REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]


@dataclass(frozen=True)
class ResearchDatasetConfig:
    symbols: list[str]
    benchmark_symbol: str = "QQQ"
    period: str = "5y"
    interval: str = "1d"
    min_rows: int = 260
    good_threshold_5d_pct: float = 1.0
    bad_threshold_5d_pct: float = -1.0
    train_pct: float = 0.70
    validation_pct: float = 0.15
    # Purge e embargo nas fronteiras de split. Sem isso, as ultimas amostras de
    # treino tem labels calculados com precos que ja pertencem ao bloco de
    # validacao/teste -- o modelo treina sobre o que deveria estar prevendo.
    # purge_horizon_days: cobre a janela do label. Default = maior horizonte
    #   gerado (20d), para que o dataset seja seguro qualquer que seja o label
    #   escolhido depois. Se voce so vai treinar em label_5d, pode baixar para 5
    #   e recuperar ~7% das linhas.
    # embargo_days: cobre a autocorrelacao das features (a maior janela de
    #   lookback dos indicadores e 50 barras; 20 cobre a maioria).
    purge_horizon_days: int = max(HORIZONS_DAYS)
    embargo_days: int = 20
    output_dir: Path = Path("data/research")
    refresh: bool = False

    @classmethod
    def from_env(cls) -> ResearchDatasetConfig:
        symbols = _symbols_from_env("RESEARCH_DATASET_SYMBOLS") or DEFAULT_SYMBOLS
        return cls(
            symbols=symbols,
            benchmark_symbol=os.getenv("RESEARCH_DATASET_BENCHMARK", "QQQ").upper().strip(),
            period=os.getenv("RESEARCH_DATASET_PERIOD", "5y"),
            min_rows=int(os.getenv("RESEARCH_DATASET_MIN_ROWS", "260")),
            output_dir=Path(os.getenv("RESEARCH_DATASET_OUTPUT_DIR", "data/research")),
            refresh=os.getenv("RESEARCH_DATASET_REFRESH", "false").lower() == "true",
        )


def _symbols_from_env(name: str) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    return sorted({item.strip().upper() for item in raw.split(",") if item.strip()})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _date_index(index: pd.Index) -> pd.DatetimeIndex:
    dates = pd.to_datetime(index, errors="coerce", utc=True)
    return dates.tz_convert(None).normalize()


def _safe_float(value) -> float | None:
    if value is None or pd.isna(value) or np.isinf(value):
        return None
    return float(value)


def _clean_history(history: pd.DataFrame) -> pd.DataFrame:
    if history is None or history.empty:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    df = history.copy()
    df.columns = [str(column).lower() for column in df.columns]
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    df = df[REQUIRED_COLUMNS]
    df.index = _date_index(df.index)
    df = df[~df.index.isna()]
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    for column in REQUIRED_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df.dropna(subset=["open", "high", "low", "close"])


def _load_history(symbol: str, config: ResearchDatasetConfig) -> pd.DataFrame:
    history = market_data_service.get_bars(
        symbol,
        period=config.period,
        interval=config.interval,
        refresh=config.refresh,
    )
    return _clean_history(history)


def _history_quality(symbol: str, history: pd.DataFrame, provider: str | None, min_rows: int) -> dict:
    issues: list[str] = []
    if history.empty:
        return {
            "symbol": symbol,
            "provider": provider,
            "status": "FAIL",
            "rows": 0,
            "issues": ["EMPTY_HISTORY"],
        }

    duplicate_dates = int(history.index.duplicated().sum())
    missing_cells = int(history[REQUIRED_COLUMNS].isna().sum().sum())
    non_positive_prices = int((history[["open", "high", "low", "close"]] <= 0).sum().sum())
    negative_volume = int((history["volume"] < 0).sum())
    zero_volume = int((history["volume"] == 0).sum())
    gaps = pd.Series(history.index).diff().dt.days.dropna()
    suspicious_gaps = int((gaps > 5).sum())
    max_gap = int(gaps.max()) if not gaps.empty else 0

    if len(history) < min_rows:
        issues.append("INSUFFICIENT_HISTORY")
    if duplicate_dates:
        issues.append("DUPLICATE_DATES")
    if missing_cells:
        issues.append("MISSING_OHLCV_CELLS")
    if non_positive_prices:
        issues.append("NON_POSITIVE_PRICES")
    if negative_volume:
        issues.append("NEGATIVE_VOLUME")
    if suspicious_gaps:
        issues.append("SUSPICIOUS_DATE_GAPS")

    status = "PASS" if not issues else "WARN"
    if len(history) < min_rows or non_positive_prices:
        status = "FAIL"

    return {
        "symbol": symbol,
        "provider": provider,
        "status": status,
        "rows": int(len(history)),
        "start": str(history.index.min().date()),
        "end": str(history.index.max().date()),
        "duplicate_dates": duplicate_dates,
        "missing_ohlcv_cells": missing_cells,
        "non_positive_prices": non_positive_prices,
        "negative_volume": negative_volume,
        "zero_volume_rows": zero_volume,
        "max_gap_days": max_gap,
        "suspicious_gaps_gt5d": suspicious_gaps,
        "issues": issues,
    }


def _benchmark_features(benchmark: pd.DataFrame) -> pd.DataFrame:
    if benchmark.empty:
        return pd.DataFrame()
    close = benchmark["close"]
    out = pd.DataFrame(index=benchmark.index)
    out["benchmark_close"] = close
    out["benchmark_ret_5d"] = close.pct_change(5) * 100
    out["benchmark_ret_20d"] = close.pct_change(20) * 100
    out["benchmark_sma50_gap_pct"] = (close / indicators.sma(close, 50) - 1) * 100
    out["benchmark_volatility_20d"] = indicators.annualized_volatility(close)
    return out


def _add_features(history: pd.DataFrame, benchmark: pd.DataFrame) -> pd.DataFrame:
    close = history["close"]
    high = history["high"]
    low = history["low"]
    volume = history["volume"]
    adx = indicators.adx(high, low, close)
    macd = indicators.macd(close)
    bb = indicators.bollinger_bands(close)
    ema20 = indicators.ema(close, 20)
    ema50 = indicators.ema(close, 50)
    sma20 = indicators.sma(close, 20)
    sma50 = indicators.sma(close, 50)
    recent_high20 = close.shift(1).rolling(20, min_periods=20).max()
    recent_low20 = close.shift(1).rolling(20, min_periods=20).min()

    out = history.copy()
    out["ret_1d"] = close.pct_change(1) * 100
    out["ret_5d"] = close.pct_change(5) * 100
    out["ret_20d"] = close.pct_change(20) * 100
    out["mom_accel_5v20"] = out["ret_5d"] - (out["ret_20d"] / 4)
    out["sma20_gap_pct"] = (close / sma20 - 1) * 100
    out["sma50_gap_pct"] = (close / sma50 - 1) * 100
    out["ema20_50_gap_pct"] = (ema20 / ema50 - 1) * 100
    out["rsi14"] = indicators.rsi(close, 14)
    out["rsi_momentum_3d"] = out["rsi14"] - out["rsi14"].shift(3)
    out["macd"] = macd["macd"]
    out["macd_signal"] = macd["signal"]
    out["macd_hist"] = macd["histogram"]
    out["macd_hist_slope_3d"] = out["macd_hist"] - out["macd_hist"].shift(3)
    out["adx14"] = adx["adx"]
    out["di_diff"] = adx["plus_di"] - adx["minus_di"]
    out["atr14"] = indicators.atr(high, low, close, 14)
    out["atr_pct"] = out["atr14"] / close * 100
    out["annualized_volatility"] = indicators.annualized_volatility(close)
    out["volume_ratio20"] = indicators.volume_ratio(volume, 20)
    out["volume_z20"] = (volume - volume.rolling(20, min_periods=20).mean()) / volume.rolling(20, min_periods=20).std().replace(0, np.nan)
    out["range_pct"] = (high - low) / close * 100
    out["close_position_20d"] = (close - recent_low20) / (recent_high20 - recent_low20).replace(0, np.nan)
    out["high20_breakout_pct"] = (close / recent_high20 - 1) * 100
    out["low20_rebound_pct"] = (close / recent_low20 - 1) * 100
    out["bollinger_width_pct"] = (bb["upper"] - bb["lower"]) / close * 100
    out["bollinger_position"] = (close - bb["lower"]) / (bb["upper"] - bb["lower"]).replace(0, np.nan)

    bench = _benchmark_features(benchmark).reindex(out.index, method="ffill")
    out = out.join(bench)
    out["rel_ret_5d_vs_benchmark"] = out["ret_5d"] - out["benchmark_ret_5d"]
    out["rel_ret_20d_vs_benchmark"] = out["ret_20d"] - out["benchmark_ret_20d"]
    return out


def _future_drawdown(close: pd.Series, horizon: int) -> pd.Series:
    values = []
    for i in range(len(close)):
        window = close.iloc[i + 1 : i + horizon + 1]
        if len(window) < horizon or not close.iloc[i]:
            values.append(np.nan)
            continue
        values.append((float(window.min()) / float(close.iloc[i]) - 1) * 100)
    return pd.Series(values, index=close.index)


def _future_runup(close: pd.Series, horizon: int) -> pd.Series:
    values = []
    for i in range(len(close)):
        window = close.iloc[i + 1 : i + horizon + 1]
        if len(window) < horizon or not close.iloc[i]:
            values.append(np.nan)
            continue
        values.append((float(window.max()) / float(close.iloc[i]) - 1) * 100)
    return pd.Series(values, index=close.index)


def _add_labels(frame: pd.DataFrame, config: ResearchDatasetConfig) -> pd.DataFrame:
    out = frame.copy()
    close = out["close"]
    for horizon in HORIZONS_DAYS:
        out[f"fwd_return_{horizon}d"] = (close.shift(-horizon) / close - 1) * 100
        out[f"fwd_drawdown_{horizon}d"] = _future_drawdown(close, horizon)
        out[f"fwd_runup_{horizon}d"] = _future_runup(close, horizon)

    label = pd.Series("neutral", index=out.index, dtype="object")
    label[out["fwd_return_5d"] >= config.good_threshold_5d_pct] = "good"
    label[out["fwd_return_5d"] <= config.bad_threshold_5d_pct] = "bad"
    out["label_5d"] = label
    return out


def _assign_splits(panel: pd.DataFrame, config: ResearchDatasetConfig) -> pd.DataFrame:
    """Divide o painel em train/validation/test COM purge e embargo.

    Linhas que caem na zona de purge recebem ``split == "purged"`` e nao devem
    entrar em nenhum conjunto. Elas sao mantidas no arquivo de proposito: o
    auditor consegue ver exatamente o que foi removido e por que, em vez de as
    linhas simplesmente desaparecerem.

    O gap aplicado em cada fronteira e ``purge_horizon_days + embargo_days``,
    medido em BARRAS DE PREGAO (nao em dias corridos).
    """
    out = panel.copy()
    dates = pd.Index(sorted(out["date"].dropna().unique()))
    if dates.empty:
        out["split"] = "train"
        return out

    try:
        result = purged_three_way_split(
            out["date"],
            label_horizon=int(config.purge_horizon_days),
            train_pct=config.train_pct,
            validation_pct=config.validation_pct,
            embargo=int(config.embargo_days),
        )
    except ValueError:
        # Serie curta demais para purgar: e melhor falhar de forma visivel do
        # que devolver silenciosamente um split vazado.
        raise ValueError(
            f"serie com {len(dates)} datas e curta demais para purge de "
            f"{config.purge_horizon_days} + embargo de {config.embargo_days} "
            "barras. Aumente o periodo (config.period) ou reduza o purge."
        ) from None

    out["split"] = result.split.to_numpy()
    return out


def _feature_columns(panel: pd.DataFrame) -> list[str]:
    excluded = {
        "symbol",
        "date",
        "provider",
        "data_quality_status",
        "label_5d",
        "split",
        *REQUIRED_COLUMNS,
    }
    return [
        column
        for column in panel.columns
        if column not in excluded and not column.startswith("fwd_") and pd.api.types.is_numeric_dtype(panel[column])
    ]


def _dataset_quality(panel: pd.DataFrame, feature_columns: list[str]) -> dict:
    if panel.empty:
        return {"status": "FAIL", "issues": ["EMPTY_DATASET"]}
    issues: list[str] = []
    split_counts = panel["split"].value_counts().to_dict()
    if "train" not in split_counts or "test" not in split_counts:
        issues.append("MISSING_TIME_SPLIT")
    if panel["symbol"].nunique() < 5:
        issues.append("LOW_SYMBOL_COVERAGE")
    label_counts = panel["label_5d"].value_counts(dropna=False).to_dict()
    if len(label_counts) < 3:
        issues.append("WEAK_LABEL_DIVERSITY")
    feature_nan_pct = panel[feature_columns].isna().mean().sort_values(ascending=False) if feature_columns else pd.Series(dtype=float)
    high_nan_features = [name for name, value in feature_nan_pct.items() if value > 0.25]
    if high_nan_features:
        issues.append("FEATURES_WITH_HIGH_NAN")
    status = "PASS" if not issues else "WARN"
    return {
        "status": status,
        "issues": issues,
        "rows": int(len(panel)),
        "symbols": int(panel["symbol"].nunique()),
        "start": str(panel["date"].min().date()),
        "end": str(panel["date"].max().date()),
        "split_counts": {str(key): int(value) for key, value in split_counts.items()},
        "label_5d_counts": {str(key): int(value) for key, value in label_counts.items()},
        "feature_count": len(feature_columns),
        "high_nan_features": high_nan_features[:20],
    }


def _write_outputs(panel: pd.DataFrame, summary: dict, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = output_dir / "research_dataset_v1.csv"
    summary_path = output_dir / "research_dataset_v1.summary.json"
    panel.to_csv(dataset_path, index=False)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return dataset_path, summary_path


def build_research_dataset(config: ResearchDatasetConfig | None = None, *, write: bool = True) -> tuple[pd.DataFrame, dict]:
    config = config or ResearchDatasetConfig.from_env()
    benchmark = _load_history(config.benchmark_symbol, config)
    rows: list[pd.DataFrame] = []
    coverage: list[dict] = []

    for symbol in config.symbols:
        history = _load_history(symbol, config)
        provider = history.attrs.get("provider") if hasattr(history, "attrs") else None
        quality = _history_quality(symbol, history, provider, config.min_rows)
        coverage.append(quality)
        if quality["status"] == "FAIL":
            continue
        frame = _add_features(history, benchmark)
        frame = _add_labels(frame, config)
        frame["symbol"] = symbol
        frame["provider"] = provider
        frame["data_quality_status"] = quality["status"]
        frame["date"] = frame.index
        rows.append(frame.reset_index(drop=True))

    panel = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if not panel.empty:
        panel = panel.replace([np.inf, -np.inf], np.nan)
        required_labels = [f"fwd_return_{horizon}d" for horizon in HORIZONS_DAYS]
        panel = panel.dropna(subset=["date", "close", "label_5d", *required_labels])
        trainable_features = _feature_columns(panel)
        if trainable_features:
            panel = panel.dropna(subset=trainable_features)
        panel = _assign_splits(panel, config)
        front = ["symbol", "date", "split", "provider", "data_quality_status"]
        panel = panel[front + [column for column in panel.columns if column not in front]]

    features = _feature_columns(panel) if not panel.empty else []
    summary = {
        "version": "research_dataset_v1",
        "created_at": _utc_now(),
        "config": {
            **asdict(config),
            "output_dir": str(config.output_dir),
        },
        "coverage": coverage,
        "dataset_quality": _dataset_quality(panel, features),
        "feature_columns": features,
        "label_columns": [column for column in panel.columns if column.startswith("fwd_")] + (["label_5d"] if not panel.empty else []),
    }
    if write:
        dataset_path, summary_path = _write_outputs(panel, summary, config.output_dir)
        summary["outputs"] = {"dataset": str(dataset_path), "summary": str(summary_path)}
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

        # Manifesto imutavel: sem isto, nao ha como provar depois QUAL conjunto
        # exato de linhas treinou um modelo. Os CSVs de cache sao sobrescritos a
        # cada refresh, entao o hash precisa ser tirado no momento da geracao.
        try:
            source_paths = _source_cache_paths(config)
            research_provenance.write_manifest(
                dataset_path,
                command="app.research_dataset.build_research_dataset",
                parameters={
                    **asdict(config),
                    "output_dir": str(config.output_dir),
                    "horizons_days": HORIZONS_DAYS,
                },
                input_paths=source_paths,
                extra={
                    "rows": int(len(panel)),
                    "symbols": int(panel["symbol"].nunique()) if not panel.empty else 0,
                    "split_counts": {
                        str(k): int(v)
                        for k, v in (
                            panel["split"].value_counts().to_dict().items()
                            if not panel.empty
                            else []
                        )
                    },
                    "purge_horizon_days": config.purge_horizon_days,
                    "embargo_days": config.embargo_days,
                    "summary_sha256": research_provenance.file_fingerprint(summary_path)[
                        "sha256"
                    ],
                },
            )
        except Exception as exc:  # manifesto nunca deve derrubar a geracao
            summary.setdefault("warnings", []).append(
                f"falha ao escrever manifesto de proveniencia: {exc}"
            )
    return panel, summary


def _source_cache_paths(config: ResearchDatasetConfig) -> list[Path]:
    """Caminhos dos CSVs de cache que alimentaram este dataset.

    Sao estes arquivos que precisam ser hasheados: o dataset derivado sozinho
    nao diz de onde veio, e o cache e sobrescrito a cada atualizacao.
    """
    cache_root = Path("data/raw/prices")
    paths: list[Path] = []
    symbols = [*config.symbols, config.benchmark_symbol]
    for symbol in symbols:
        safe = symbol.replace("/", "_")
        for provider_dir in sorted(cache_root.glob("*")):
            candidate = provider_dir / config.interval / config.period / f"{safe}.csv"
            if candidate.exists():
                paths.append(candidate)
    return paths
