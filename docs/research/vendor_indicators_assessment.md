# Auditoria quantitativa dos indicadores adquiridos

## Escopo e limitações

Os sete pacotes entregues contêm somente binários MetaTrader 5 `.ex5`. Não há
fontes `.mq5`, documentação de parâmetros ou PDFs nos ZIPs. Portanto, a fórmula
exata, o uso de barra ainda aberta e eventual repaint não podem ser certificados
por inspeção de código. Os binários não foram decompilados. A especificação abaixo
separa regras declaradas nos vídeos de aproximações que precisam ser validadas
contra os sinais visuais e buffers dos indicadores.

Todos os backtests devem tomar a decisão apenas após o fechamento da barra que
confirma o sinal e executar na abertura da barra seguinte. Resultados desenhados
retroativamente no gráfico não constituem evidência.

## Catálogo testável

| Produto | Regra declarada | Saída/risco declarado | Informação ainda oculta |
|---|---|---|---|
| Gold Fakeout CRAZY v4 1.00 | XAUUSD M10; EMA100; Bollinger(20, 2); variante 24/7 sem filtro de horário nem corte de sexta | SL fixo 200 pontos; TP fixo 150 pontos; time-stop de 4 horas; cooldown mantido | fórmula de direção, regra e duração do cooldown, momento em que o sinal fica definitivo |
| 13X | EMA13; diferencial/espaçamento e cruzamento de +DI/−DI; seta verde compra e vermelha venda | sair no fechamento da barra marcada com X; alternativamente stop na máxima/mínima da barra do X | período DMI/ADX, filtros adicionais da versão atual, definição do X |
| 100 Pips por Dia | cruzamento MA5/MA10 próximo ao cruzamento do RSI através de 50; versão atual adiciona ADX e afastamento percentual das médias | entrada, stop, TP1 e TP2 desenhados | tipo das médias, período/limiar ADX, tolerância temporal, fórmula do stop/TP |
| London Box | MT5 H1; caixa de “preço justo” antes da abertura de Londres; entrada somente no fechamento que confirma rompimento | stop além do lado oposto; alvo preferido 1,25R–2R, sobretudo 1,5R–2R | horas exatas da caixa, timezone/DST, buffer de confirmação |
| Nasdaq Gap Drive v6 | Nasdaq M1; uma decisão por dia na abertura indicada como aproximadamente 19:00; compra ou venda deve ocorrer após fechar a barra de decisão | stop, TP1 e TP2 próprios; sair se o trade não desenvolver rapidamente | definição da abertura, timezone, fórmula bid/ask bias, níveis e time-stop |
| Duck Duck Duck v4 | SMA60 em H4, H1 e M5; H4/H1 definem direção e M5 dá entrada quando os três estão do mesmo lado | discricionária; tendência longa | gatilho M5 e saída são subjetivos |
| Caixa Americana v2 | WIN/B3 M2; caixa; entrada no fechamento confirmando rompimento | stop além do lado oposto; TP1/TP2; proteger no zero após TP1 | horas da caixa, fórmula de volatilidade/fluxo, distâncias dos alvos |

## Hipóteses reproduzíveis

1. **Gold Fakeout:** EMA100 e Bollinger(20, 2), conforme os parâmetros expostos
   pelo binário; toque/rejeição da EMA100 na direção do lado prévio do preço.
   A versão CRAZY usa SL=200 e TP=150 pontos, escaneia 500 barras, desenha até
   30 trades simultâneos e encerra após quatro horas. A variante declara operar
   24/7 sem filtro de horário e sem corte de sexta. A versão horária descrita no
   vídeo será tratada como estratégia separada, testando 07:00–11:30 nos fusos
   America/Sao_Paulo, America/New_York e do servidor. A fórmula de direção e o
   cooldown continuam não certificados.
2. **13X:** EMA13 + DMI(14); entrada no cruzamento +DI/−DI quando preço e EMA13
   concordam, varrendo ADX 15–30. A saída por deterioração será o cruzamento
   inverso, queda do ADX ou buffer de saída do binário quando observável.
3. **100 Pips:** MA5/MA10 simples e exponenciais; cruzamentos do RSI(14) em 50
   dentro de 0–3 barras; ADX 15–30; afastamento MA normalizado por ATR e preço.
4. **London Box:** caixas terminando na abertura de Londres com 1–4 horas de
   formação, entrada no fechamento além do limite, buffer de 0–0,15 ATR, stop
   estrutural e alvos 1,25R/1,5R/2R.
5. **Gap Drive:** só poderá ser replicado fielmente com bid/ask. Serão comparados
   desequilíbrio de atualizações bid/ask, gap overnight, retorno do primeiro
   minuto e microestrutura da janela. OHLC isolado é apenas baseline.
6. **Duck:** sinal objetivo mínimo: H4 e H1 concluídos do mesmo lado da SMA60 e
   cruzamento/retomada no M5. A parte discricionária não será usada no ranking.
7. **Caixa Americana:** fica fora do ranking Nasdaq/ouro e bloqueada até haver
   histórico WIN M2; não será validada usando outro instrumento por analogia.

## Protocolo de validação

- Registrar sinais do `.ex5` em tempo real e em reprodução histórica, verificando
  se setas e níveis mudam após fechar a barra.
- Comparar timestamps do binário com cada réplica e medir precision, recall e
  concordância, sem escolher parâmetros no holdout.
- Desenvolvimento walk-forward com embargo; holdout cronológico intocado; custos
  bid/ask, slippage e comissão; resultado anual, por horário e regime.
- Corrigir múltiplos testes (Benjamini–Hochberg e deflated/probabilistic Sharpe
  quando aplicável) e rejeitar soluções dependentes de poucos trades ou um ano.
- Classificações permitidas: aprovado para paper trading, precisa de mais dados,
  experimental ou rejeitado. Nenhum indicador é aprovado com base no vídeo ou em
  exemplos selecionados.

## Fontes primárias fornecidas

1. Felipe Andrade — [GOLD FAKEOUT](https://www.youtube.com/watch?v=JypPCU-lFv0).
2. Felipe Andrade — [Indicador 13X](https://www.youtube.com/watch?v=ynUHlFKvfvM).
3. Felipe Andrade — [Indicador 100 PIPS POR DIA](https://www.youtube.com/watch?v=PJbo-h5R2nA).
4. Felipe Andrade — [London Box MT5](https://www.youtube.com/watch?v=bVL6LpD8Su4).
5. Felipe Andrade — [NASDAQ GAP DRIVE](https://www.youtube.com/watch?v=zG9n2TPyesA).
6. Felipe Andrade — [Duck Duck Duck MT5](https://www.youtube.com/watch?v=4LFktFxGIBQ).
7. Felipe Andrade — [Caixa Americana MT5](https://www.youtube.com/watch?v=jlnIcbO_1cc).

As transcrições automáticas estruturadas estão em
`output/vendor_indicator_research/transcripts_clean/`; erros de reconhecimento
foram interpretados apenas quando o contexto operacional era inequívoco.
