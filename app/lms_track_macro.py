"""Trilha "Leitura de regime e contexto macro" (antes "em produção").

Usa os estudos do OneB: calendar_v1 (calendário macro, 2019-2026) e tsmom_v1
(tendência de 1/3/12 meses, veredito exibido no app). Números citados vêm de
docs/research/calendar_v1_2026-10-07.md; se o estudo for refeito, revisar.
"""
from __future__ import annotations

TRACK_MACRO = (
    "leitura-de-regime-e-contexto",
    "Leitura de regime e contexto macro",
    "Calendário, tendência de médio prazo, dólar, juros, ouro e volatilidade como contexto para a decisão.",
    [
        (
            "Eventos e tendência",
            [
                ("Calendário macro: o que mexe e quanto", "CPI, payroll e FOMC medidos em 2019-2026.", 15),
                ("Tendência de 1, 3 e 12 meses", "A regra de tendência com mais evidência e como ler a aba Tendência.", 15),
            ],
        ),
        (
            "Intermercado",
            [
                ("Dólar, juros e Nasdaq", "Como ler correlações sem confundir com causa.", 14),
                ("O que move o ouro", "Juro real, dólar e bancos centrais: uma relação que mudou.", 14),
                ("Volatilidade e tamanho de posição", "Mesmo risco em dólares quando o mercado acelera.", 13),
            ],
        ),
    ],
)

MATERIAL_MACRO: dict[str, dict] = {
    "Calendário macro: o que mexe e quanto": {
        "summary": "Divulgações de CPI, payroll e FOMC multiplicam a volatilidade por várias vezes nos minutos seguintes. O efeito é medido, não adivinhado, e muda conforme o tema do momento.",
        "checklist": ["Olho o calendário antes de operar.", "Sei quanto a volatilidade costuma subir em cada evento.", "Reduzo tamanho ou espero passar a primeira meia hora.", "Não trato o primeiro movimento como direção certa."],
        "exercise": "Na aba Mercado › Calendário, escolha o próximo evento de alto impacto e escreva o que você faria com uma posição aberta 10 minutos antes.",
        "required": True,
    },
    "Tendência de 1, 3 e 12 meses": {
        "summary": "Seguir a tendência de semanas a meses é a regra com mais evidência acadêmica no longo prazo. No teste do OneB com 17 CFDs, de 2013 a 2026 e com custos, ela não mostrou vantagem: a direção aparece como descrição do preço, não como sinal.",
        "checklist": ["Sei ler a direção em 1, 3 e 12 meses.", "Sei o que é o preço de virada.", "Confiro o selo do teste antes de usar como evidência.", "Não confundo tendência de meses com sinal de entrada intradiário."],
        "exercise": "Na aba Análise › Tendência, anote para dois ativos se os três horizontes concordam e a que distância está o preço de virada de 3 meses.",
        "required": True,
    },
    "Dólar, juros e Nasdaq": {
        "summary": "Dólar e juros costumam se mover junto com o Nasdaq em certos períodos, mas correlação muda de sinal e não prova causa. Ela serve para entender o contexto, não para prever.",
        "checklist": ["Sei o que é correlação e o que ela não diz.", "Verifico em que janela a correlação foi medida.", "Percebo quando uma relação antiga quebra.", "Não opero só porque o dólar subiu."],
        "exercise": "Na aba Análise › Macro, anote a correlação recente do Nasdaq com os juros de 10 anos e escreva uma situação em que ela poderia mudar de sinal.",
        "required": True,
    },
    "O que move o ouro": {
        "summary": "Por duas décadas o ouro andou contra o juro real americano. Desde 2022 essa relação afrouxou: compras recordes de bancos centrais e incerteza global sustentaram o preço mesmo com juro real alto.",
        "checklist": ["Sei o que é juro real.", "Sei que a relação ouro x juro real mudou depois de 2022.", "Considero compras de bancos centrais como fator.", "Desconfio de regra antiga sem checar se ainda vale."],
        "exercise": "Escreva dois fatores que sustentam o ouro hoje e um que poderia derrubá-lo, citando de onde veio cada informação.",
        "required": True,
    },
    "Volatilidade e tamanho de posição": {
        "summary": "Quando a volatilidade sobe, o mesmo stop é atingido com mais facilidade. Ajustar o tamanho à volatilidade mantém o risco em dólares estável.",
        "checklist": ["Sei medir a volatilidade do ativo (ATR ou anualizada).", "Reduzo a quantidade quando a volatilidade sobe.", "Considero eventos do calendário como volatilidade programada.", "Mantenho o risco em dólares por operação constante."],
        "exercise": "Com risco de US$ 100, calcule a quantidade para um stop de 1 ATR num dia normal e num dia em que a volatilidade é 3 vezes maior.",
        "required": True,
    },
}

