# Laboratório de indicadores (lab_v1): descoberta sem sobreviventes

Pré-registro: `configs/preregistration/lab_v1.json` (LOCK). A emenda de 10/10/2026 foi feita antes de qualquer cálculo:
- **WTI fora** por falha da fonte (ask incompleto);
- **família F8 (Duck)** acrescentada;
- **XAUUSD M5** remontado do M1.

Relatórios: `D:\OneB\research\lab_v1\discovery.json` e `gross_diagnostic.json`.

## Veredito: nenhum dos 64 candidatos sobreviveu

- **Teste:** 8 famílias × 2 parâmetros × 4 ativos (ouro, Nasdaq, S&P 500, euro/dólar), em M5 da Dukascopy de 2019 a 2022, com custo real.
- **Positivos:** só 4 dos 64, todos perto de zero (no máximo +0,009R por trade), com IC cruzando zero.
- **Correção para múltiplos testes:** o menor q-valor (Benjamini-Hochberg) foi 1,0.
- **Confirmação (2023–2026):** não roda. Não há sobrevivente, e o período continua intocado.

| Família | Melhor caso | Faixa típica (R por trade) |
|---|---|---|
| F1 Donchian (Tartarugas) | euro/dólar 55: −0,03 | −0,03 a −0,38 |
| F2 Cruzamento de médias | ouro 20/50: +0,009 | −0,02 a −0,48 |
| F3 Bollinger (reversão) | euro/dólar 2,0: −0,05 | −0,05 a −0,89 |
| F4 RSI(2) (Connors) | euro/dólar 10: +0,001 | 0 a −0,27 |
| F5 Squeeze | Nasdaq 10: −0,07 | −0,07 a −0,42 |
| F6 Rompimento da abertura (Crabel) | Nasdaq 15 min: +0,006 | +0,01 a −0,36 |
| F7 Momentum intradiário (Gao et al.) | Nasdaq até 15h: +0,001 | 0 a −0,54 |
| **F8 Duck (SMA60 H4/H1 + M5)** | Nasdaq alvo 2: −0,08 | **−0,08 a −0,38, negativo em todos os ativos** |

## Diagnóstico sem custos (fora do pré-registro, só para entender)

- **A maioria das regras não tem vantagem nem antes do custo.** A regra mediana dá −0,02R por trade sem nenhum spread. O custo tira em média mais 0,10R.
- **A exceção é o momentum intradiário (F7).** Sem custo, dá +0,11R no Nasdaq (IC +0,05 a +0,17) e +0,09R no S&P 500 (IC +0,02 a +0,16), o que bate com a literatura. Com spread real, cai para zero no Nasdaq e fica negativo no S&P. Para a vantagem sobreviver, seria preciso um custo bem menor, como um futuro com corretagem baixa.
- **O Duck é negativo mesmo sem custo.** A regra objetiva (tendência em H4/H1 e entrada no cruzamento do M5) entra tarde e sai no ruído.

## Custo da corretora: S&P 500 é ~25x mais caro que Nasdaq

| Símbolo HonorPro | Spread ao vivo | Preço | Custo relativo |
|---|---|---|---|
| US100.s (Nasdaq) | 0,7 ponto | ~25.000 | ~0,003% |
| US500.s (S&P 500) | **5,3 pontos** | ~7.660 | **~0,07%** |

O pré-registro manda usar o maior spread entre a Dukascopy e a corretora. Por isso o S&P 500 aparece muito pior em todas as famílias: 5,3 pontos na HonorPro contra 0,52 na Dukascopy.

**Na prática:** quem opera índice americano nessa corretora deve preferir o US100.s.

## Decisão

- Nenhuma regra do laboratório vira indicador, sinal ou evidência na IA.
- O período de 2023–2026 continua intocado para testes futuros pré-registrados.
- **Candidato a novo pré-registro:** o momentum intradiário (F7) com custo de futuro. Ele é a única regra com vantagem bruta e respaldo na literatura. Seria testado apenas na confirmação de 2023–2026, com o custo definido antes.

## Teste f7_honor_v1: momentum intradiário com o custo da HonorPro, REPROVADO

Pré-registro: `configs/preregistration/f7_honor_v1.json`, travado antes do cálculo. Um único teste, em 2023 a 2026 (período intocado), no Nasdaq.
- **Custo:** spread do US100.s de 0,7 ponto, fixo em todas as horas, mais 0,5 ponto de slippage por lado.
- **Resultado:** 805 trades, **−0,028R por trade** (IC 95% de −0,086 a +0,028), com 48% de acerto.
- **Janela recente:** −0,10R por trade.
- **Por ano:** 2023 +0,06R · 2024 −0,05R · 2025 −0,08R · 2026 −0,06R. A vantagem que existia até 2022 desapareceu a partir de 2024, o padrão típico de efeito que enfraquece depois de publicado.
- **Custo dobrado:** −0,057R (IC −0,11 a −0,003).

Encerrado: não será refeito com outros parâmetros.
