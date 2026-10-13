# Operações simuladas condicionadas à tendência

Atualização: a replicação congelada em11–15/05 não confirmou a melhora.
M5/M15 concordantes: quatro trades/-64,47 USD/onça. Tendência M5: cinco/-21,57.
Ver gold_trend_replication_2026-09-27.md. Os resultados positivos abaixo
permanecem apenas como histórico exploratório, não candidatos aprovados.

Classificação: experimental. Nenhuma ordem real ou demo enviada.
Dados: sinais originais Gold M10 em04–08/05/2026 e1.518.115 ticks HonorPro.
13X: valores dos EX5 M5/M15/H1; direção de entrada ainda provisória.

## Regras congeladas e disponibilidade

Cinco regras: sem filtro; tendência M5; tendência M15; concordância M5+M15;
tendência M5 com momentum. M5=EMA5/20 e inclinação EMA20 em3 barras;
M15=EMA20/50 e inclinação EMA50 em3 barras. Momentum é sinal da mudança
de fechamento em3 barras M5. Sinal buy exige tendência ascendente; sell,
descendente. EMA/min_periods exige warmup20/50 barras; sem dados suficientes,
filtro não permite operar. Não se interpretou cor do gráfico como informação futura.

Barras bid reconstruídas dos ticks, resample fechado à esquerda com rótulo
no horário de conclusão; asof usa somente rótulo<=decisão. Timestamp bruto
comum MT5, sem converter para sessão NY. Quotes futuras não podem determinar
tendência atual: teste automatizado altera todas as quotes posteriores e verifica
que as features anteriores permanecem iguais. Lacunas não recebem PnL presumido.

Simulador existente Gold: first_seen+250ms, long ask/short bid, slippage0,05
por lado e comissão0,10 por onça; custos extras hipotéticos. Stops/targets
originais congelados, hold4h, uma posição. 13X: mantém eventos originais de
saída mesmo quando barra entrada é filtrada, e usa maxhold4h como hipótese.

Treino04–05/05 truncado antes06/05; comparação posterior06–08/05.
Validação é partição pela data de decisão de replay contínuo de cada regra:
não reinicia posições no corte para inventar novas entradas. O saldo posterior
não necessariamente é o resultado de uma estratégia escolhida no treino.
Para escolher regra pelo treino exige>=5 trades completos, saldo positivo e
nenhuma censura. Nenhuma regra foi elegível: selected_from_train=null.

**Estas datas já foram examinadas anteriormente.** Não são holdout intocado,
mesmo com features causais e separação temporal. Cinco filtros relacionados
e15 replays13X adicionais implicam múltiplos testes. Não há significância ou
probabilidade de sucesso calibrada. Não eleger vencedor pelo saldo desta semana.

## Gold: há pistas, mas não evidência robusta

Saldos dos trades completos emUSD/onça. Censurados excluídos e risco incompleto.

| Regra | Treino: trades/saldo | Dias posteriores: trades/saldo | Semana contínua: trades/saldo |
|---|---|---|---|
| Sem filtro | 8 / +3,12 | 7 / -31,22 | 15 / -28,10 |
| Tendência M5 | 1 / +14,77 | 3 / +5,36 | 4 / +20,13 |
| Tendência M15 | 3 / -3,33 | 9 / -4,14 | 12 / -7,47 |
| M5 eM15 concordantes | 0 / 0 | 3 / +24,27 | 3 / +24,27 |
| Tendência+momentum M5 | 0 / 0 | 3 / +1,60 | 3 / +1,60 |

Treino truncado pode censurar posições que o replay contínuo depois conclui,
por isso contagens/valores por bloco não precisam somar a semana em geral.
Sem filtro foi inelegível por censura apesar do saldo de treino positivo.
M5+M15 teve três vencedores, mas ZERO trades de treino: não havia evidência
para escolhê-lo previamente. Drawdown marcado desses três trades foi24,87/onça,
apesar de drawdown de trades fechados serzero. Três vencedores não são riscozero.
M5 melhora esta semana, mas quatro trades não sustentam inferência de vantagem.
Não se altera a regra para privilegiar só compra ou horário favorável depois
de observar esses mesmos trades.

## 13X provisório

15 replays (cinco filtros x três TF) concluídos. M5 continuou negativo em
todas as regras; M15 com concordância M5/M15 teve só dois trades e+6,24/onça,
porém o único trade posterior ao corte perdeu0,01. Isso produz PF~625 pelo
denominador quasezero: exemplo de por que PF isolado não aprova um algoritmo.
H1 sem filtro teve duas compras/+8,39; tendência M15 ou concordância teve
uma operação/-16,35. Mudança de quais posições são aceitas também muda os
trades seguintes: não é válido apenas apagar perdas de um resultado pronto.
Nenhuma aprovação; entradas não certificadas e amostra minúscula.

## Artefatos e repetição

Código: scripts/gold_trend_regime_replay.py; testes:
tests/test_gold_trend_regime_replay.py. Seis testes dos filtros/replays passaram.
Saída completa com features de cada sinal, trades, exclusões, custos, hashes e
critérios: output/vendor_indicator_research/gold_trend_regimes_20260927.json.

```powershell
$trendTicks = @(Get-ChildItem -LiteralPath D:/OneB/market-data/mt5/gold-economic-20260927,D:/OneB/market-data/mt5/gold-week-20260927 -Filter '*.csv.gz' | Select-Object -ExpandProperty FullName)
$trendBuffers = @(Get-ChildItem -LiteralPath output/vendor_indicator_research/pilot27cert -Filter '*13x*buffers.csv' | Select-Object -ExpandProperty FullName)
python scripts/gold_trend_regime_replay.py --objects output/vendor_indicator_research/pilot28week/pilot28week_gold_M10_0_XAUUSD.s_PERIOD_M10_objects.csv --ticks $trendTicks --13x-buffers $trendBuffers --output output/vendor_indicator_research/gold_trend_regimes_20260927.json
python -m pytest tests/test_gold_trend_regime_replay.py tests/test_original_gold_ticks.py tests/test_original_13x_ticks.py -q
```

Próxima prova justificável: congelar a hipótese Gold+tendências concordantes
sem promovê-la e replicar em semanas/meses diferentes com os mesmos custos e
registro de todas as posições censuradas. Antes de probabilidades IA ou sinais
operacionais, obter amostra suficiente, custos específicos e teste realmente novo.
