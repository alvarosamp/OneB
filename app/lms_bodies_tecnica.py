"""Texto das aulas de Análise técnica e de Processo (chaves = títulos do seed, sem acento).

Regra editorial: indicador e padrão gráfico aparecem como ferramenta de leitura e
hipótese a testar, nunca como "o mercado faz X". Onde há resultado próprio do
OneB, ele é citado.
"""
from __future__ import annotations

TECNICA_BODIES: dict[str, str] = {
    "Candles e price action": """\
Um **candle** resume um período: abertura, máxima, mínima e fechamento. O corpo vai da abertura ao fechamento; os pavios mostram até onde o preço foi e voltou.

## O que um candle conta

- **Corpo grande**: um lado dominou o período.
- **Pavio longo**: o preço foi até um nível e foi rejeitado.
- **Corpo pequeno**: indecisão ou pouca participação.

## O que um candle não conta

Um candle sozinho não diz o que vem depois. O mesmo pavio longo significa coisas diferentes em tendência, em lateralidade e perto de um nível importante. Por isso, no OneB, candle é **contexto**, não gatilho.

## Price action

**Price action** é ler o movimento do preço sem depender de indicadores: sequência de topos e fundos, rompimentos, rejeições. É útil para descrever o mercado; para virar regra de entrada, precisa ser escrito de forma objetiva e testado.

## Como usar isso

- Descreva o candle atual junto com o contexto: onde ele está em relação à tendência e aos níveis?
- No Laboratório, o replay "Nasdaq: dia de tendência" é bom para observar corpos e pavios em sequência.
""",
    "Tendencia, faixa e reversao": """\
Antes de escolher um setup, classifique o **regime** do ativo.

## Três regimes

- **Tendência**: topos e fundos cada vez mais altos (ou mais baixos). Médias inclinadas.
- **Faixa (lateral)**: o preço oscila entre limites, sem direção.
- **Reversão**: a tendência perde força e muda de lado.

## Por que importa

Cada regime pede uma lógica. Rompimentos fazem mais sentido em tendência; em faixa, muitos voltam para dentro. Essas são hipóteses comuns, que valem ser conferidas no seu ativo.

## Tendência de longo prazo tem evidência

Entre todas as ideias de "seguir a tendência", a que tem mais evidência acadêmica é a de **semanas a meses** (1, 3 e 12 meses), testada em mais de um século de dados de índices, commodities e moedas. O OneB testa essa regra com custos no teste pré-registrado tsmom_v1 e mostra o resultado na aba Análise › Tendência.

## No OneB

O regime diário combina médias (EMA 20 e 50), RSI, força da tendência (ADX) e estrutura de topos e fundos.

## Como usar isso

- Classifique três ativos da sua lista e escreva qual setup é permitido em cada regime.
""",
    "Suporte, resistencia e zonas": """\
**Suporte** e **resistência** são regiões onde o preço já reagiu antes. Trate-os como **zonas**, não como linhas exatas.

## Como marcar

- Use topos e fundos recentes e relevantes (swing highs e lows).
- Prefira poucos níveis claros a muitos níveis confusos.
- Marque uma faixa de preço, não um valor de centavos.

## Heurísticas populares

"Resistência rompida vira suporte" é uma ideia muito repetida. Ela pode ou não valer no seu ativo e no seu horário: trate como **hipótese** e confira no histórico antes de usar como regra.

## Para que servem no plano

Níveis ajudam a decidir **onde a ideia fica errada** (stop) e **até onde faz sentido mirar** (alvo). Esse é o uso mais objetivo deles.

## Como usar isso

- Para um setup planejado, marque suporte, resistência, entrada e invalidação.
""",
    "Medias, RSI e MACD sem excesso de sinal": """\
Indicadores transformam o preço em números. São úteis para **descrever**; viram armadilha quando são usados como gatilho isolado.

## Os três mais comuns

- **Médias móveis**: mostram a direção. A média exponencial (EMA) reage mais rápido aos preços recentes.
- **RSI**: mede a força recente de 0 a 100. Acima de 70 indica movimento esticado para cima, o que em tendência forte pode durar muito.
- **MACD**: compara duas médias para mostrar aceleração ou perda de momentum.

## O problema do excesso

Com muitos indicadores, sempre algum confirma o que você quer ver. Use poucos e saiba o papel de cada um.

## O que os nossos testes mostram

Cruzamentos de médias e rompimentos de curto prazo são exatamente o tipo de regra que o laboratório do OneB testa com custos. Indicadores comprados que usam combinações de médias, RSI e ADX (como o 100 Pips) não mostraram vantagem depois de custos nos nossos testes.

## Como usar isso

- Escreva uma regra com média, RSI ou MACD e, junto, quando ela deve falhar.
""",
    "Volume e forca do movimento": """\
**Volume** é a quantidade negociada. Ele mostra quanta participação houve num movimento.

## Volume relativo

Compare o volume atual com a média recente. Volume relativo de 2,0x significa o dobro do normal para aquele horário.

## Leituras comuns

- Movimento com volume alto: mais participação.
- Rompimento com volume baixo: participação fraca.

São leituras comuns, não leis. Trate como hipótese e confira no histórico do ativo.

## Cuidado com a fonte

Em CFDs e forex, o "volume" costuma ser o número de ticks da corretora, não o volume real do mercado. Em ações e ETFs americanos, o volume é o da bolsa.

## Como usar isso

- Encontre um candle com volume acima da média e escreva se ele confirma ou contradiz o seu plano.
""",
    "ATR, Bollinger e volatilidade": """\
**Volatilidade** é o tamanho típico do movimento. Ela define o stop, o alvo e o tamanho da posição.

## ATR

O **ATR** (Average True Range) mede a amplitude média dos candles, incluindo gaps. Um stop menor que o movimento normal do ativo tende a ser atingido por ruído.

## Bandas de Bollinger

Uma média com bandas a alguns desvios-padrão de distância. Bandas estreitas indicam compressão; largas, expansão.

## Volatilidade e tamanho

Com o mesmo risco em dólares, volatilidade maior pede stop mais distante e **menos unidades**. A aba Análise › Tendência mostra a volatilidade anualizada de cada ativo e se ela está alta em relação aos últimos dois anos.

## Como usar isso

- Calcule um stop de 1,5 ATR a partir do último preço e a quantidade correspondente ao seu risco.
""",
    "Montando um setup na Mesa Tecnica": """\
Um **setup** completo responde, antes da entrada:

- **Contexto**: qual o regime e a tendência?
- **Tese**: por que o preço deve ir na direção esperada?
- **Gatilho**: qual evento objetivo dispara a entrada?
- **Stop e invalidação**: onde a ideia fica errada?
- **Alvo**: até onde faz sentido mirar?
- **Tamanho**: quanto arriscar?
- **Critério de não operar**: o que faria você desistir?

## Risco e retorno

Com relação risco/retorno menor, o setup precisa acertar mais para pagar os custos. Sem evidência de acerto alto, rever o plano ou aceitar "sem setup" é o caminho.

## Do papel ao teste

Um setup escrito assim pode ser testado. Um setup "no olho" não pode.

## Como usar isso

- Monte um setup na Mesa Técnica com todos os campos e execute-o no Laboratório.
""",
}

