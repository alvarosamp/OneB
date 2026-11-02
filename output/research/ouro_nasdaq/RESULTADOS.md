# Rodada 5 — Ouro e Nasdaq: indicadores, redes neurais e MT5 (2026-11-02)

Scripts: `scripts/fetch_gold_nasdaq.py` (dados) e `scripts/research_gold_nasdaq.py` (estudo). Números completos em `resultados.json`, `ic_gold.csv` e `ic_nq.csv`.

## Conclusão em uma frase

Nenhum indicador, modelo linear ou rede neural (MLP, LSTM) previu ouro ou Nasdaq de forma confiável nos dois períodos (até 2020 e 2021+). O único padrão estatisticamente forte, a barra de reabertura do ouro, existe nos preços mas some depois do spread e do swap da corretora.

## Dados

| Fonte | O quê | Período |
|---|---|---|
| yfinance | GC=F, NQ=F, QQQ, GLD, DXY, VIX, VIX3M, ^TNX, prata, cobre, petróleo, HYG, IEF, USDJPY (diário) | 2000–2026 |
| FRED (sem chave) | juro real 10a (DFII10), breakeven, curva 10a-2a, NFCI, dólar amplo | 2003–2026 |
| MT5 Honor Pro `XAUUSD.dk` | ouro H1 (custom; conferido: 0,96 de correlação horária com o feed da corretora) | 2019-03 a 2026-09 |
| MT5 Honor Pro `XAUUSD.s` / `US100.s` | feed real com spread por barra | só 7 meses / 7 semanas |
| yfinance 1h | GC=F, NQ=F, QQQ | 2024–2026 (limite de 730 dias) |

O US100 do MT5 tem só 7 semanas, pouco demais para treinar. A Nasdaq intradiária usou o QQQ 1h.

## Protocolo

Sinal no fechamento de t, posição a partir de t+1. Dados cruzados e macro defasados 1 dia. Walk-forward com retreino anual e expurgo de h dias entre treino e teste. Custo de 3 bps por lado no diário e spread real no H1. Critério de achado: |t| > 2,8 no treino **e** |t| > 2 com o mesmo sinal no teste. Significância da AUC por deslocamento circular, que preserva a autocorrelação. Diferença de Sharpe contra comprar e segurar por bootstrap em blocos (IC 90%).

## 1) Varredura de indicadores (63 features × 3 horizontes × 2 ativos = 378 testes)

**Nenhum passou.** Os mais próximos:

| Ativo | h | Indicador | t treino | t teste | Leitura |
|---|---|---|---|---|---|
| Ouro | 1d | retorno de ontem (reversão) | -3,55 | -1,59 | enfraqueceu |
| Ouro | 1d | juro real 10a (nível) | +2,70 | +1,72 | fraco, mesmo sentido |
| Ouro | 1d | momentum 12-1 | +2,86 | +1,77 | fraco, mesmo sentido |
| NQ | 5d | cobre 5d (queda → alta do NQ) | -2,65 | -2,63 | **candidato a acompanhar** |
| NQ | 5d | VIX/VIX3M (backwardation → alta) | +2,36 | +2,01 | repete a rodada 3 |

Com 378 testes, é de esperar uns 2 a 4 casos de |t| ≈ 2,6 só por acaso. Os candidatos acima ficam em observação.

Ouro × juros reais / dólar: a correlação **simultânea** em 20 dias é de -0,7 a -0,9 na maioria dos anos (exceção: 2025, +0,42). Isso explica o preço, mas não o prevê.

## 2) Redes neurais diárias (walk-forward 2012–2026)

AUC (0,5 = sorteio) e Sharpe da estratégia comprado/fora, líquida de custos:

| Ativo | Modelo | h | AUC 2012–20 | AUC 2021+ | Sharpe 2021+ | Comprar e segurar 2021+ |
|---|---|---|---|---|---|---|
| Ouro | Logística | 1d | 0,491 | **0,544** (p=0,008) | 0,94 | 0,64 |
| Ouro | MLP | 1d | 0,499 | **0,547** (p=0,002) | 0,46 | 0,64 |
| Ouro | LSTM | 5d | 0,477 | 0,549 (p=0,10) | 0,94 | 0,64 |
| Ouro | LSTM | 20d | 0,469 | 0,586 (p=0,12) | 0,67 | 0,64 |
| NQ | MLP | 1d | 0,517 | 0,484 | 0,49 | 0,62 |
| NQ | LSTM | 5d | 0,519 | 0,454 | 0,62 | 0,62 |
| NQ | Logística | 20d | 0,584 (p=0,05) | 0,448 | 0,29 | 0,62 |

