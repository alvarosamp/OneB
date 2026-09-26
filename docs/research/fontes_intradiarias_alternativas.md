# Fontes intradiárias alternativas para Nasdaq e S&P 500

## Decisão

O conjunto de pesquisa deve manter três camadas explicitamente separadas:

1. **Execução/futuro:** NQ e, quando adquirido, ES com contratos individuais ou série contínua cuja regra de rolagem esteja registrada.
2. **Proxy intradiário:** QQQ e SPY para força relativa, confirmação de mercado e breadth proxy. Seus preços, custos, horários e volumes não substituem NQ/ES.
3. **Macro diário causal:** yields, dólar amplo e VIX, usando somente a última observação que já estaria publicada no instante da decisão.

## Avaliação das fontes

| Fonte | Instrumento | Profundidade/granularidade | Papel recomendado | Limitação |
|---|---|---|---|---|
| Databento, CME Globex MDP 3.0 | NQ e ES | Trades, OHLCV, BBO, profundidade e MBO; minuto/tick | Fonte preferida para validação final de futuros | Requer conta, credencial e dados pagos conforme uso |
| CME DataMine | NQ e ES | Dados históricos oficiais da bolsa | Auditoria/validação final | Aquisição normalmente paga e arquivos mais trabalhosos |
| Tiingo Equity Intraday | QQQ e SPY | Barras intradiárias consolidadas configuráveis | Filtros de confirmação e força relativa | ETF proxy; limite de chamadas/linhas da conta precisa ser respeitado |
| Alpha Vantage | QQQ e SPY | 1/5/15/30/60 min, meses históricos desde 2000 | Alternativa de proxy | Histórico intradiário é endpoint premium |
| Polygon | ETFs e índices | Agregados por minuto | Alternativa de proxy/índice | Planos e licenciamento; índice minuto desde 2023 na documentação consultada |

## Estado local

- NQ M1/M5: 26/12/2022–12/12/2025 já normalizado em `D:\OneB\market-data\research-ready`.
- HonorPro: `US100.s` e `US500.s` existem, mas não retornaram histórico M5.
- Tiingo: a credencial local retornou QQQ e SPY M5, mas a tentativa longa revelou limite de 10.000 linhas e depois HTTP 429. O coletor `scripts/export_tiingo_intraday.py` agora pagina, identifica truncamento e preserva manifesto; a coleta completa deve ser retomada depois da renovação da cota.
- Macro FRED: DGS2, DGS5, DGS10, DGS30, DTWEXBGS e VIXCLS já estão em cache.

## Filtros a testar

### Nasdaq

- retorno e z-score de QQQ e SPY, sempre defasados uma barra;
- força relativa QQQ–SPY em 5, 15, 30 e 60 minutos;
- confirmação ou divergência entre retorno do NQ e retorno do SPY;
- regime diário por variação de DGS2/DGS10, inclinação 10Y–2Y, dólar e VIX;
- interação entre Gap Drive/13X e regime, avaliada incrementalmente contra o sinal sem filtro.

### Ouro

- retorno e força relativa de XAGUSD, EURUSD, WTI e Brent;
- ouro/prata e divergência ouro–EURUSD como proxies, sem chamar EURUSD de DXY;
- regime diário por DGS10, juro real de 10 anos e dólar;
- interação com fakeout e London Box, exigindo ganho fora da amostra e número mínimo de trades.

## Protocolo causal

- Features M5 são calculadas apenas após o fechamento da barra e usadas na abertura seguinte.
- Séries diárias são deslocadas pelo calendário de publicação; na ausência de timestamp point-in-time, usa-se no mínimo D+1.
- Seleção de filtros ocorre apenas nos folds de desenvolvimento; o holdout final não escolhe parâmetros.
- Resultado positivo precisa sobreviver a custos, anos/regimes, parâmetros vizinhos e correção por múltiplos testes.
- QQQ/SPY podem decidir se um trade de NQ é permitido, mas nunca fornecem o preço de execução do futuro.

## Fontes

1. Databento. [Futures: Introduction and continuous-contract conventions](https://databento.com/docs/examples/futures/futures-introduction/special-conventions-for-futures-on-databento).
2. Databento. [Continuous contract symbology](https://databento.com/docs/standards-and-conventions/symbology).
3. Databento. [Historical API](https://databento.com/docs/api-reference-historical?historical=http).
4. CME Group. [CME DataMine Equity Execution Statistics FAQ](https://www.cmegroup.com/market-data/files/datamine-equity-faq.pdf).
5. Tiingo. [Equity Realtime and Historical Intraday API](https://www.tiingo.com/documentation/equity-realtime-stock-data).
6. Alpha Vantage. [TIME_SERIES_INTRADAY documentation](https://www.alphavantage.co/documentation/).
7. Polygon. [Indices minute aggregates](https://polygon.io/docs/flat-files/indices/minute-aggregates/2023/10).
