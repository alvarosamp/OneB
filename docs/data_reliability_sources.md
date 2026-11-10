# Confiabilidade de Dados de Mercado

Este projeto nao deve tratar qualquer feed gratuito como verdade unica para
validar edge estatistico. A regra operacional e simples: pesquisa pode usar
fonte conveniente; conclusao de edge precisa de dado ajustado, auditavel e
reconciliado.

## Decisao atual

Para candles diarios de acoes/ETFs, use Tiingo EOD como fonte primaria quando
`MARKET_DATA_PROVIDER=tiingo` e `TIINGO_API_KEY` estiverem configurados.
Motivo: o endpoint EOD entrega OHLCV ajustado, campos de dividendos e splits,
e documenta correcao de precos ao longo da noite.

Yahoo/yfinance fica como fallback de desenvolvimento e cache local, nao como
base final para validar uma vantagem estatistica.

## Matriz de fontes

| Uso | Fonte recomendada | Confiabilidade | Observacao |
| --- | --- | --- | --- |
| Backtest EOD de acoes/ETFs US | Tiingo EOD | Alta para pesquisa | OHLCV ajustado e corporate actions; bom custo/beneficio. |
| Producao intraday / execucao | Polygon SIP ou Databento US Equities | Alta | Preferir feeds SIP/exchange para timestamps, volume e cobertura. |
| Nasdaq real-time oficial | Nasdaq Basic / Nasdaq Data Link | Muito alta | Melhor quando houver necessidade contratual de dado direto de exchange. |
| Macro, yields, VIX, calendario economico | FRED | Fonte oficial | Usar FRED/ALFRED quando revisions point-in-time importarem. O app agora cacheia series FRED em `data/raw/macro/fred`. |
| Fundamentais oficiais | SEC EDGAR APIs | Fonte primaria | Melhor para XBRL/fatos reportados; exige mapeamento por CIK e filing date. |
| Noticias/earnings operacionais | Finnhub/FMP | Media | Util para contexto; nao usar como unica fonte de label/edge. |

## Macro: FRED, DXY e US10Y

FRED continua sendo a fonte primaria para:

- `DXY`: `DTWEXBGS`, Trade Weighted U.S. Dollar Index: Broad, Goods.
- `US10Y`: `DGS10`, Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity.

Melhorias implementadas:

1. Cache persistente das series FRED em `data/raw/macro/fred/<SERIE>.csv`.
2. Se FRED estiver indisponivel, o app tenta usar o cache antes de devolver vazio.
3. Para continuidade operacional, `DXY` pode cair para `DX-Y.NYB` via Yahoo.
4. Para continuidade operacional, `US10Y` pode cair para `^TNX / 10` via Yahoo, porque `^TNX`
   e cotado em decimos de ponto percentual.

Esses proxies nao substituem FRED em validacao final de edge. Eles servem para
evitar que a UI/auditoria perca completamente o contexto macro durante uma queda
temporaria da API ou ausencia local de `FRED_API_KEY`.

## Protocolo minimo antes de confiar em um edge

1. Usar dados ajustados por splits/dividendos para features de preco.
2. Manter metadados por arquivo: provedor, periodo, data de coleta, linhas,
   inicio/fim e problemas de qualidade.
3. Reconciliar pelo menos uma amostra diaria contra outro provedor:
   tolerancia sugerida de `0.5%` para close ajustado e `5%` para volume.
4. Falhar a pesquisa se mais de `2%` dos candles do universo tiverem gaps,
   duplicatas, OHLC inconsistente ou divergencia acima da tolerancia.
5. Separar claramente dados de pesquisa de dados de producao. Edge descoberto
   em EOD nao vira regra intraday sem novo teste no feed intraday.
6. Para fundamentalis, fazer join por `filingDate`/data de disponibilidade,
   nunca por periodo fiscal apenas.

## Fontes consultadas

- Tiingo EOD docs: https://www.tiingo.com/documentation/end-of-day
- Tiingo Stock API overview: https://www.tiingo.com/products/stock-api
- Polygon Stocks REST overview: https://polygon.io/docs/rest/stocks/overview
- Databento US Equities: https://databento.com/equities
- Nasdaq Data Link docs: https://docs.data.nasdaq.com/
- Nasdaq Basic: https://www.nasdaq.com/solutions/nasdaq-basic
- FRED series observations API: https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- SEC EDGAR APIs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
