"""Orquestra atualização do histórico e um estudo completo sobre uma lista de ativos."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.research import correlation, events, regimes, store


def run_study(
    symbols: list[str],
    directory: Path = store.DEFAULT_DIR,
    refresh: bool = True,
    fetcher: store.Fetcher | None = None,
    top: int = 15,
) -> dict:
    if refresh:
        for s in symbols:
            store.update(s, directory, fetcher=fetcher)

    closes = store.load_closes(symbols, directory)
    if closes.shape[1] < 2:
        return {"error": "São necessários ao menos 2 ativos com histórico.", "symbols": list(closes.columns)}

    returns = correlation.log_returns(closes)
    pairs = correlation.pair_correlations(returns)
    drift = correlation.correlation_drift(returns)

    per_symbol = {}
    for s in closes.columns:
        c = closes[s].dropna()
        per_symbol[s] = {
            "bars": len(c),
            "regime": regimes.regime_summary(c),
            "rsi_below_30": events.event_study(c, events.signal_rsi_below(c)),
            "golden_cross": events.event_study(c, events.signal_sma_cross_up(c)),
        }

    return {
        "symbols": list(closes.columns),
        "period": [str(closes.index[0].date()), str(closes.index[-1].date())],
        "pairs_tested": len(pairs),
        "pairs_significant": int(pairs["significant"].sum()) if len(pairs) else 0,
        "top_correlations": pairs.head(top).to_dict("records"),
        "biggest_drifts": drift.head(top).to_dict("records"),
        "per_symbol": per_symbol,
        "caveats": [
            "Correlação não implica causalidade.",
            "p_adj corrige múltiplos testes (Benjamini-Hochberg); só 'significant' resiste a isso.",
            "Eventos com n pequeno ou |t_stat| < 2 são indistinguíveis do acaso.",
            "Padrões passados não garantem comportamento futuro; não é recomendação de investimento.",
        ],
    }


def main() -> None:
    tickers = sys.argv[1:] or ["QQQ", "SPY", "GC=F", "BRL=X", "NVDA", "AAPL", "MSFT"]
    print(json.dumps(run_study(tickers), indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
