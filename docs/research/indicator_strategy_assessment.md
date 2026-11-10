# Avaliacao das estrategias quantitativas fornecidas

## Diagnostico

O documento fornecido define sete hipoteses operacionais, mas anteriormente o
repositorio nao continha uma implementacao Python unificada dessas sete
estrategias. Havia tres componentes diferentes:

1. regras tecnicas diarias genericas em `scripts/audit_indicator_setups.py`;
2. um indicador visual MTF H4/H1/M15/M5/M1 em
   `mql5/Indicators/MTF_Liquidity_Structure.mq5`;
3. o novo pesquisador intradiario, que inicialmente cobria opening range, VWAP
   e overnight, mas nao formalizava todos os nomes e parametros do documento.

As sete familias agora estao integradas em
`scripts/intraday_setup_research.py`, junto das quatro extensoes intradiarias.

## Mapeamento

| Estrategia fornecida | Implementacao atual | Parametros pesquisados | Estado empirico |
|---|---|---|---|
| Gold Fakeout v0 | `gold_fakeout` | lookback 18/20/22; MA1000; confirmacao 1/2; buffer 0,15 ATR | bloqueada sem dados intradiarios |
| Gold Mean Reversion | `gold_mean_reversion` | BB20 1,8/2,0/2,2; RSI 25/30/35; ADX max. 20/25; alvo media/VWAP/R | bloqueada sem dados intradiarios |
| Gold Trend Pullback | `gold_trend_pullback` | EMA 15/40, 20/50, 25/60; ADX 18/22; DI | bloqueada sem dados intradiarios |
| Gold Volatility Squeeze | `gold_volatility_squeeze` | percentil BBW 15%/25%; expansao de largura | bloqueada sem dados intradiarios |
| Nasdaq 13x Sweep | `nasdaq_13x_sweep` | lookback 11/13/15; buffer 0,10/0,15/0,25 ATR; 12/24 barras | bloqueada sem dados intradiarios |
| Nasdaq 13x EMA-ATR | `nasdaq_13x_ema_atr` | distancia 1/1,5/2 ATR; reclaim 0,25/0,50 ATR; alvo 1,5R-2,5R | bloqueada sem dados intradiarios |
| Nasdaq 13x Momentum Failure | `nasdaq_13x_momentum_failure` | lookback 13; momentum 3/5; melhoria RSI 0/3 | bloqueada sem dados intradiarios |

## Hipoteses tornadas explicitas

- `MA1000` foi formalizada como media movel simples. Se a origem pretendia EMA,
  isso deve ser testado como uma familia separada, nao alterado depois de ver o
  holdout.
- A confirmacao do Gold Fakeout exige que 1 ou 2 candles posteriores permaneçam
  de volta dentro do nivel varrido. A entrada continua sendo a abertura seguinte
  ao ultimo candle de confirmacao.
- Momentum failure foi formalizado como novo extremo de preco com reclaim e RSI
  que nao confirma o extremo na janela de 3 ou 5 barras.
- A janela do ouro e 07:00-13:30 America/New_York; o Fakeout so sinaliza entre
  07:00 e 11:00, conforme o documento.
- Para XAUUSD, valor do ponto, spread e comissao dependem da corretora. Os
  defaults sao placeholders e impedem uma conclusao economica universal.
- NQ/MNQ M1 sao agregados causalmente para 5, 10 e 15 minutos. Se a fonte ja
  comecar em M5, apenas 5/10/15 podem ser derivados.
- O dataset publico USA100 da Dukascopy e tratado como `NAS100`, nunca como NQ.
  Ele serve como teste de transferencia em CFD, nao substitui contratos CME.

## Controles implementados

- sinal no fechamento e entrada na abertura seguinte;
- prioridade pessimista do stop em barras ambiguas;
- stop estrutural nos sweeps;
- uma posicao por vez e encerramento dentro da sessao;
- custos em tick, valor do ponto, spread, slippage e comissao;
- sensibilidade a custos de 1x, 1,5x e 2x;
- screening de entradas antes de ajustar saidas;
- expanding walk-forward no desenvolvimento;
- holdout final de 20% congelado;
- correcao Benjamini-Hochberg;
- estabilidade por regime;
- meta-labeling com limiar escolhido em previsoes OOF do desenvolvimento;
- manifesto SHA-256 dos dados, codigo, configuracao e resultados;
- bloqueio com menos de 250 sessoes.

## Decisao atual

As estrategias estao **implementadas como hipoteses**, mas nenhuma pode ser
classificada como aprovada, experimentalmente positiva ou rejeitada sem os
arquivos intradiarios. O estado correto e `BLOCKED`/`NEEDS_MORE_DATA`.

Elas nao foram conectadas ao simulador operacional da aplicacao porque isso
criaria sinais sem evidencia. A integracao de paper trading so deve ocorrer
depois que um setup sobreviver ao holdout, a custos 2x e a parametros vizinhos.
