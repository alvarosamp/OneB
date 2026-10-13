# Teste dos indicadores originais no MT5 — 2026-09-26

Terminal Honor Pro MT5 aberto via controle de aplicativos Windows. Os sete
indicadores comprados estão instalados em Indicators/Purchased. Algotrading
não foi habilitado e nenhuma ordem foi enviada à conta.

## Primeira execução nativa

- Binário: Purchased/GOLD Fakeout CRAZY v4.ex5.
- Símbolo: XAUUSD.s, não XAUUSD24_7.s.
- Timeframe: M10.
- Intervalo solicitado: 2026-01-01 a 2026-09-25.
- Modelagem: Cada tick (gerado), não ticks reais certificados.
- Parâmetros originais observados: EMA100, Bollinger20/desvio2,
  StopPontos200, AlvoPontos150, HistoryBars500, MaxTrades30,
  SLTP_Barras10, AlertarTF=true, UsarTimeStop=true, HorasMax4.
- Teste visual iniciado em 09:35 local. Log confirma carregamento do binário
  original e início da reprodução. Gráfico em abril mostrou setas e etiquetas
  GAIN/LOSS. Isso confirma funcionamento visual, não lucratividade.

### Conclusão confirmada pelo log

Execução terminou em 09:43:23 local, sem erro de execução reportado:
33.100.167 ticks gerados, 16.208 barras M10, duração 8min18s.
O histórico disponível começa em 2026-04-10 e o testador deslocou o início
efetivo para 2026-04-14, para dispor de barras de aquecimento.
Portanto, não houve cobertura de janeiro a março, apesar do intervalo solicitado.
As etiquetas OPEN no fim são sinais desenhados, não posições da conta.

## Limites

## Segunda execução: London Box

Iniciada em 09:44:54 local: `Purchased/Estratégia Caixa de Londres.ex5`,
XAUUSD.s H1, intervalo solicitado 2026-01-01 a 2026-09-25, Cada tick gerado.
O binário carregou e exibiu caixas, compra/venda fraca/forte, SL, TP1 e TP2.
A execução está em andamento; não registrar como concluída ou lucrativa.
O registrador separado VendorSignalAudit foi compilado e instalado em
Experts/Research, mas ainda não foi usado nessa execução visual simples.

## Limitações da evidência

A execução ainda não constitui backtest econômico completo. As etiquetas do
indicador não equivalem a operações executadas a bid/ask com slippage e comissão.
Não foi demonstrada ausência de repaint. O intervalo solicitado pode exceder
o histórico fornecido pelo broker; registrar cobertura real no fim do teste.
São necessários captura sequencial dos sinais/objetos e comparação dos sinais
congelados com recálculo posterior, antes de calcular resultados líquidos.

Log local: AppData/Roaming/MetaQuotes/Terminal/
90A3EE13DEA06374A8DE536622D95A3C/Tester/logs/20260926.log.

Não apresentar métricas anteriores das reproduções Python como resultados
destes binários originais.
