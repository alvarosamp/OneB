# 100 Pips (EX5) — teste fora da amostra no Dukascopy, 2019–2026

Pré-registro: `pips100_ex5_oos_dukascopy` (LOCK). Relatório: `output/setup_research/pips100_ex5_oos_dukascopy_20261007.json`.
Capturas: `D:\OneB\research\ex5_dukascopy\pilot45*` (MT5 Strategy Tester, XAUUSD.dk, H1, 0 snapshots truncados).

## Veredito: DESCRIPTIVE_ONLY (sem evidência de vantagem; não recomendar)

O passo B reprovou, então os números abaixo **não** valem como prova sobre o EX5 na HonorPro.
Eles só descrevem o comportamento do indicador no feed Dukascopy.
Mesmo nesse papel descritivo, nenhuma hipótese mostra vantagem.

| Passo | Resultado |
|---|---|
| A — M1 OHLC × ticks reais (HonorPro) | 20/20, aprovado |
| B — XAUUSD.dk × HonorPro (mai/2026) | recall 0,45, precisão 0,375, **reprovado** (critério ≥ 0,8) |

O diagnóstico do passo B (relatado antes) mostrou que 18 dos 20 sinais coincidem em horário e lado.
O que falha são os níveis de entrada, stop e alvo, que diferem em mais de US$0,50, e há 6 sinais extras.
O indicador é sensível ao feed; o mesmo EX5 em dados de outro broker desenha níveis diferentes.

## Resultado descritivo (custos: spread real/piso HonorPro por hora, slippage US$0,05/lado, comissão US$0,10)

| Hipótese | Trades | Expectativa | IC (Bonferroni) | Acerto | PF | Últimos 12 meses |
|---|---|---|---|---|---|---|
| H1 primária (TP1) | 251 | −0,008R | [−0,143; +0,124] | 51,4% | 0,98 | +0,11R (32 trades) |
| H2 secundária (TP2) | 200 | −0,104R | [−0,309; +0,115] | 31,0% | 0,85 | +0,09R (27 trades) |

Por ano (H1): 2019 +0,10 · 2020 +0,06 · 2021 −0,07 · 2022 −0,13 · 2023 −0,16 · 2024 −0,00 · 2025 +0,26 · 2026 −0,01R. Nenhum ano tem IC acima de zero.

## Leitura

- **Acerto de 51% com expectativa zero.** O indicador "acerta" metade das vezes no TP1, mas o ganho médio não cobre a perda média depois dos custos. É o mesmo padrão que vimos na Vortex: taxa de acerto alta não é lucro.
- **2025 positivo é ruído.** O IC de 2025 contém zero, e 2026 volta a ficar perto de zero. Não há regime recente confiável.
- **Censura alta:** 60 (H1) e 91 (H2) trades foram censurados por lacunas de dados acima de 120 min (o relatório não guarda os trades individuais, então a causa exata de cada censura não foi auditada). Eles não entram na média; o viés pode ir para os dois lados e não muda a conclusão.

## Decisão

100 Pips fica **arquivado** como fonte de recomendação. Não vou reotimizar parâmetros, porque isso seria procurar um resultado bom depois de ver os dados.