- **Ouro:** os modelos acertam mais em 2021+ e erram mais que um sorteio em 2012–2020. O melhor p (0,002) não passa a correção para 36 testes (limite de 0,0014). A melhora coincide com a alta forte do ouro, então não é confiável.
- **Nasdaq:** nada. Nenhum modelo bate comprar e segurar. Isso repete a rodada 1 (ML indistinguível de sorteio).
- Filtros de tendência (SMA200, 12 meses) não aumentam o retorno. A SMA200 no NQ reduz a queda máxima de -35% para -20% em 2021+, o mesmo achado de risco das rodadas anteriores.

## 3) Ouro H1 pelo MT5 (2019–2026)

- **Sazonalidade por hora:** só a hora 1 do servidor passou (+2,8 bps treino, t=3,7; +5,1 bps teste, t=4,9; positiva em todos os 8 anos). É a primeira barra depois da pausa diária do ouro.
- **Teste executável no feed real** (`XAUUSD.s`): compra no ask às 23h e venda no bid à 1h rendem +2,4 bps por noite. O swap do MT5 (comprado, -66 pontos/lote, quarta triplo) custa cerca de 2,4 bps por noite. **Líquido: +0,04 bps, ou seja, zero.** No futuro GC=F, que não cobra swap, o efeito é mais fraco (+2,2 bps, t=1,05).
- **Redes neurais H1** (direção das próximas 4h, 21 features, walk-forward semestral 2023–2026): AUC de 0,497 (LSTM), 0,500 (logística) e 0,509 (MLP). Depois do spread, todas perdem de 4% a 9,5% ao ano.

## 4) Nasdaq intradiário

- **Momentum intradiário** (Gao, Han, Li e Zhou, 2018: a 1ª meia hora prevê a última) no QQQ 1h, 2024–2026: beta -0,003, t=-0,29. **Não existe mais.** A estratégia perde 2,5 bps por dia depois dos custos.
- **Pregão noturno:** de 2001 a 2020, quase todo o retorno do QQQ veio da noite (+3,95 bps/dia, t=3,2; pregão -0,33 bps). Em 2021+ o efeito enfraquece (t=1,6). Ficar só com a noite rende menos que comprar e segurar.
- **Virada de mês:** sem efeito (t=0,8 e -0,3).

## O que fazer com isso

1. **Produto:** manter o foco em risco, sem previsão. Isso já está em `docs/PLANO.md`. Para o ouro, vale mostrar a sensibilidade ao juro real e ao dólar como explicação do dia, não como sinal.
2. **Acompanhar em tempo real** (registro de sinais): cobre 5d → NQ e VIX/VIX3M → NQ. O critério continua o mesmo.
3. **Reabertura do ouro:** só faz sentido em instrumento sem swap (micro futuro MGC) ou numa corretora com swap menor. Antes, medir spread e slippage reais da reabertura em conta demo.
4. **Setups intradiários do ouro** (`output/intraday_setup_validation`, bloqueados em setembro por falta de dados): agora dá para rodá-los no H1 de 7 anos do `XAUUSD.dk`.
5. **Não vale mais a pena** testar arquiteturas maiores de rede neural com os mesmos dados de preço. O problema não é o modelo, é a falta de informação nos dados.

## Fontes consultadas

- Aye, Gupta, Hammoudeh e Kim (2015), previsão de retornos do ouro com média dinâmica de modelos: preditores funcionam "em algum momento", não de forma consistente. https://repository.up.ac.za/bitstream/2263/45456/3/Aye_Forecasting_2015.pdf
- Pierdzioch e Rohloff, juro real e volatilidade do ouro (volatilidade, não direção). https://ideas.repec.org/a/wsi/afexxx/v18y2023i01ns2010495222410019.html
- Gao, Han, Li e Zhou (2018), "Market intraday momentum", JFE. https://econpapers.repec.org/RePEc:eee:jfinec:v:129:y:2018:i:2:p:394-414 ; replicação mais fraca no QQQ: https://cxoadvisory.com/calendar-effects/first-and-last-half-hours-of-trading-linked ; QuantConnect: https://www.quantconnect.com/research/15348/intraday-etf-momentum/p1
- Estudos de LSTM no ouro com acerto de ~50,7% (regressão linear com 53%): https://www.shs-conferences.org/10.1051/shsconf/202418102005 , https://publikasi.dinus.ac.id/jais/article/view/10305
- Fórum MQL5 sobre backtest de ouro com profit factor alto em período de alta forte: https://www.mql5.com/en/forum/509738
