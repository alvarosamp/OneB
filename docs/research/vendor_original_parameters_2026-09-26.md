# Inspeção dos outros originais no MT5

Inspeção direta dos diálogos das versões instaladas. Não é backtest econômico.
London Box segue em execução; nenhuma configuração desse teste foi alterada.

| Original | Evidência observada | Limite |
|---|---|---|
| 13X 3.00 | Descrição: EMA13 + DMI + filtros anti-lateralidade. Diálogo sem aba Parâmetros de entrada. Gráfico atual mostra média colorida, setas e X. | Períodos/limiares internos não expostos; não confundir com réplica DMI14. |
| 100 Pips 3.00 | Descrição explícita: EMA5/EMA10 + RSI(10) HL/2, filtros anti-lateralidade; recomendado H1. Sem aba de entradas observada. | RSI14 sobre fechamento não replica esta versão. Limiar/fórmula dos filtros não revelados. |
| DuckV4 4.00 | Descrição: SMA M5 colorida, fundo e dashboard. Aba de entradas só expõe Tema do painel (default fundo escuro). | Não expõe períodos ou gatilhos/saídas parametrizáveis. Direção MTF deve ser capturada com barras H1/H4 fechadas. |
| Nasdaq Gap Drive v6, versão interna 2.00 | Descrição: indicador puro, plot equivalente ao EA Auto v2. Abertura default hora 1, minuto 0 no servidor; Ignorar sábado/domingo=true; SMA50; TP1=1R; TP2 visual=1,5R; extensão das linhas 7 barras. | Default de horário não é automaticamente abertura de Nova York. Corrigir fuso/DST antes do teste; bid/ask bias não foi certificado. Não foi aplicado ao ouro. |
| Caixa Americana V2, versão interna 1.00 | Offset GMT servidor default +3; início caixa hora 11/minuto0; 10 barras M2 na formação; 60 barras M2 mínimas após caixa; TP1 multiplicador1. | Estratégia WIN/B3. Sem histórico WIN não há teste válido de desempenho; não foi aplicada ao ouro. |

Não foram alterados os inputs desses indicadores. Os diálogos de 100 Pips,
Duck, Gap Drive e Caixa Americana foram fechados sem aplicá-los ao gráfico.
O 13X foi observado no gráfico XAUUSD24_7.s H1; essa observação não valida seu
desempenho no XAUUSD.s nem substitui captura sequencial no testador.

## Impacto na pesquisa

Os resultados anteriores das reproduções Python continuam somente resultados
dessas hipóteses. Especialmente 100 Pips exige uma variante nova RSI10 sobre
preço mediano, mantendo os resultados anteriores versionados. A fórmula dos
filtros anti-lateralidade ainda não é conhecida. Não selecionar parâmetros
pelos exemplos visuais nem tratar seta histórica como sinal disponível na época.