BODIES_MACRO: dict[str, str] = {
    "Calendário macro: o que mexe e quanto": """\
Algumas divulgações econômicas dos EUA movem o mercado inteiro em minutos. O OneB mediu quanto, em vez de repetir o que "todo mundo diz".

## Como foi medido

Para cada divulgação de 2019 a 2026 comparamos o movimento depois do horário oficial com o movimento no **mesmo horário** de 20 dias anteriores sem evento. O estudo foi pré-registrado (calendar_v1) e usa as datas oficiais da FRED e do Fed.

## O que encontramos (Nasdaq, 30 minutos depois)

- **CPI (inflação)**: cerca de **3,9 vezes** o movimento normal; nos 5 primeiros minutos, 6,7 vezes.
- **Payroll (emprego)**: cerca de **3,5 vezes**.
- **FOMC (decisão de juros)**: cerca de **2,4 vezes**, e o efeito dura: duas horas depois, ainda 2,4 vezes.
- **PIB e PCE**: efeito menor, entre 1,4 e 1,8 vezes.
- Na hora **antes** do evento o mercado costuma ficar mais calmo que o normal (0,7 a 0,8 vezes).

## O efeito muda com o tema

O CPI quase não mexia no Nasdaq em 2019. Em 2022, ano em que a inflação dominava as decisões do Fed, o movimento médio depois do CPI chegou a ser **14 vezes** o normal. O mesmo evento importa mais ou menos conforme o tema do momento.

## E a direção?

O primeiro movimento não diz para onde o preço vai. O único padrão estatisticamente firme foi uma **reversão** depois do payroll no Nasdaq (cerca de −0,12% na primeira hora, já descontado o spread), e ele ainda precisa de um teste próprio antes de virar qualquer regra.

## Como usar isso

- Veja a coluna "Volatilidade típica" em Mercado › Calendário.
- Com posição aberta perto de um evento forte, reduza o tamanho ou feche antes.
- Para entrar, espere pelo menos a primeira meia hora; no FOMC, as duas primeiras horas.
""",
    "Tendência de 1, 3 e 12 meses": """\
"Seguir a tendência" é a ideia de investimento com mais evidência acadêmica. O estudo mais citado (Hurst, Ooi e Pedersen, da AQR) testou a regra em mais de um século de dados de índices, commodities, juros e moedas.

## A regra

- Olhe o retorno dos últimos **1, 3 e 12 meses**.
- Se for positivo, a tendência daquele horizonte é de alta; se negativo, de baixa.
- Combine os três: todos em alta, todos em baixa ou misto.
- Ajuste o tamanho pela volatilidade: ativos mais nervosos recebem posição menor.

## O preço de virada

A tendência de 3 meses vira quando o preço cruza o fechamento de **3 meses atrás**. Esse número é objetivo e aparece na aba Análise › Tendência para cada ativo.

## O que o teste do OneB mostrou

O que funcionou em mais de um século pode não funcionar em qualquer mercado e período. O OneB rodou um teste pré-registrado (tsmom_v1) em 17 CFDs (índices, ouro, prata, petróleo e moedas), com custos, de 2013 a 2026:

- resultado médio de **−0,08% ao mês**, com intervalo de confiança cruzando o zero: **sem evidência**;
- mesmo sem custo nenhum, só +0,03% ao mês;
- a regra perdeu sobretudo em moedas; commodities foram levemente positivas.

A provável explicação: faltam títulos públicos e a maioria das commodities, onde a tendência mais pagou historicamente, e 2013–2019 foi uma década fraca para seguidores de tendência.

Por isso, na aba Análise › Tendência a direção aparece como **descrição do preço**, com o selo "Sem evidência". É um ótimo exemplo de por que testar antes de acreditar, mesmo em ideias famosas.

## O que a tendência não é

Não é sinal de entrada para o dia. É contexto de semanas a meses: ajuda a não brigar contra a maré.

## Como usar isso

- Antes de um setup, veja se os três horizontes concordam.
- Desconfie mais de operações contra os três horizontes juntos.
""",
    "Dólar, juros e Nasdaq": """\
O Nasdaq reúne empresas de crescimento, cujo valor depende muito de lucros futuros. Por isso ele costuma ser sensível a **juros**: juros mais altos reduzem o valor presente desses lucros.

## Correlação

**Correlação** mede se dois ativos costumam andar juntos (+1), em sentidos opostos (−1) ou sem relação (0) numa janela de tempo.

- Ela **muda**: a relação entre ações e juros foi diferente antes e depois de 2022.
- Ela **não prova causa**: dois ativos podem reagir à mesma notícia sem que um mova o outro.
- Ela depende da **janela**: 20 dias e 1 ano podem contar histórias opostas.

## Dólar

Um dólar forte costuma apertar as condições financeiras globais e pesa no lucro de multinacionais americanas. Também é uma relação que vai e volta.

## No OneB

A aba Análise › Macro mostra as correlações recentes e avisa quando uma relação antiga mudou de comportamento. Essa leitura é **contexto**: o motor de regime usa esses dados, mas nenhuma correlação vira ordem.

## Como usar isso

- Antes de usar uma relação ("juro sobe, Nasdaq cai"), confira se ela vale na janela recente.
- Em dias de dado de inflação ou de juros, espere mais volatilidade nos dois.
""",
    "O que move o ouro": """\
O ouro não paga juros. Por isso, por cerca de duas décadas, ele andou **contra o juro real americano** (juro descontada a inflação): juro real alto deixava o ouro menos atraente, e juro real baixo o favorecia.

## A relação mudou

Em 2022 o juro real dos EUA subiu de forma inédita e o ouro não caiu como a relação antiga previa. Depois, o ouro bateu recordes com juro real ainda alto. Duas forças explicam boa parte disso:

- **Bancos centrais** de países emergentes passaram a comprar ouro no ritmo mais forte em décadas, para diversificar reservas fora do dólar.
- **Incerteza global e geopolítica** aumentaram a procura por proteção.

O juro real ainda influencia a direção no curto prazo, mas deixou de definir sozinho o nível do preço.

## Lição de processo

Uma regra que funcionou por 20 anos pode parar de funcionar. Isso vale para indicadores também: os indicadores de ouro que o OneB testou não mostraram vantagem depois de custos em 2019–2026.

## Como usar isso

- Ao ler uma notícia sobre ouro, pergunte qual fator ela afeta: juro real, dólar, bancos centrais ou incerteza.
- Veja na aba Tendência se o ouro está em alta nos três horizontes antes de pensar em vender contra ele.
""",
    "Volatilidade e tamanho de posição": """\
Volatilidade é o tamanho típico do movimento. Ela muda o tempo todo, e o tamanho da posição deve mudar junto.

## O mesmo risco, tamanhos diferentes

Com risco de US$ 100 por operação:

- Dia normal, stop de US$ 2: quantidade = 100 ÷ 2 = **50**.
- Dia com volatilidade 3 vezes maior, stop de US$ 6 (para não ser atingido por ruído): 100 ÷ 6 ≈ **16**.

O risco em dólares é o mesmo; a quantidade cai.

## Volatilidade programada

Os eventos do calendário são volatilidade **com hora marcada**: depois do CPI, o movimento típico do Nasdaq fica perto de 4 vezes o normal por meia hora. Dá para planejar antes.

## Evidência

Estudos de portfólios ajustados pela volatilidade (Moreira e Muir) mostram que reduzir exposição quando a volatilidade está alta melhorou a relação entre risco e retorno em vários mercados. O teste de tendência do OneB usa exatamente esse ajuste.

## Como usar isso

- Veja a volatilidade anualizada e se ela está alta na aba Análise › Tendência.
- Antes de eventos fortes, reduza a quantidade ou espere.
""",
}
