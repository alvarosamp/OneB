# Resultados quantitativos dos indicadores adquiridos

## Conclusão executiva

Nenhum dos sete produtos está aprovado para paper trading nesta rodada. O melhor
resultado nominal foi a reprodução do 13X no NQ M15, mas não sobreviveu à correção
dos 47 testes de instrumento/timeframe (p unilateral 0,0186; q de
Benjamini–Hochberg 0,876). Gold Fakeout perdeu em todos os tempos, inclusive no
M10 prescrito. Duck perdeu no M5 de NQ e XAUUSD. London Box teve resultado
nominalmente positivo apenas no H1 e somente no período recente. A regra pública
do Gap Drive, aproximada sem o cálculo proprietário de bid/ask, perdeu no M1.

Essas conclusões se aplicam às regras reproduzíveis extraídas dos vídeos, não a
uma certificação integral dos `.ex5`: os binários são fechados e alguns filtros,
setas e níveis permanecem ocultos.

## Dados e execução

- NQ: série contínua M1 de terceiro, 26/12/2022–12/12/2025, 1.048.575 barras;
  a regra de rolagem não é documentada e não há bid/ask.
- XAUUSD: M5 de terceiro, 04/01/2021–30/01/2026, 351.040 barras; não é GC.
- HonorPro: XAUUSD.s recente usado para calibrar custo. Spread observado mediano
  de 26 pontos (US$0,26); custo modelado de US$0,28 por round trip de 0,01 lote.
  O XAUUSD24_7.s teve spread mediano de 126 pontos e foi excluído do teste.
- NQ: US$20 por ponto e US$15 de custo total modelado por contrato/round trip.
- Sinal no fechamento, entrada somente na abertura seguinte, stop primeiro em
  barras que tocam stop e alvo, uma posição por vez e saída temporal.
- Seleção: 60% desenvolvimento, 20% validação, 20% holdout cronológico intocado.

## Ranking fora da amostra

| Classificação | Reprodução | Instrumento/tempo | Trades | Expectancy | PF | Sharpe | Evidência |
|---|---|---:|---:|---:|---:|---:|---|
| Experimental | 13X | NQ M15 | 164 | US$172,19 | 1,499 | 2,880 | p=0,0186, mas q=0,876; 2023 negativo |
| Experimental | 13X | NQ M10 | 252 | US$62,79 | 1,191 | 1,662 | não significativo; M1/M5 negativos |
| Experimental | 100 Pips | NQ M5 | 99 | US$20,23 | 1,134 | 1,108 | p=0,307; 2024 negativo |
| Precisa de mais dados | London Box | XAUUSD H1 | 158* | US$0,59 | 1,107 | 0,485 | seleção no H1; q=0,705; desenvolvimento negativo |
| Rejeitado | Gold Fakeout | XAUUSD M10 | 186 | −US$0,72 | 0,431 | −8,651 | perde em M5/M10/M15/M30/H1 |
| Rejeitado | Duck | NQ M5 | 820 | −US$13,49 | 0,923 | −1,131 | perde em todos os tempos avaliáveis |
| Precisa de bid/ask | Gap Drive | NQ M1 | 331* | −US$27,79 | 0,748 | −2,508 | proxy OHLC; fórmula proprietária não observada |
| Precisa de dados | Caixa Americana | WIN M2 | — | — | — | — | HonorPro não oferece WIN e não há histórico M2 |

`*` Resultado da seleção refeita diretamente no timeframe prescrito. Valores de
NQ e XAUUSD não são comparáveis em dólares por terem unidades contratuais distintas.

## Estabilidade temporal

### 13X — NQ M15

| Ano | Trades | Líquido | Expectancy | PF | Sharpe |
|---:|---:|---:|---:|---:|---:|
| 2023 | 305 | −US$9.766,92 | −US$32,02 | 0,889 | −1,018 |
| 2024 | 294 | US$22.177,45 | US$75,43 | 1,233 | 1,778 |
| 2025 | 262 | US$34.821,56 | US$132,91 | 1,305 | 1,817 |

