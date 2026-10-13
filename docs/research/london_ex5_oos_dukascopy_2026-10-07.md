# Caixa de Londres (EX5) — teste fora da amostra no Dukascopy, 2019–2026

Pré-registro: `london_ex5_oos_dukascopy` (LOCK). Relatório: `output/setup_research/london_ex5_oos_dukascopy_20261007.json`.
Capturas: `D:\OneB\research\ex5_dukascopy\pilot46*` (MT5 Strategy Tester, XAUUSD.dk, H1, 10 execuções, 0 snapshots truncados).

## Veredito: DESCRIPTIVE_ONLY — e, descritivamente, **perde dinheiro de forma consistente**

| Passo | Resultado |
|---|---|
| A — M1 OHLC × ticks reais (HonorPro) | 106/106, aprovado |
| B — XAUUSD.dk × HonorPro | recall 0,60, precisão 0,58, **reprovado** (critério ≥ 0,8) |

Diagnóstico do passo B (feito antes de ver o passo C):
- 102 dos 106 sinais de referência aparecem no Dukascopy com o mesmo lado e no mesmo horário (±70 min).
- O que diverge são os níveis. A diferença máxima entre entrada, stop, TP1 e TP2 tem mediana de US$0,43 e p90 de US$0,84.
- Com a tolerância pré-registrada de US$0,50, só 64 sinais casam. Com US$1,00, seriam 96.
- A causa provável é a diferença de preço entre os feeds. A tolerância **não** foi afrouxada depois do fato.

Por isso os números abaixo não provam nada sobre o EX5 na HonorPro. Ainda assim, com mais de 1.100 trades e a direção e o horário quase idênticos, eles mostram o que o indicador faz.

## Resultado descritivo (custos: spread real/piso HonorPro por hora, slippage US$0,05/lado, comissão US$0,10)

| Hipótese | Trades | Expectativa | IC (Bonferroni, 3 hipóteses) | Acerto | PF | Total | Últimos 12 meses |
|---|---|---|---|---|---|---|---|
| H1 primária (TP1) | 1.164 | **−0,068R** | **[−0,129; −0,010]** | 54,9% | 0,85 | −79,5R | −0,01R (150) |
| H2 secundária (TP2) | 833 | **−0,106R** | **[−0,199; −0,009]** | 37,5% | 0,83 | −88,2R | −0,12R (102) |
| H3 só "Forte" (TP1) | 707 | −0,050R | [−0,125; +0,024] | 57,7% | 0,88 | −35,3R | +0,03R (97) |

Por ano (H1): 2019 −0,12 · 2020 −0,08 · 2021 −0,03 · 2022 −0,01 · 2023 −0,12 · 2024 −0,12 · 2025 −0,01 · 2026 −0,03R. **Todos os 8 anos são negativos.**

## Leitura

- **É o resultado mais claro até agora.** H1 e H2 têm o IC inteiro abaixo de zero, mesmo com a correção de Bonferroni. Não é "falta de amostra"; o indicador perde.
- **A taxa de acerto engana.** No TP1 ele acerta 55% e mesmo assim perde 80R em 7 anos, porque o ganho médio líquido é só ~70% da perda média (PF 0,85 com 55% de acerto implica ganho/perda ≈ 0,70). É exatamente o tipo de número ("55% de acerto") que vira propaganda.
- **O filtro "Forte" não salva.** Ele melhora um pouco, mas continua negativo, e 2025 positivo está dentro do ruído (IC −0,12 a +0,20).
- **Censura:** 99 (H1), 170 (H2) e 62 (H3) trades censurados por lacunas acima de 120 min. Eles não entram na média.

## Decisão

Caixa de Londres **arquivada**. Não reotimizar. Dos indicadores comprados testados até aqui (Gold Fakeout, 13X, 100 Pips e Caixa de Londres), nenhum mostrou vantagem depois dos custos.
