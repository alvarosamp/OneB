# Primeiro piloto econômico do original Gold M10

Classificação: experimental / precisa de mais dados. Não aprovado para paper trading.

## Implementado e executado

O simulador scripts/backtest_original_gold_ticks.py usa os objetos do EX5
original recapturados com cálculo a cada tick. Não usa a reprodução Python
aproximada da estratégia. Objetos históricos da fotografia inicial são excluídos.
Entrada somente na primeira quote após first_seen mais latência hipotética:
compra ask, venda bid. Stop/target absolutos são congelados na primeira fotografia,
sem recalcular níveis usando observações futuras. Não usa textos GAIN/LOSS.
Uma posição por vez é hipótese operacional, não regra certificada do fornecedor.
Saída no bid para long e ask para short, pelo primeiro stop/target observado ou
após quatro horas da execução. Slippage adverso por lado. Stops atravessados são
executados no preço observado, não artificialmente no nível. Latência configurada
refere-se à entrada; não reproduz latência dinâmica de execução de saídas.

Coleta read-only: 326.730 ticks em 04/05/2026 e 250.233 em 05/05/2026,
todos com quotes válidas. O segundo dia suporta saídas, não acrescenta sinais:
captura de sinais cobre apenas 04/05. Horários permanecem no domínio bruto comum
MT5, sem alegar conversão histórica de sessão. Manifest/hashes em
D:/OneB/market-data/mt5/gold-economic-20260927/coverage.json.
Quote ausente na entrada >5s ou lacuna >60s durante posição causa exclusão/censura,
nunca ganho presumido. Descarta duplicatas exatas de janelas adjacentes apenas.

## Resultados descritivos, sem inferência de vantagem

11 sinais novos; 4 trades concluídos; 7 excluídos por posição já aberta.
Os nove cenários são sensibilidade predefinida, não seleção do melhor resultado.
Custos além do spread são hipóteses, não tabela certificada da conta.

| Latência de entrada | Slippage/lado + comissão ida/volta por onça | Saldo por onça | PF | Drawdown de trades fechados/onça |
|---|---|---:|---:|---:|
| 250 ms | 0 + 0 | 14,55 | 1,685 | 21,24 |
| 250 ms | 0,05 + 0,10 | 13,75 | 1,641 | 21,44 |
| 250 ms | 0,15 + 0,30 | 12,15 | 1,556 | 21,84 |

Também executadas latências 0 e 1.000 ms. Resultado integral com cada operação,
exclusões, parâmetros e hashes: output/vendor_indicator_research/gold_economic_pilot_20260927.json.
Unidade é USD por onça para exposição fixa, não retorno percentual de uma conta.
Drawdown acima não mede perda intratrade; Sharpe e Sortino ficam nulos deliberadamente.
Três trades vencedores em quatro são insuficientes para inference estatística.
Não é período final fora da amostra: este dia já foi usado em diagnóstico técnico.
Não houve otimização, comparação econômica com baselines ou ML nesta etapa.

## 13X: levantamento executado, sem inventar semântica

scripts/profile_vendor_buffers.py encontrou 1.381 fotografias M5 de barra anterior.
Buffer 0 é série contínua em escala de preço; buffer 1 contém 0/1; buffers 2/3
têm 13/7 valores não zero; buffers 4/5 têm 97/96 valores não zero. Estes formatos
não provam quais são compra, venda, setas ou X de saída. Evidência em
output/vendor_indicator_research/13x_buffer_profile_20260927.json.
Não atribuir direção pelo lucro obtido: isso seria escolha retrospectiva.
Próxima verificação: confrontar timestamps/valores com plots e Janela de Dados
do original; documentar o mapeamento antes de qualquer backtest 13X.

## Repetição

```powershell
python scripts/backtest_original_gold_ticks.py --objects output/vendor_indicator_research/pilot27cert/pilot27cert_gold_M10_0_XAUUSD.s_PERIOD_M10_objects.csv --ticks D:/OneB/market-data/mt5/gold-economic-20260927/XAUUSD.s_ticks_2026-05-04_00h_24hours.csv.gz D:/OneB/market-data/mt5/gold-economic-20260927/XAUUSD.s_ticks_2026-05-05_00h_24hours.csv.gz --output output/vendor_indicator_research/gold_economic_pilot_20260927.json
python -m pytest tests/test_original_gold_ticks.py -q
```

Dois testes automatizados passaram: entrada ask após latência/stop com gap e
censura de lacuna sem declarar lucro. Próxima etapa é ampliar captura sequencial
e ticks pareados para muitos dias, incluir controles simples com a mesma execução,
medir risco intratrade, fixar custos e separar treino/validação/teste intocado.
Nenhum ranking ou filtro IA deve ser aprovado com esta amostra de quatro trades.
