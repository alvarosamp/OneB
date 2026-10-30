# Resultados da pesquisa (gerado em 2026-10-29)

Universo: 30 acoes grandes da Nasdaq + QQQ/SPY, diario, 2014-10 a 2026-10. Execucao na abertura
do dia seguinte ao sinal, custo de 10 bps por lado, long-only. Treino 2014-2020 / teste 2021-2026.
**Vies de sobrevivencia:** o universo sao as vencedoras de hoje, entao todo retorno absoluto esta inflado.

## 1) Regras classicas (carteira igual-peso, periodo de TESTE 2021-2026)
| Estrategia | CAGR% | Sharpe | MaxDD% | Exposicao% | Trades | Win% | Media/trade% |
|---|---|---|---|---|---|---|---|
| Buy & Hold (30 acoes) | 18.4 | 0.92 | -36.4 | 100 | - | - | - |
| Golden cross 50/200 | 14.2 | 1.08 | -13.9 | 64 | 135 | 49 | +27.5 |
| Momentum 6m + SMA200 | 11.3 | 0.98 | -16.0 | 59 | 769 | 33 | +4.5 |
| Preco > SMA200 | 11.5 | 0.96 | -17.5 | 63 | 744 | 25 | +4.9 |
| Donchian 20/10 | 5.8 | 0.67 | -12.9 | 43 | 765 | 42 | +1.7 |
| MACD cruzamento | 7.4 | 0.69 | -21.9 | 50 | 1779 | 38 | +1.0 |
| Bollinger inferior | 6.7 | 0.73 | -12.6 | 23 | 755 | 69 | +1.5 |
| RSI14 < 30 | 4.0 | 0.64 | -6.3 | 12 | 258 | 72 | +2.5 |
| RSI2 < 10 em alta (sai >70) | 3.8 | 0.82 | -5.5 | 14 | 1121 | 69 | +0.7 |
| Volume 2x + alta | 1.2 | 0.47 | -5.3 | 8 | 341 | 53 | +0.8 |

## 2) Saidas (entrada RSI2<10 em alta)
Sair so quando RSI2>90 (deixar correr) foi melhor (teste: Sharpe 1.00, +149 bps/trade) que RSI2>70 (0.82),
saida por tempo 3-10 dias (0.56-0.76) e stops de 5-8% (0.72-0.74): stops pioraram.

## 3) Indicadores (poder preditivo, 22 features, retorno relativo em 5 dias)
Nenhum indicador passou de |t|=2 no treino; IC maximo ~0.03-0.04. Os mais estaveis foram
volatilidade (ATR/vol20/vol60, IC positivo) e retornos longos (ret_120, mom_12_1), ainda fracos.

## 4) ML walk-forward fora da amostra (2019-2026, top-5 por modelo, rebalance 5d)
| Modelo | AUC | Liq CAGR | Liq Sharpe | Bruto Sharpe | Giro |
|---|---|---|---|---|---|
| Regressao logistica | 0.510 | 26.4% | 0.91 | 1.08 | 51% |
| Gradient boosting | 0.515 | 25.9% | 0.95 | 1.15 | 56% |
| Rede neural MLP 32-16 | 0.507 | 25.9% | 0.97 | 1.21 | 66% |
| Sorteio aleatorio (100x) | 0.500 | 14.2% | 0.67 | 1.07 (+-0.18) | 83% |
| Igual-peso todos (sem custo) | - | 25.7% | 1.22 | - | - |
Conclusao: indistinguivel de sorteio apos custos de giro; pior que simplesmente segurar todos.

## 5) Noticias
- Resultados trimestrais (1302 eventos): movimento medio 5.1% vs 1.7% normal (3.0x). 88% batem EPS,
  mas o preco sobe so em 50% e 30% das vezes "bate e cai >2%". Correlacao surpresa x reacao: 0.16.
- Deriva pos-resultado (reacao > +5%, n=268): +1.5% de excesso em 20d (t=2.4), mas instavel:
  treino t=2.4, teste t=1.2 (e 60d: +5.4% treino vs -0.9% teste). Fraco apos corrigir multiplos testes.
- Risco: 5o percentil do dia do resultado -9.7%; pior -35%.
- Dias de choque sem resultado (228): nenhum efeito significativo.
- Historico de manchetes de anos NAO existe de graca; manchetes atuais passam a ser guardadas em data/news/.

## 6) Rodada 2 — hipóteses pré-definidas (scripts/research_v2.py)
Teste 2021+ (CAGR% / Sharpe / MaxDD%), com ETFs (sem viés de sobrevivência) e ações:
| Estratégia | Treino | Teste |
|---|---|---|
| SPY segurar | 13.2 / 0.81 / -32 | 14.7 / 0.91 / -26 |
| QQQ segurar | 21.6 / 1.04 / -28 | 15.9 / 0.77 / -37 |
| QQQ > SMA200 senão caixa | 8.4 / 0.56 / -27 | 14.4 / 0.92 / -25 |
| QQQ com vol-alvo 15% | 14.7 / 1.03 / -18 | 12.4 / 0.83 / -27 |
| ETFs momentum dual top-3 | 3.8 / 0.34 / -24 | 13.0 / 0.79 / -13 |
| Ações EW (30) | 30.3 / 1.38 / -29 | 18.4 / 0.92 / -36 |
| Ações EW com vol-alvo 15% | 21.9 / 1.45 / -13 | 14.1 / 0.96 / -26 |
| Ações top-10 momentum | 32.9 / 1.24 / -34 | 24.4 / 0.93 / -35 |
| Momentum + filtro QQQ + vol-alvo | 18.1 / 1.25 / -14 | 13.6 / 0.94 / -15 |

Bootstrap em blocos (IC 90%) da diferença de Sharpe vs. comprar e segurar: TODOS os intervalos incluem 0
(larguras de ~±0.4). Ou seja, nenhuma estratégia testada é estatisticamente melhor que a referência;
o que muda de forma consistente é a queda máxima (vol-alvo e filtros reduzem -36% para -15% a -26%).
