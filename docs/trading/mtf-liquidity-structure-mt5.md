# MTF Liquidity Structure para MetaTrader 5

O indicador `mql5/Indicators/MTF_Liquidity_Structure.mq5` foi feito para o gráfico M1 de qualquer símbolo da corretora — por exemplo, `XAUUSD`, `XAUUSDm`, `NAS100`, `USTEC` ou `NAS100.cash`. Ele não envia ordens. As setas só aparecem depois de a vela M1 fechar, portanto não usam dados futuros nem repintam uma entrada já fechada.

## Regras objetivas implementadas

| Camada | Leitura |
|---|---|
| H4 | Direção por rompimento de último swing confirmado; quando não há rompimento, preço e inclinação da EMA 50 H4 devem concordar. |
| H1 | Um BOS (fechamento além do último swing H1) na direção H4, válido por até 12 velas H1. |
| M15 | Varredura de liquidez: perfura a mínima/máxima dos 20 candles anteriores e fecha de volta para dentro. |
| M5 | Condução: fechamento rompe o intervalo dos 5 candles M5 anteriores na direção do setup. |
| M1 | Ataque: fechamento rompe o intervalo dos 5 candles M1 anteriores, com todos os filtros acima ativos. |

O swing só existe após `InpSwingStrength` candles fecharem à direita. Isto é crucial: um pivô desenhado antes de ser confirmado seria olhar o futuro e faria o teste parecer melhor do que é.

## Instalação

1. No MT5, abra **Arquivo → Abrir pasta de dados → MQL5 → Indicators**.
2. Copie [MTF_Liquidity_Structure.mq5](../../mql5/Indicators/MTF_Liquidity_Structure.mq5) para essa pasta e compile no MetaEditor (F7).
3. Abra o gráfico **M1** do símbolo da sua corretora, carregue pelo menos alguns meses de histórico em todos os tempos e arraste o indicador ao gráfico.
4. Ajuste `InpArrowOffsetPoints` ao número de dígitos do ativo. Isso é apenas visual e não muda o sinal.

Não opere uma seta isoladamente. O indicador não conhece spread, slippage, horário de notícia, tamanho de lote ou o seu risco. Um ponto de partida operacional é stop além da extremidade da varredura M15 e alvo de pelo menos 2R, mas esses parâmetros devem ser medidos no seu feed.

## Validação correta no feed da corretora

Exporte histórico M1 de `XAUUSD` e de `NAS100` no MT5 (fuso do servidor preservado). Depois rode:

```powershell
python scripts/validate_mtf_liquidity.py --csv C:\caminho\XAUUSD_M1.csv --symbol XAUUSD
python scripts/validate_mtf_liquidity.py --csv C:\caminho\NAS100_M1.csv --symbol NAS100
```

O validador grava sinais e um relatório em `output/mtf_validation/`. Ele mede o retorno direcional após 60 minutos, sem custos; não é ainda uma prova de rentabilidade. Para aceitar a estratégia, valide períodos diferentes (idealmente pelo menos seis meses), inclua spread/comissão/slippage e separe uma janela final que não foi usada para ajustar os parâmetros.
