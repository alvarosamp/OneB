# Gold Fakeout (reimplementação aberta v1): teste fora da amostra 2019–2026

**Veredito pré-registrado: ARCHIVE.** A regra não tem vantagem no ouro spot,
nem antes nem depois de custos. Não reotimizar a v1. Nenhuma ordem enviada.

## Desenho (registrado antes do download)

`configs/preregistration/gold_fakeout_open_v1_oos_dukascopy.json` (SHA256 no
LOCK; emenda de recência também feita antes do download). Regra idêntica à v1
(`1234df77…`); único ajuste de adaptação: feed em UTC (janela 07–11 BRT = 10–14 UTC).

## Dados e confiabilidade

- Dukascopy XAUUSD M5, bid e ask separados, 01/03/2019 a 25/09/2026:
  535.197 barras, bid/ask casados em 99,6%.
- Auditoria dia a dia de 186 blocos: zero blocos incompletos. O downloader agora
  rejeita bloco com buraco interno (o `dukascopy-node` grava arquivo parcial em
  HTTP 429 sem avisar) e só aceita lacuna da fonte com prova de um dia isolado.
- Lacunas da fonte (ask vazio na própria Dukascopy): 7 dias úteis, 0,35%
  (limite de suspeita: 1%), listadas em `source_gaps.json` e no relatório.
- **Validação contra a HonorPro** (abr–set/2026, critérios fixados antes):
  correlação de retornos 5 min 0,965 (≥0,95); diferença mediana de preço
  US$ 0,21 (≤1,00); 81 de 84 sinais da HonorPro reproduzidos (96%, ≥60%). PASSOU.
- Bônus: o fuso do servidor HonorPro foi **medido**: UTC+3 (correlação 0,965
  contra <0,09 em qualquer outro offset) no período abr–set/2026.

## Resultado (período de teste mar/2019–mar/2026, nunca usado com esta regra)

| Métrica | Valor |
|---|---|
| Trades completos | 1.141 |
| Expectância líquida (custo pré-registrado) | **−0,116R**, IC 95% **−0,177 a −0,056** |
| Acerto | 38,5% com alvo 1,5R |
| Fator de lucro | 0,79 |
| Janela recente abr/2025–mar/2026 | −0,006R (IC −0,18 a +0,17), 149 trades |
| Entrada aleatória (mesma janela, stops e custos) | p50 −0,167R · p95 −0,115R |
| Percentil do setup vs. aleatório | 94,5 (não supera o p95) |
| Rompimento simples | −0,231R |

Por ano: nenhum ano com expectância positiva significativa; 2024 −0,14R,
2025 −0,01R, 2026 (parcial) −0,21R. A volatilidade relativa (ATR M5 em % do
preço) subiu de ~0,07% para ~0,18% em 2026: o mercado de hoje é outro, e a
regra continua sem vantagem nele.

### Sensibilidade ao custo (descritiva, não muda o veredito)

| Custo | Expectância | IC 95% |
|---|---:|---|
| Pré-registrado (maior spread Dukascopy/HonorPro + 0,05 + 0,10) | −0,116R | −0,18 a −0,06 |
| Spread HonorPro + slippage + comissão | −0,090R | −0,15 a −0,03 |
| Spread HonorPro, sem extras | −0,049R | −0,11 a +0,01 |
| **Custo zero** | **+0,008R** | **−0,06 a +0,07** |

Mesmo sem custo algum, o sinal é estatisticamente zero. O problema não é o
custo da corretora: a regra não prevê nada. As confirmações filtram algo em
relação ao rompimento simples e às entradas aleatórias, mas longe de pagar os custos.

## O que isso NÃO diz

É a reimplementação aberta feita a partir da descrição. O **EX5 original**
pode ter lógica diferente (os objetos capturados não são reproduzíveis em
Python). Ele não foi testado aqui.

## Próximo teste com o mesmo rigor

Importar estes dados Dukascopy como símbolo personalizado no MT5 e rodar o
EX5 original no Strategy Tester (2019–2026), capturando os objetos como já é
feito no VendorSignalAudit. Pré-registrar antes, com os mesmos critérios.

Reprodução:

```powershell
python scripts/download_dukascopy_intraday.py --instrument XAUUSD --timeframe m5 --start 2019-03-01 --end 2026-09-26 --output-root D:/OneB/market-data/dukascopy-xau-2019-2026
python scripts/run_oos_dukascopy.py --dukascopy D:/OneB/market-data/dukascopy-xau-2019-2026/normalized/XAUUSD_M5_2019-03-01_2026-09-26.csv.gz
```