PROCESSO_BODIES: dict[str, str] = {
    "Journaling de decisoes": """\
O **diário de decisões** transforma cada operação, ou decisão de não operar, em material de estudo.

## O que registrar

- **Tese**: o motivo da operação.
- **Gatilho**: o evento que disparou a entrada.
- **Invalidação e stop**: onde você estaria errado.
- **Risco**: quanto arriscou, em dólares e em R.
- **Resultado**: em R, e se o plano foi seguido.

## Por que o processo, não só o resultado

Uma operação boa pode perder e uma ruim pode ganhar. Só o registro do processo permite separar sorte de habilidade.

## Como usar isso

- Crie uma entrada no Diário de Decisão com todos os campos, inclusive para um dia em que você decidiu não operar.
""",
    "Tese, gatilho e invalidacao": """\
Uma decisão **auditável** tem três partes escritas antes da entrada.

## As três partes

- **Tese**: "O Nasdaq está em tendência de alta em 1, 3 e 12 meses e corrigiu até a média de 20."
- **Gatilho**: "Entro se fechar acima de 25.600 num candle de 15 minutos."
- **Invalidação**: "A ideia está errada se fechar abaixo de 25.480." É aqui que vai o stop.

## Por que escrever

Sem invalidação escrita, o stop vira negociação com você mesmo. Escrito antes, ele é só cumprido.

## Prazo

Inclua quanto tempo a ideia tem para funcionar. Uma tese de 1 dia não deve virar posição de 1 mês.

## Como usar isso

- Reescreva uma decisão recente com tese, gatilho e invalidação em frases objetivas.
""",
    "Revisao de falso positivo": """\
Um **falso positivo** é um sinal que cumpriu as regras e falhou.

## Duas causas possíveis

- **Faltou um filtro**: havia evidência contrária que a regra ignorou.
- **Variância normal**: nenhum método acerta sempre; algumas perdas são o custo de operar.

## Como revisar

- Compare a confiança que você tinha com o resultado.
- Procure o sinal contraditório que estava visível na hora (não o que só apareceu depois).
- Verifique se o regime mudou.

## Cuidado com o ajuste fino

Mudar a regra a cada falso positivo é a forma mais rápida de criar um método que só funciona no passado. Mudança de regra pede novo teste, como na aula "Fora da amostra e pré-registro".

## Como usar isso

- Revise uma decisão que falhou e escreva se foi filtro faltando ou variância.
""",
    "Checklist semanal da Mesa": """\
Uma vez por semana, revise o processo.

## Checklist

- Quantas operações fiz e quantas seguiram o plano?
- Qual foi o resultado em R? E o acerto?
- Qual foi a maior queda (drawdown) da semana?
- Quais sinais eu bloqueei e o que aconteceu depois?
- Quais aulas fiz e qual lacuna apareceu?

## Drawdown

**Drawdown** é a maior queda do capital a partir de um pico. Ele mostra a dor que o método impõe, algo que a média esconde.

## Como usar isso

- Preencha a revisão desta semana e escolha uma única coisa para melhorar na próxima.
""",
    "Plano de evolucao individual": """\
A próxima aula deve nascer do seu **erro mais frequente**.

## Erros comuns e onde estudar

- Entrar sem invalidação: "Tese, gatilho e invalidação".
- Tamanho errado: "Tamanho de posição e stop".
- Entrar por impulso: "Lidando com FOMO e overtrading".
- Confiar em sinal sem teste: trilha "Como avaliar um sinal".

## Objetivo mensurável

"Ganhar mais" não é objetivo de processo. "Zerar entradas sem invalidação escrita em 4 semanas" é: dá para medir e depende só de você.

## Como usar isso

- Escolha uma lacuna, a aula correspondente e um exercício de 7 dias no Laboratório para corrigi-la.
""",
}