O agrupamento positivo M10/M15/M30/H1 é interessante, mas a inversão entre 2023
e 2024–2025 indica dependência de regime. Como o timeframe foi visto entre várias
alternativas e q=0,876, o candidato permanece experimental.

### 100 Pips — NQ M5

2023 foi positivo (PF 1,185), 2024 negativo (PF 0,912) e 2025 positivo
(PF 1,337). No XAUUSD, os mesmos parâmetros produziram pequenas vantagens em M5
e M15, mas sem significância; M10 e H1 foram negativos. Não há portabilidade ou
estabilidade suficiente.

### London Box — XAUUSD H1

2021, 2022 e 2023 perderam; 2024 ficou próximo de zero; apenas 2025 ficou
positivo (PF 1,144). A seleção específica H1 produziu PF 1,107 no holdout, mas
o desenvolvimento foi negativo e q=0,705. A aparente melhora recente deve ser
tratada como hipótese de regime, não como edge estabelecido.

## Interpretação por produto

### Gold Fakeout CRAZY v4

Os parâmetros expostos são EMA100, Bollinger(20,2), SL 200 pontos, TP 150 pontos
e time-stop de quatro horas. A relação bruta é 0,75R. A melhor variante selecionada
usou tolerância de 0,05 ATR e a janela do vídeo, mas perdeu em desenvolvimento e
holdout. A variante 24/7 é especialmente frágil a spread e deve ser rejeitada na
HonorPro.

### 13X

A regra pública EMA13 + cruzamento DMI/ADX não funciona em NQ M1/M5 nem em nenhum
tempo do XAUUSD. O bloco M10–H1 de NQ merece somente uma replicação confirmatória
com contratos individuais e os filtros exatos do `.ex5`. Não selecionar novamente
parâmetros no holdout já observado.

### 100 Pips por Dia

MA5/MA10 + RSI(14) cruzando 50 + ADX e separação produziu sinal fraco no NQ M5,
mas não em tempos vizinhos. O nome “100 pips” não deve ser interpretado como alvo
ou expectativa comprovada.

### London Box

O H1 é materialmente melhor que tempos menores, consistente com a instrução do
vídeo, porém a vantagem aparece só no fim da amostra. Precisa de definição exata
da caixa, timezone e tratamento de DST antes de novo teste confirmatório.

### Nasdaq Gap Drive

O vídeo informa M1, uma decisão diária e uso de bid/ask bias, mas não revela a
fórmula. O proxy com direção do primeiro minuto/gap foi negativo no M1. O produto
exato continua não identificado até obter buffers/setas do `.ex5` e histórico
US100.s com ticks bid/ask.

### Duck Duck Duck

O alinhamento SMA60 em H4/H1 e entrada M5 foi testado usando somente candles H1/H4
já concluídos. A versão objetiva perdeu. Como o vídeo declara que a entrada e a
gestão têm subjetividade de price action, o produto não é automatizável de forma
reproduzível sem regras adicionais.

### Caixa Americana

Não é válido usar NQ como substituto do WIN. O indicador permanece “precisa de
mais dados” até existir WIN M2 com custos e sessões da B3.

## Próxima rodada confirmatória

1. Capturar buffers e objetos dos `.ex5` para fechar regras ocultas e testar repaint.
2. Coletar US100.s M1 com ticks/bid/ask HonorPro por pelo menos 250 sessões.
3. Obter contratos individuais NQ e GC com rolagem explícita; não otimizar no
   holdout já utilizado.
4. Pré-registrar apenas: 13X NQ M15, London Box XAU H1 e 100 Pips NQ M5.
5. Executar novo walk-forward e um holdout futuro; somente então considerar paper trading.

## Artefatos reproduzíveis

- `scripts/vendor_strategy_backtest.py`
- `scripts/vendor_timeframe_sensitivity.py`
- `scripts/collect_vendor_indicator_transcripts.py`
- `tests/test_vendor_strategy_backtest.py`
- `output/vendor_indicator_research/backtest_v1/`
- `output/vendor_indicator_research/prescribed_timeframes_v1/`
- `output/vendor_indicator_research/timeframes_v2/`

Os vídeos fornecidos são as fontes primárias das regras e estão relacionados em
`docs/research/vendor_indicators_assessment.md`.
