# Indicadores originais: ampliação para uma semana

Classificação: experimental / precisa de mais dados. Nenhum aprovado.

## Executado

Gold EX5 original M10, defaults, 04–09/05/2026, Model4, cálculo por tick,
691 fotografias, 49 entradas novas (49 com defasagem600s), 272 objetos únicos.
Sem revisão dos buffers ou preços dos objetos nesta captura; 47 alterações de
texto não são PnL executável. Captura em output/vendor_indicator_research/pilot28week.
EX5 comprado intacto. Nenhuma ordem, nenhuma habilitação de Algotrading.

Ticks HonorPro XAUUSD.s: 1.518.115 quotes válidas em 04–08/05 (raw, antes de
deduplicação exata), manifest/hashes nas pastas D:/OneB/market-data/mt5/
gold-economic-20260927 e gold-week-20260927. São cinco dias, não250 sessões.
Manter XAUUSD24_7.s separado; foi usado somente na checagem visual do 13X.

## Gold: o resultado positivo de um dia não se manteve

Cenário central: entrada250ms depois de first_seen; spread real, slippage0,05
por lado, comissão ida/volta0,10 por onça, maxhold4h. Custos extras são hipóteses.
Uma posição por vez; preços de stop/target congelados no primeiro aparecimento.
49 sinais: 15 operações completas, 32 recusadas por posição aberta, duas posições
censuradas (lacuna de quotes e fim do período). Não há PnL imputado às censuradas.

| Métrica | Resultado dos trades completos |
|---|---:|
| Saldo USD/onça | -28,10 |
| Expectancy USD/onça | -1,873 |
| Profit factor | 0,735 |
| Trades vencedores | 7/15 |
| Drawdown de trades fechados USD/onça | 66,85 |
| Drawdown marcado a mercado USD/onça | 94,03 |

Drawdown marcado usa bid/ask executável com custos ao longo dos trades completos;
também exclui as posições censuradas. Não representa risco total conhecido da
semana nem drawdown percentual de conta. Slippage de saída é hipótese constante;
sem latência dinâmica de saída ou swaps. Os nove cenários tiveram saldo negativo.
Não é rejeição universal do indicador: rejeita aprovação com esta evidência curta.

Por data de decisão: 04/05 +13,75; 05/05 -10,63; 07/05 -23,77; 08/05 -7,45.
06/05 sem trades completos nesta execução, não dia validado de lucro zero.
Compras:9 trades/+1,12; vendas:6 trades/-29,22. Janela raw12–16 teve só dois
trades positivos. Não transformar isso em filtro depois de ver o resultado.
Horários são domínio bruto MT5, não sessão NY/Londres historicamente certificada.
Arquivo: output/vendor_indicator_research/gold_original_week_20260927.json.

## 13X: saídas confirmadas, entradas ainda provisórias

Controle do computador usado para observar a Janela de Dados no MT5 autenticado:
EMA13, Compra13X, Venda13X, SaídaLong, SaídaShort. Linha colorida normalmente
consome um buffer numérico e um de cor; [documentação MQL5](https://www.mql5.com/en/docs/customind/indicators_examples/draw_color_line).
Isso sustenta hipótese0/1 EMA/cor e2/3 compra/venda, mas não prova o mapa inteiro.

Confirmação numérica direta em XAUUSD24_7.s H1:
25/09/2026 16h: Janela de Dados SaídaLong4291,24 = buffer4.
25/09/2026 19h: SaídaShort4273,13 = buffer5.
Lotes pilot28map e pilot28map2 (80barras de rechecagem) concluídos sem revisões.
As capturas incluem históricos iniciais para mapeamento, NÃO execução retroativa.
Venda visual observada em26/09 23h com valor4278,28, mas não capturada como
barra fechada no lote, portanto não há confirmação numérica completa do buffer3.
Compra/buffer2 tampouco foi confirmada numericamente. Mapeamento de entrada
permanece explicitamente provisório; não afirmar certificação dos sinais.

Simulador scripts/backtest_original_13x_ticks.py usa valores do EX5 da semana
04–08/05, não a réplica DMI. Exclui fotografia histórica inicial e valores zero,
amostra shift1, compra ask/venda bid após250ms; sai no buffer4/5 observado com
mesma latência, ou4h como hipótese de segurança. Sem stop fixo (não documentado).
Uma posição, ignora entradas opostas enquanto aberta; regra não certificada do
fornecedor. Portanto são replays condicionais ao mapa, não performance validada.

| TF | Trades completos | Saldo USD/onça | Limite |
|---|---:|---:|---|
| M5 | 17 | -40,05 | Uma posição censurada; entradas provisórias |
| M15 | 8 | -24,20 | Pouca amostra; entradas provisórias |
| H1 | 2 | +8,39 | Apenas duas compras; não inferir vantagem |

Arquivos: output/vendor_indicator_research/13x_original_provisional_*20260927.json.
Detalhamento por dia, quatro horas raw e direção sem selecionar bins:
output/vendor_indicator_research/original_week_hours_20260927.json.
Quatro testes automatizados dos replays passaram: exclusão de histórico/formação,
quotes bid/ask com latência, saída pós-evento e censura sem ganho presumido.

## Repetição e próxima barreira

Presets configs/mt5/pilot28week_gold_M10.{ini,set} e
pilot28map{,2}_13x_H1.{ini,set}. Runner scripts/run_mt5_vendor_pilots.ps1;
terminal deve ser fechado normalmente antes do lote, presets copiados à pasta
Profiles/Tester. Local apenas, Optimization0, sem ordens. Dados/hash versionados.

```powershell
$weekTicks = @(Get-ChildItem -LiteralPath D:/OneB/market-data/mt5/gold-economic-20260927,D:/OneB/market-data/mt5/gold-week-20260927 -Filter '*.csv.gz' | Select-Object -ExpandProperty FullName)
python scripts/backtest_original_gold_ticks.py --objects output/vendor_indicator_research/pilot28week/pilot28week_gold_M10_0_XAUUSD.s_PERIOD_M10_objects.csv --ticks $weekTicks --output output/vendor_indicator_research/gold_original_week_20260927.json
python scripts/backtest_original_13x_ticks.py --buffers output/vendor_indicator_research/pilot27cert/pilot27cert_13x_M5_2_XAUUSD.s_PERIOD_M5_buffers.csv --ticks $weekTicks --output output/vendor_indicator_research/13x_original_provisional_M5_20260927.json
python -m pytest tests/test_original_gold_ticks.py tests/test_original_13x_ticks.py -q
```

Antes de ampliar ML: confirmar numericamente as duas entradas13X, completar
janela de quotes para saídas censuradas, replicar em meses/regimes distintos,
verificar fuso e custos da conta. Congelar regras e comparar controles com a
mesma execução. A semana já foi examinada e não pode virar teste final intocado.
Não calibrar uma probabilidade de sucesso com15 trades. Não promover H1 por
duas operações positivas, nem janela12–16 por dois exemplos favoráveis.
