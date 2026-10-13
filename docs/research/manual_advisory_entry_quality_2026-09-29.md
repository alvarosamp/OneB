# Plano manual de entrada/saída: teste econômico

O objetivo do algoritmo é **aconselhar**, não enviar ordens. Para cada novo sinal
observado do Gold Fakeout original no XAUUSD.s M10, ele deve dizer comprar,
vender ou **não operar**, com instante da cotação, preço executável estimado,
stop, alvo e prazo máximo de saída. A pessoa confirma ou descarta. Atualmente
nenhum setup está aprovado; a ação exibível é `NO_TRADE`, sem confiança calibrada.

O módulo `scripts/entry_quality.py` calcula compra no ask e venda no bid,
com slippage adicional na entrada. O risco líquido até o stop soma slippage
de saída e comissão ida/volta; o ganho líquido remanescente até o alvo os
subtrai. Rejeita níveis cruzados, ganho consumido pelos custos e relação
ganho/risco líquida inferior a 1,0. Esse limiar é um freio econômico
**diagnóstico, escolhido após exame das semanas disponíveis**, não uma regra
validada. Uma relação acima de 1 não implica vantagem estatística.
O [manual MQL5 para cotação atual](https://www.mql5.com/en/docs/marketinformation/symbolinfotick)
confirma os campos `bid`, `ask` e `time_msc` usados na auditoria.

Cotação
anterior ao sinal ou mais de 5 segundos depois dele bloqueia um plano manual;
o horário é o domínio bruto do MT5, sem fuso de sessão certificado. A saída
proposta é condicional: stop, alvo ou limite de quatro horas, o que ocorrer
primeiro. Stop pode sofrer gap/slippage, portanto não é perda garantida.

O replay reexecuta a sequência com uma posição por vez após cada recusa; não
remove trades perdedores de uma lista já realizada. Capturas de objetos,
latência fixa de 250 ms, spread bid/ask histórico real, slippage hipotético
0,05/lado, comissão hipotética 0,10 por onça/ida-volta. PnL é USD/onça, não
retorno percentual de conta. Posições censuradas não recebem PnL inventado.

| Período | Regra | Sinais | Trades completos | PnL USD/onça | PF | Recusas pela relação |
|---|---|---:|---:|---:|---:|---:|
| 04–08/05/2026 | Sem freio | 49 | 15 | -28,10 | 0,735 | — |
| 04–08/05/2026 | Relação líquida ≥1 | 49 | 7 | -66,55 | 0,221 | 22 |
| 11–15/05/2026 | Sem freio | 47 | 15 | -41,51 | 0,660 | — |
| 11–15/05/2026 | Relação líquida ≥1 | 47 | 6 | -11,71 | 0,775 | 33 |

A primeira semana piorou com o freio; a segunda perdeu menos, mas continuou
negativa. As semanas já tinham sido analisadas, logo não são teste novo fora
da amostra para essa regra. Nenhuma evidência para recomendar entrada real ou
paper trading. O freio continua útil como proteção contra preço desfavorável,
mas não deve ser confundido com estratégia lucrativa. Não ajustar o limiar para
"salvar" retrospectivamente estes resultados.

Para repetir:

```powershell
$week1 = @(Get-ChildItem -LiteralPath 'D:\OneB\market-data\mt5\gold-economic-20260927','D:\OneB\market-data\mt5\gold-week-20260927' -Filter '*.csv.gz' | Select-Object -ExpandProperty FullName)
python scripts/evaluate_entry_quality.py --objects output/vendor_indicator_research/pilot28week/pilot28week_gold_M10_0_XAUUSD.s_PERIOD_M10_objects.csv --ticks $week1 --output output/vendor_indicator_research/gold_entry_quality_week1_20260929.json
$week2 = @(Get-ChildItem -LiteralPath 'D:\OneB\market-data\mt5\gold-replication-20260927' -Filter '*.csv.gz' | Select-Object -ExpandProperty FullName)
python scripts/evaluate_entry_quality.py --objects output/vendor_indicator_research/pilot29verify/pilot29verify_gold_M10_0_XAUUSD.s_PERIOD_M10_objects.csv --ticks $week2 --output output/vendor_indicator_research/gold_entry_quality_week2_20260929.json
python -m pytest tests/test_original_gold_ticks.py -q
```

Os JSONs guardam hashes das fontes, trades, exclusões e economia de cada
entrada. Próximo teste legítimo: congelar critério, custo, horário e validade
da cotação **antes** de semanas ainda não analisadas, adquirir pelo menos 250
sessões e comparar com nenhum filtro e com filtros simples. Só após estabilidade
fora da amostra e custos auditados considerar cartões de compra/venda para
simulação humana; jamais acionar Algotrading nesta etapa.
