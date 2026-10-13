# Gold Fakeout — EX5 ORIGINAL: teste fora da amostra 2019–2026

**Veredito pré-registrado: ARCHIVE.** O indicador original (Purchased GOLD
Fakeout CRAZY v4, defaults) não tem vantagem no ouro spot em 7 anos, com nenhuma
das regras de saída testadas. Nenhuma ordem; Algotrading não foi habilitado.

## Desenho

`configs/preregistration/gold_fakeout_ex5_oos_dukascopy.json` (SHA256 no LOCK,
gravado antes de qualquer execução; emenda do relógio com horário de verão feita
antes dos passos B/C). Três passos com critério fixo:

| Passo | Pergunta | Resultado |
|---|---|---|
| A | EX5 em "1 minuto OHLC" gera os mesmos sinais que em ticks reais? | **96/96** idênticos; maior diferença de stop/alvo US$ 0,12 |
| B | EX5 no símbolo personalizado Dukascopy reproduz o EX5 na HonorPro? | **93/96** (recall 97%, precisão 98%; mínimo 80%) |
| C | Vantagem em mar/2019–mar/2026? | **Não** (abaixo) |

Infraestrutura: `mql5/Scripts/Research/ImportCustomRates.mq5` cria `XAUUSD.dk`
(2.684.810 barras M1 bid Dukascopy, relógio de servidor UTC+3 no DST dos EUA e
UTC+2 fora), `scripts/build_custom_symbol_csv.py`, configs `configs/mt5/pilot41dk*`,
captura com `VendorSignalAudit` (Model=1, CalculateEveryTick), 8 execuções anuais
sem snapshot truncado (capturas em `D:\OneB\research\ex5_dukascopy`, 4,4 GB),
análise `scripts/run_ex5_oos.py`.

## Resultado (custos conservadores, saída pré-registrada de 4 h)

15.110 entradas do EX5; 14.194 no período de teste; 9.377 ignoradas por posição
aberta (uma por vez); 4.280 trades completos.

| Métrica | Valor |
|---|---|
| Expectância líquida | **−0,020R**, IC 95% **−0,035 a −0,005** |
| Acerto | 47,4% |
| Fator de lucro | 0,88 |
| Janela recente abr/2025–mar/2026 | −0,056R (IC −0,118 a +0,007) |
| Entrada aleatória (mesmas horas, mesma geometria) | p50 −0,033R · p95 −0,019R |
| Percentil vs. aleatório | 93,5 (não supera o p95) |

Nenhum ano com expectância positiva significativa (2019 −0,033; 2020 0,000;
2021 −0,044; 2022 −0,006; 2023 −0,015; 2024 −0,012; 2025 −0,039; 2026 −0,006).

## Sensibilidade (descritiva; não muda o veredito)

80% dos trades saíram pelo prazo de 4 h, que é premissa do projeto, não do
vendedor: o stop mediano do EX5 é US$ 20 e o alvo mediano US$ 14,7 (alvo menor
que o stop). E a regra de lacuna (60 min) descartava trades que cruzavam a pausa
diária de 60 min do ouro. Testamos as alternativas:

| Saída | Trades | Expectância | IC 95% | Recente |
|---|---:|---:|---|---:|
| 4 h (pré-registrado) | 4.280 | −0,020R | −0,035 a −0,005 | −0,056R |
| 4 h, tolera pausa diária | 4.640 | −0,023R | −0,037 a −0,009 | −0,064R |
| 24 h | 1.880 | −0,017R | −0,052 a +0,018 | −0,075R |
| 72 h | 1.354 | −0,009R | −0,058 a +0,041 | −0,064R |
| Até stop/alvo (10 dias) | 869 | +0,006R | −0,056 a +0,070 | −0,047R |

Com prazos longos o acerto sobe para ~60%, mas é exatamente o necessário para
empatar com alvo menor que o stop. Em todos os cenários a vantagem é zero ou
negativa, e a janela recente é negativa em todos.

## Conclusão sobre o Gold Fakeout

A reimplementação aberta (−0,12R) e o EX5 original (−0,02R) foram reprovados
fora da amostra, com dados validados contra a corretora. Os rótulos GAIN/LOSS
desenhados pelo indicador não correspondem a vantagem executável.

## Limitações registradas

- Relógio de inverno (UTC+2) é premissa; só o verão foi medido na HonorPro.
- Trades atravessando o fim de semana são censurados (sem PnL inventado).
- Ticks gerados de M1 (validado no passo A apenas em duas semanas de 2026).
- Custos de comissão da conta continuam hipotéticos (0,10/onça).

## Achado de engenharia

O simulador usa lacuna máxima de 60 min; em ativos com pausa diária de 60 min
(ouro), isso censura trades que cruzam a pausa. Para setups que operam no fim
do pregão, usar 120 min (mantém a censura de fins de semana).
