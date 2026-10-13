# Simulação por timeframe, horário e família

## Resultado desta execução

55 combinações concluídas, 110 comparações com/sem filtro, três folds por caso.
Nenhum candidato passou o filtro conservador de desenvolvimento. Não existe
algoritmo com confiança estatística demonstrada por esta execução.
Arquivos completos em output/vendor_indicator_research/walkforward_hours_v1:
results.json (trades e folds), development_summary.csv (custos/resultados/censura),
hours_descriptive.csv (horários NY), sides_descriptive.csv (compra/venda), summary.md.

Pista exploratória: hipótese 13X NAS100 M30 sem filtro, 93 trades completos,
saldo271,66 unidades de preço, três folds positivos, porém sete trades censurados
e q=1 após múltiplas comparações. Não passou tamanho mínimo nem evidência estatística.
Duck M5 Nasdaq com filtro: 73 trades completos e saldo367,76 unidades, apenas dois
folds positivos, uma censura, q=1. Também não aprovado. São hipóteses, não EX5.
No ouro, nenhuma combinação sem filtro teve saldo positivo agregado nos folds.
Filtros frequentemente recusaram todos os horários: zero trades não é sucesso.

Não houve avaliação econômica dos 20% finais por este script. Não abrir esse
período repetidamente para escolher modelo. Primeiro corrigir custos/dados,
mapear originais e congelar uma hipótese justificável em registro de experimento.
Duck H1 e Gap H1 sem operações nesta implementação não provam falta de vantagem:
Duck foi concebido para M5 e abertura09:30 não é alinhada às barras H1 inteiras.

## Objetivo e limites

Buscar uma vantagem pequena que se mantenha em períodos posteriores, não um
indicador com aparência convincente. Nenhum teste deste documento envia ordens.
São duas linhas separadas: Gold EX5 original em ticks e hipóteses aproximadas
das famílias em histórico longo. Uma não comprova a outra.

## Linha A: Gold original, ticks da corretora

Mesmo dia 04/05/2026, quotes de 04–05/05, parâmetros originais e captura causal.
Hipótese de uma posição por vez, execução bid/ask, latência de entrada 250 ms,
slippage 0,05/lado e comissão ida/volta 0,10 por onça:

| Timeframe | Trades | Saldo USD/onça | PF |
|---|---:|---:|---:|
| M5 | 5 | 74,30 | não definido: sem perdas |
| M10 | 4 | 13,75 | 1,64 |
| M15 | 2 | -9,49 | 0,61 |
| H1 | 2 | 16,03 | não definido: sem perdas |

Não comparar como ranking: sinais se sobrepõem, há somente um dia e poucas
operações. M10 é o recomendado pelo fornecedor. Nenhuma aprovação, nem escolha
de M5 porque parece vencedor. No custo usado, PF sem perdas NÃO é infinito
defensável ou evidência de risco zero. Não foram conferidos visual/oculto em
todos os TF, apenas M10. Drawdown de trades fechados não é risco intratrade.
Dados detalhados em output/vendor_indicator_research/gold_economic_*20260927.json.

## Linha B: hipóteses em dados longos

Script: scripts/walkforward_execution_research.py.
TF: M5/M10/M15/M30/H1, rejeitando candles de TF superior incompletos.
Portable: 13X, 100 Pips, Duck; Gold/London somente ouro; Gap OHLC somente Nasdaq.
Baseline adicional: direção do fechamento versus EMA13.
Caixa Americana pendente de WIN/B3; não substituir por Nasdaq/ouro.
13X/100 Pips/Duck originais pendentes de mapeamento certificado das entradas/saídas;
Gap original pendente de configuração de sessão; não chamar os proxies de EX5.

NASDAQ: Dukascopy CFD 2023–início 2024, bid/ask pareados, não NQ.
Ouro: histórico M5 disponível 2021–2026, sem bid/ask; hipótese explícita de
que OHLC é bid e ask=bid+0,30. Isso NÃO certifica custos históricos do ouro.
Não fundir XAUUSD24_7.s com XAUUSD.s.

Parâmetros congelados: 13X ADX20 com EMA13/DMI14 aproximado; 100 Pips EMA5/10,
RSI10 sobre HL/2, cruzamentos contemporâneos, ADX20; Duck SMA60 com H1/H4
concluídos; Gold toque EMA100/BB20, stop20/alvo15 em preço, não a antiga réplica
stop2/alvo1,5; London caixa NY00–03 e janela posterior4h; Gap primeira barra
NY09:30. Filtros proprietários e Londres/DST não são reproduzidos exatamente.
Risco ATR14, alvo1,5R e hold4h nos demais. Nada disso foi otimizado nesta execução.

Entrada na abertura imediatamente seguinte ao candle concluído, long ask / short
bid; stops em gaps usam preço adverso e, se stop/alvo na mesma barra, stop primeiro.
Slippage/comissão: Nasdaq0,25/lado+0,50 ida/volta por unidade; ouro0,05+0,10.
São hipóteses em unidade de preço, não custos reais da conta ou capital investido.
Sem swaps e sem latência dinâmica intrabar. Lacunas censuram posições: inspecionar
quantidade censurada, não interpretar o PnL restante como amostra completa.

## Separação temporal e horários

50% inicial: desenvolvimento. Três folds expansivos: validar 50–60%, 60–70%,
70–80%. Os 20% finais NÃO recebem avaliação econômica neste script.
Esse embargo é local a este experimento: não certifica que outros estudos do
projeto jamais examinaram essas datas. Uma prova final realmente nova exige
novos períodos prospectivos ou dados não usados anteriormente.

Bins NY: 00–04,04–08,08–12,12–16,16–20,20–24. Somente o treino anterior a cada
fold escolhe bins, com pelo menos30 trades e expectancy positiva no treino.
Depois simula novamente o filtro no período posterior, em vez de apagar perdas
de um backtest já pronto. Também grava resultados descritivos por horário sem
escolher o melhor horário de validação. Long e short constam nos trades JSON.

Resumo: scripts/summarize_walkforward_execution.py. Bootstrap diário em blocos
de5 dias/1.000 réplicas, incluindo dias úteis sem trades; BH entre comparações.
Critério conservador exploratório: >=100 trades, zero censura, três folds
positivos, limite inferior da média diária >0 e q<0,05. Não cobre todo o histórico
de testes do projeto, nem garante controle sob qualquer dependência entre modelos.
Não promove automaticamente candidato para paper trading.

## Repetição

```powershell
python scripts/walkforward_execution_research.py --nasdaq D:/OneB/market-data/dukascopy-nas100-2023-2026/normalized/NAS100_M5_2023-01-01_2024-02-11.csv.gz --gold D:/OneB/market-data/research-ready/XAUUSD_M5_2021-01-01_2026-01-31.csv.gz --output output/vendor_indicator_research/walkforward_hours_v1
python scripts/summarize_walkforward_execution.py output/vendor_indicator_research/walkforward_hours_v1
python -m pytest tests/test_walkforward_execution_research.py tests/test_original_gold_ticks.py -q
```

Quatro testes passaram: completude de TF, execução no próximo candle e stop-first,
bid/ask com latência e gap, censura de quotes. Antes de IA probabilística: verificar
dados/custos, incluir risco intratrade e completar mapeamento dos originais. Depois
comparar regressão regularizada contra árvores com as mesmas datas e execução;
calibrar probabilidades em janela posterior e medir Brier, não só acurácia.
