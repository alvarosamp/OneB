# Validação intradiária real — NQ e XAUUSD

## Conclusão executiva

Nenhum setup foi aprovado para paper trading nesta rodada. Os melhores resultados positivos no holdout não sobreviveram à correção Benjamini–Hochberg e não foram estáveis o bastante no calendário. A conclusão rigorosa é **experimental**, com necessidade de validação em feed independente e custos reais da corretora.

## Dados efetivamente usados

| Mercado | Representação | Timeframe testado | Cobertura | Sessões RTH usadas | Arquivo |
|---|---|---:|---|---:|---|
| Nasdaq | NQ futuro contínuo | M5 | 26/12/2022–11/12/2025 | 765 | `D:\OneB\market-data\research-ready\NQ_M5_2022-12-26_2025-12-12.csv.gz` |
| Ouro | XAUUSD spot/CFD  | M10, agregado causalmente do M5 | 04/01/2021–30/01/2026 | 1.282 | `D:\OneB\market-data\research-ready\XAUUSD_M10_2021-01-01_2026-01-31.csv.gz` |

Os arquivos normalizados não contêm timestamps duplicados, volume negativo ou OHLC inválido. Não houve preenchimento de candles ausentes. Fins de semana, feriados e interrupções do feed permanecem como gaps. Os dados brutos M1/M5 e os ZIPs originais também foram preservados em `D:\OneB\market-data\kaggle`.

O NQ veio do conjunto público “NQ Futures 1-Min Bar (2022–2025)”. O XAUUSD veio do conjunto público CC0 “XAU/USD Gold Price Historical Data (2004–2026)”. Esses dados permitem pesquisa, mas não substituem um feed oficial da CME nem o feed da corretora que executará as ordens.

## Protocolo

- Sinal calculado apenas no fechamento da barra `t`; entrada na abertura de `t+1`.
- Empate intrabar entre stop e alvo resolvido pessimisticamente pelo stop.
- Posições encerradas na sessão; nenhuma informação futura é preenchida.
- Desenvolvimento expanding walk-forward com cinco folds.
- Últimos 20% das sessões mantidos como holdout intocado: NQ 13/05/2025–11/12/2025; XAUUSD 23/12/2024–30/01/2026.
- NQ: custo modelado de US$ 15 por round trip por contrato (comissão, um tick de spread e slippage). XAUUSD: custo provisório de 0,24 unidade de preço por round trip; precisa ser substituído pela especificação da corretora.
- 59 hipóteses de entrada e 165 combinações finais no NQ; 81 hipóteses de entrada e 180 combinações finais no XAUUSD.
- P-valores dos 12 finalistas corrigidos por Benjamini–Hochberg.

## Ranking Nasdaq — holdout

| Rank | Setup | Parâmetros | Trades | Retorno líquido | Expectancy | PF | Sharpe | Meses positivos | q BH | Decisão |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | Opening breakout | OR 15m, buffer 0, stop 1 ATR, alvo 2R, saída 60m | 1.102 | US$ 14.100,85 | US$ 12,80 | 1,038 | 0,767 | 4/8 | 0,975 | Experimental |
| 2 | Opening breakout | OR 15m, buffer 0, stop 1 ATR, alvo 3R, saída 30m | 1.248 | US$ 15.154,83 | US$ 12,14 | 1,042 | 0,711 | 3/8 | 0,975 | Experimental |
| 3 | Opening breakout | OR 15m, buffer 0, stop 1 ATR, alvo 2R, saída 30m | 1.316 | US$ 6.206,09 | US$ 4,72 | 1,016 | 0,337 | 3/8 | 0,975 | Experimental |

O `nasdaq_13x_momentum_failure` liderou o desenvolvimento (expectancy US$ 40,94; PF 1,102; quatro folds positivos), mas inverteu no holdout para −US$ 17.722,27, expectancy −US$ 27,06 e PF 0,931. Isso é um caso claro de instabilidade temporal e deve ser rejeitado na parametrização atual. O `nasdaq_13x_sweep` também ficou negativo entre os finalistas de holdout. As demais famílias não acumularam evidência de desenvolvimento suficiente para entrar entre os 12 finalistas.

## Ranking ouro — holdout

| Rank | Setup | Parâmetros | Trades | Retorno líquido | Expectancy | PF | Sharpe | Meses positivos | q BH | Decisão |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | Trend pullback | EMA 20/50, ADX≥22, stop 0,75 ATR, alvo 1,5R, saída 120m | 67 | 24,75 | 0,37 | 1,158 | 0,890 | 5/13 | 0,865 | Precisa de mais dados |
| 2 | Opening fade | OR 30m, buffer 1 tick, stop 1,25 ATR, alvo 1,5R, saída 120m | 240 | 46,48 | 0,19 | 1,068 | 0,489 | 6/14 | 0,865 | Experimental |
| 3 | Opening fade | OR 30m, buffer 1 tick, stop 1,25 ATR, alvo 3R, saída 60m | 263 | 25,36 | 0,10 | 1,043 | 0,297 | 7/14 | 0,865 | Experimental |

O primeiro colocado depende de três trades em janeiro de 2026: 2025 isoladamente perdeu 24,90. Isso viola o requisito de estabilidade e impede aprovação. `gold_fakeout`, `gold_mean_reversion`, `gold_volatility_squeeze`, VWAP e rompimentos não apresentaram ganho de desenvolvimento estável suficiente na especificação testada; ficam rejeitados nesta rodada, não rejeitados universalmente.

## Modelos simples versus complexos

No NQ, a regressão logística L1 aplicada como meta-label perdeu US$ 18.512,76 no holdout; Random Forest ganhou US$ 980,47 em 99 trades, mas MCC 0,073, balanced accuracy 0,538 e Brier 0,245 não demonstram ganho incremental robusto. No XAUUSD, a logística teve +9,99 em 55 trades e o Random Forest −6,16; ambas permanecem experimentais. Complexidade não produziu evidência confiável além das regras simples.

## Limitações que impedem promoção

- NQ é uma série contínua de terceiro, sem identificação explícita de rolagens e sem bid/ask; os saltos de rolagem precisam de auditoria por contrato.
- XAUUSD não é GC. Volume é dependente do feed e o valor financeiro por ponto/spread é provisório.
- Não há bid/ask histórico nos dois conjuntos usados; spread e slippage foram modelados.
- O melhor NQ foi positivo em apenas metade dos meses do holdout; o melhor ouro depende de poucos trades de 2026.
- Nenhum q-value ficou abaixo de 10%.

## Próxima decisão

- **Aprovado para paper trading:** nenhum.
- **Precisa de mais dados:** trend pullback do ouro, especialmente GC/MGC oficial ou XAUUSD do broker, com bid/ask.
- **Experimental:** opening breakout NQ e opening fade XAUUSD.
- **Rejeitado nesta parametrização:** 13x momentum failure/sweep no NQ e as famílias de ouro que não chegaram aos finalistas ou falharam fora da amostra.

Uma segunda rodada deve usar contratos individuais NQ/GC da CME ou Databento, regra explícita de rolagem e custos medidos no broker. Só faz sentido testar LightGBM/XGBoost, SHAP e interações depois que uma regra simples repetir o sinal em feed independente.
