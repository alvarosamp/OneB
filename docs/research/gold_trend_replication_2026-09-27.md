# Replicação congelada: a melhora não se confirmou

**Conclusão: rejeitado para aprovação nesta configuração.** Não é prova de que
o indicador nunca funcionará. É falha da hipótese testada, ainda com pouca amostra.
Nenhuma ordem enviada ou Algotrading habilitado. EX5 original intacto.

## Registro antes de consultar o resultado

configs/gold_trend_replication_v1.json fixou a semana11–15/05/2026, Gold M10
original default, hipótese principal tendência M5/M15 concordante, secundária
tendência M5 e baseline sem filtro. Nenhuma otimização. EMAs5/20 M5 e20/50 M15,
inclinação3 barras, só informações de barras concluídas. Warmup é a semana
anterior, com preços passados, nunca reutilizada como novos sinais.
O registro foi salvo antes da captura, coleta e leitura dos resultados da nova
semana neste fluxo. Não afirma que ninguém no projeto jamais examinou essas datas.

Entrada no primeiro tick após first_seen+250ms, long ask/short bid; SL/TP
originais congelados, hold4h, uma posição. Três cenários de custos registrados.
Não foram ajustados horários, stops, targets, filtros ou períodos após o resultado.

## Dados e execução

Nova coleta:1.435.728 ticks, todos com quotes válidas,11–15/05.
Manifest/hashes: D:/OneB/market-data/mt5/gold-replication-20260927/coverage.json.
Com a semana anterior, foram adquiridos2.953.843 ticks de dez dias de ouro.
Isso não chega perto da meta250 sessões, nem certifica custos específicos da conta.

Lote pilot29verify concluído com Model4 e cálculo por tick,691 fotografias,
47 entradas novas,300 objetos únicos. Sem revisões nos buffers rechecados;
objetos mudaram texto47 vezes. Não converter GAIN/LOSS em PnL.
46 sinais observados600s depois do desenho; um602s. Execução nunca retroativa.
O testador solicita ticks reais; log deve permanecer como evidência de fallback.

## Resultado da verificação

Cenário central: slippage0,05/lado e comissão0,10 ida/volta por onça, além
do spread real. Custos adicionais são hipóteses. Saldo USD/onça, não retorno de conta.

| Regra | Sinais permitidos | Trades completos | Saldo | PF | Vencedores |
|---|---:|---:|---:|---:|---:|
| Sem filtro | 47 | 15 | -41,51 | 0,660 | 6/15 |
| M5+M15 concordantes (principal) | 7 | 4 | -64,47 | 0,137 | 1/4 |
| Tendência M5 (secundária) | 11 | 5 | -21,57 | 0,579 | 3/5 |

Sinais restantes foram ignorados porque já havia posição aberta:32,3 e6,
respectivamente. Nenhuma censura nesta semana nos três cenários. As três regras
ficaram negativas em todos os cenários de custo, inclusive sem custos adicionais
(mas com spread real). Filtro principal não replicou o saldo+24,27 de três
trades exploratórios da semana anterior; agora teve quatro trades/-64,47.
Filtro secundário tampouco replicou: quatro/+20,13 antes, cinco/-21,57 agora.
Não foi calculada significância ou Sharpe com essa amostra minúscula.

Drawdown marcado a mercado/onça: principal79,94, secundário44,04, baseline81,17.
Comparação não equivale a exposição/risco de capital igual: filtros negociam
quantidades diferentes de oportunidades. Sem swaps e sem latência dinâmica de saída.

## Diagnóstico: direção correta não basta

No filtro M5, três de cinco operações venceram (60%), mas o ganho médio líquido
foi9,89/onça e a perda média25,62/onça. Logo, acerto60% não demonstra vantagem.
Esses valores são descritivos da amostra, não parâmetros de uma distribuição futura.

No filtro principal, riscos planejados no preço executável foram24,75;27,24;
18,92;27,64 por onça. Recompensas até o alvo foram10,25;7,76;16,08;7,36.
Os níveis desenhados vêm de um horário anterior ao instante em que a entrada
fica disponível: ao comprar/vender no preço realmente executável, a relação
alvo/risco pode ser muito diferente do15/20 nominal. Não reancorar níveis
retroativamente para fazer a simulação parecer melhor.

O saldo principal concentrou perdas em14/05: três trades/-74,73, contra um
trade/+10,26 em13/05. Isso indica instabilidade, não autoriza excluir14/05
ou operar apenas venda depois de ver esses dados.

## Artefatos e repetição

Código scripts/replicate_gold_trend_rule.py valida correspondência entre config
e features congeladas, limites dos dados, warmup estritamente anterior, hashes
de fontes/código, trades, exclusões, direção e data. Saída completa:
output/vendor_indicator_research/gold_trend_replication_v1_20260927.json.
Presets configs/mt5/pilot29verify_gold_M10.{ini,set}; log e CSVs em
output/vendor_indicator_research/pilot29verify. Seis testes automatizados passaram.

```powershell
$verifyTicks = @(Get-ChildItem -LiteralPath D:/OneB/market-data/mt5/gold-replication-20260927 -Filter '*.csv.gz' | Select-Object -ExpandProperty FullName)
$warmTicks = @(Get-ChildItem -LiteralPath D:/OneB/market-data/mt5/gold-economic-20260927,D:/OneB/market-data/mt5/gold-week-20260927 -Filter '*.csv.gz' | Select-Object -ExpandProperty FullName)
python scripts/replicate_gold_trend_rule.py --config configs/gold_trend_replication_v1.json --objects output/vendor_indicator_research/pilot29verify/pilot29verify_gold_M10_0_XAUUSD.s_PERIOD_M10_objects.csv --ticks $verifyTicks --warmup $warmTicks --output output/vendor_indicator_research/gold_trend_replication_v1_20260927.json
python -m pytest tests/test_gold_replication.py tests/test_gold_trend_regime_replay.py tests/test_original_gold_ticks.py -q
```

## Próxima hipótese, ainda não testada ou aprovada

Auditar qualidade da entrada pelo preço executável: risco até o stop, ganho
remanescente até o alvo e deterioração desde o sinal desenhado. Esses valores
são disponíveis antes de decidir e podem levar a **não operar**. Definir limites
por justificativa econômica e registrá-los antes de nova semana; não procurar
o limiar que melhor salva11–15/05. Comparar a regra congelada com controles
simples, ampliar períodos/regimes e confirmar custos. Não treinar IA para
apagar a falha de replicação, nem prometer pequena vantagem sem novas evidências.
