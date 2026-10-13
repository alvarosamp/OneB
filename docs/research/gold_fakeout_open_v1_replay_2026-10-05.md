# Gold Fakeout — reimplementação aberta v1: primeiro replay pré-registrado

Classificação: **COLLECTING / SHADOW**. Não aprovado para paper trading. Nenhuma ordem.

## O que foi testado

Regra congelada em `configs/preregistration/gold_fakeout_open_v1.json` (SHA256 no
`LOCK.json`, gravado **antes** do primeiro replay). É uma leitura explícita da
descrição do trader, não o EX5 original:

- XAUUSD.s HonorPro, barras M5 agregadas em M10; MM1000; rompimento das 20 barras
  anteriores a favor da MM; duas confirmações (fechamento mantém o nível rompido);
  janela 07:00–11:00 BRT com offset do servidor **assumido** UTC+3.
- Fakeout = barra que volta para dentro do nível antes de confirmar → `INVALIDATED`.
- Entrada na abertura da barra M5 seguinte ao fechamento da confirmação 2, ask/bid
  + slippage 0,05; stop no extremo das barras do setup; alvo 1,5R; saída máx. 4 h;
  comissão hipotética 0,10/onça ida-volta; uma posição por vez.

Dados: `synced-2026-09-25/XAUUSD.s_M5_2026-04-01_2026-09-26.csv.gz`
(sha256 `9c223ac7…`), 10/04 a 25/09/2026, 145 sessões, 32.834 barras M5.

## Resultado

| Métrica | Valor |
|---|---|
| Rompimentos detectados | 151 (67 invalidados como fakeout, 84 formados) |
| Trades completos | 71 (13 sinais ignorados por posição aberta, 0 censurados) |
| Expectância líquida | **−0,15R** por trade |
| IC 95% (bootstrap) | −0,38R a +0,09R |
| Acerto | 35,2% (IC 25–47%) com alvo 1,5R |
| Fator de lucro | 0,73 |
| Drawdown | 12,2R |
| Entrada aleatória (200 seeds, mesma janela/custos/stops) | p05 −0,28R · p50 −0,02R · p95 +0,19R |
| Percentil do setup vs. aleatório | **20** |
| Rompimento simples (sem MM/confirmações) | −0,13R, IC −0,26 a 0,00 |

Veredito pela regra registrada: **COLLECTING** (145/250 sessões, 71/100 trades).
Leitura parcial: nada indica vantagem; o setup está abaixo da mediana de
entradas aleatórias com a mesma geometria. Para detectar +0,15R com o desvio
observado (1,06R) são necessários ~400 trades.

Quebras por direção/hora existem no JSON, mas **não** podem ser usadas para
escolher filtros: seria seleção sobre o mesmo período (data snooping). Qualquer
filtro novo vira `gold_fakeout_open_v2` pré-registrado e testado em dados futuros.

## Bug encontrado e corrigido durante a execução (registrado por transparência)

A primeira execução carimbava o sinal na **abertura** da barra M10. A entrada
acontecia na barra M5 do meio da própria barra de sinal — antes de ela fechar.
Sintoma: a baseline "rompimento simples" deu +0,34R com IC acima de zero. Após
carimbar no fechamento, caiu para −0,13R: o "edge" era 100% vazamento de futuro.
Correção em `app/setups/base.py` (`bar_close`), teste
`test_entry_never_happens_before_signal_bar_closes`. Um segundo ajuste alinhou a
liberação da posição ao fechamento da barra de saída, verificado pelo teste de
paridade replay × shadow ao vivo. Nenhum parâmetro da regra mudou.

## Próximos passos

1. Rodar `scripts/run_shadow.py` durante as sessões: coleta ticks bid/ask
   prospectivos (com manifest/SHA256) e grava cada transição no ledger SHADOW.
2. Verificar o offset do servidor ao longo da mudança de horário (a captura de
   05/10/2026 mostrou servidor = UTC+3).
3. Reavaliar com `scripts/run_setup_replay.py` ao atingir 250 sessões / 100 trades;
   se o IC continuar contendo zero, arquivar a v1.

Reprodução:

```powershell
python scripts/run_setup_replay.py --setup gold_fakeout_open_v1 --bars "D:/OneB/market-data/mt5/HonorPro/synced-2026-09-25/XAUUSD.s_M5_2026-04-01_2026-09-26.csv.gz"
python -m pytest tests/test_setups_and_execution.py tests/test_shadow_and_ledger.py -q
```
