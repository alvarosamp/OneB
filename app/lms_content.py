"""Conteúdo de aula da Academia que não cabe no seed curto de app/routers/lms.py.

- TRACK_SINAIS: a trilha "Como avaliar um sinal", construída com os resultados
  reais da pesquisa do OneB (docs/research/*2026-10-0*). Os números citados são
  os dos relatórios; se um relatório for refeito, a aula precisa ser revista.
- LESSON_BODIES: texto da aula (markdown simples: parágrafos, "## " subtítulos,
  "- " listas, **negrito**). O frontend renderiza sem HTML cru.
"""
from __future__ import annotations

TRACK_SINAIS = (
    "como-avaliar-um-sinal",
    "Como avaliar um sinal",
    "Taxa de acerto, custos, backtest honesto, teste fora da amostra e como ler promessas de sinais, com os testes reais do OneB.",
    [
        (
            "O número que importa",
            [
                ("Acerto não é lucro", "Por que 55% de acerto pode perder dinheiro: expectativa em R.", 16),
                ("Custos que somem com o resultado", "Spread, slippage e comissão medidos num setup real.", 14),
            ],
        ),
        (
            "Teste honesto",
            [
                ("Backtest honesto: olhar o futuro sem perceber", "Look-ahead e repaint: o erro que criou +0,34R do nada.", 18),
                ("Fora da amostra e pré-registro", "Separar descoberta de confirmação e decidir a regra antes do teste.", 18),
            ],
        ),
        (
            "Na prática",
            [
                ("Lendo promessas de sinais", "Checklist para avaliar um serviço de sinais antes de pagar ou seguir.", 15),
            ],
        ),
        (
            "O laboratório do OneB",
            [
                ("64 regras testadas: o que reprovou e por quê", "Duck, RSI, médias, Bollinger e rompimentos com custo real, de 2019 a 2026.", 16),
                ("Horário e spread: quando o custo come o movimento", "O mapa de horários e por que o mesmo trade custa 25 vezes mais em outro símbolo.", 14),
                ("Como conferir o OneB: placar, diário e o que não prometemos", "Placar ao vivo, diário, saldo mínimo e por que a IA não dá compra e venda.", 15),
            ],
        ),
    ],
)

MATERIAL_SINAIS: dict[str, dict] = {
    "Acerto não é lucro": {
        "summary": "Taxa de acerto sozinha não diz se um método ganha dinheiro. O que importa é a expectativa: quanto se ganha em média por operação, depois dos custos, medido em R (múltiplos do risco).",
        "checklist": [
            "Sei calcular expectativa = acerto × ganho médio − erro × perda média.",
            "Peço sempre o ganho médio e a perda média, não só o acerto.",
            "Sei que um método com 55% de acerto pode perder.",
            "Avalio resultado em R, não em pontos ou porcentagem solta.",
        ],
        "exercise": "Um método acerta 60%, ganha 0,5R quando acerta e perde 1R quando erra. Calcule a expectativa e diga se vale operar.",
        "required": True,
    },
    "Custos que somem com o resultado": {
        "summary": "Spread, slippage e comissão são cobrados em toda operação. Em alvos pequenos, eles decidem sozinhos se o método ganha ou perde.",
        "checklist": [
            "Sei a diferença entre spread, slippage e comissão.",
            "Comparo o custo total com o tamanho do alvo.",
            "Desconfio de backtest que não informa os custos usados.",
            "Sei que o spread muda conforme o horário.",
        ],
        "exercise": "Um setup tem alvo de US$ 2,00 e stop de US$ 2,00. Spread de US$ 0,30 e slippage de US$ 0,05 por lado. Quanto sobra do alvo e quanto cresce a perda?",
        "required": True,
    },
    "Backtest honesto: olhar o futuro sem perceber": {
        "summary": "Um backtest pode usar, sem querer, informação que ainda não existia no momento da decisão. O resultado fica bonito e é falso.",
        "checklist": [
            "Sei o que é look-ahead.",
            "Sei o que é repaint (sinal que muda depois).",
            "Confiro se o sinal é registrado no fechamento da barra.",
            "Desconfio de resultado bom demais e procuro o erro antes de comemorar.",
        ],
        "exercise": "Um indicador marca a seta no candle de 10:00, mas só sabe o fechamento às 10:05. Explique qual preço de entrada o backtest pode usar e por quê.",
        "required": True,
    },
    "Fora da amostra e pré-registro": {
        "summary": "Quem testa muitas variações acaba achando alguma que deu certo por sorte. A defesa é decidir a regra antes, testar em dados que ninguém olhou e corrigir pelo número de tentativas.",
        "checklist": [
            "Separo período de descoberta e período de confirmação.",
            "Escrevo a regra de aprovação antes de ver o resultado.",
            "Sei que testar 20 variações gera falsos positivos.",
            "Exijo que o resultado valha também no período recente.",
        ],
        "exercise": "Você testou 20 combinações de parâmetros e uma deu lucro. Liste o que faria antes de acreditar nela.",
        "required": True,
    },
    "Lendo promessas de sinais": {
        "summary": "Serviços de sinais costumam mostrar acerto alto, prints e selos. Um checklist simples separa evidência de marketing.",
        "checklist": [
            "Pergunto quem auditou e como.",
            "Pergunto o que conta como acerto.",
            "Peço expectativa em R depois de custos.",
            "Peço histórico completo, incluindo perdas e períodos ruins.",
        ],
        "exercise": "Escolha um anúncio de sinais que você já viu e aplique o checklist da aula. Quais perguntas ficaram sem resposta?",
        "required": True,
    },
    "64 regras testadas: o que reprovou e por quê": {
        "summary": "O OneB testou 64 regras clássicas de indicador (inclusive o Duck) em ouro, Nasdaq, S&P 500 e euro/dólar, com custo real e correção para múltiplos testes. Nenhuma sobreviveu. A maioria não tem vantagem nem antes do custo; a única com vantagem bruta perdeu força a partir de 2024.",
        "checklist": [
            "Sei que regra famosa não é regra lucrativa.",
            "Separo vantagem bruta (sem custo) de vantagem líquida.",
            "Sei por que testar muitas regras exige correção para múltiplos testes.",
            "Desconfio de efeito que só aparece num período.",
        ],
        "exercise": "Escolha um indicador que você já viu anunciado e escreva: qual seria a regra exata de entrada e saída, e que resultado com custo faria você aceitá-lo.",
        "required": True,
    },
    "Horário e spread: quando o custo come o movimento": {
        "summary": "O mesmo spread pesa diferente conforme a hora e o símbolo. No mapa de horários do OneB, o spread do US100.s consome menos de 1% do movimento típico da hora; o do US500.s, de 18% a 99%.",
        "checklist": [
            "Comparo o spread com o movimento típico da hora, não com o preço.",
            "Sei que hora parada não é hora segura: o custo pesa mais.",
            "Sei que hora agitada é hora de risco maior, não de oportunidade garantida.",
            "Calculo o lote pelo risco e confiro se o lote mínimo cabe.",
        ],
        "exercise": "Na aba Análise › Ativo, informe seu saldo e risco e anote o lote sugerido para Nasdaq e para ouro. Algum ficou abaixo do lote mínimo?",
        "required": True,
    },
    "Como conferir o OneB: placar, diário e o que não prometemos": {
        "summary": "Tudo o que o OneB afirma tem um placar: a previsão de amplitude e o plano das 10:30 são gravados antes do resultado e conferidos depois, dia a dia, inclusive os dias ruins.",
        "checklist": [
            "Sei onde ver o placar ao vivo e o diário (Análise › Por que confiar).",
            "Sei que a previsão diz QUANTO o mercado deve mexer, não PARA ONDE.",
            "Sei que o plano das 10:30 é regra fixa de compra e venda, não sinal.",
            "Confiro o saldo mínimo de cada ativo antes de operar (Análise › Quanto operar).",
            "Desconfio de qualquer serviço que não publica o placar completo, sinal a sinal, antes do resultado.",
        ],
        "exercise": "Abra Análise › Por que confiar e anote, do diário, quantos dos últimos pregões ficaram dentro da faixa prevista. Depois abra Quanto operar com o seu saldo real e anote quais ativos cabem.",
        "required": True,
    },
}

LESSON_BODIES: dict[str, str] = {
    "Acerto não é lucro": """\
Quase todo anúncio de sinal mostra a **taxa de acerto**: "82% de acerto", "9 em cada 10 operações no lucro". O número é verdadeiro e quase sempre irrelevante, porque ele não diz **quanto** se ganha quando acerta nem **quanto** se perde quando erra.

## A conta que importa

A medida certa é a **expectativa**, o resultado médio por operação:

- expectativa = acerto × ganho médio − erro × perda média

É mais fácil comparar métodos em **R**, o múltiplo do risco. Se você arrisca US$ 100 até o stop, 1R = US$ 100. Um trade que ganha US$ 50 rendeu +0,5R; um que bateu o stop rendeu −1R.

Exemplo: acerto de 70%, ganho médio de +0,3R e perda média de −1R.

- 0,70 × 0,3 − 0,30 × 1 = 0,21 − 0,30 = **−0,09R por operação**

O método acerta 7 em cada 10 e perde dinheiro.

## Um caso real testado pelo OneB

Testamos um indicador comprado de ouro, a "Caixa de Londres", em dados de março de 2019 a setembro de 2026, com spread e custos realistas:

- 1.164 operações, **55% de acerto**
- expectativa de **−0,068R** por operação
- todos os 8 anos-calendário terminaram negativos, somando cerca de −80R

Como pode acertar mais da metade e perder? Porque o ganho médio líquido foi só cerca de **70% da perda média**. Cada acerto pagava menos do que cada erro custava.

## Por que alvos curtos inflam o acerto

Um alvo pequeno é atingido com facilidade, então o acerto sobe. Mas o ganho de cada acerto também é pequeno. Num teste nosso, colocar um alvo de apenas US$ 1 no ouro fez uma estratégia perdedora "acertar" 81% das vezes. Quem só olha o acerto acha que encontrou um método excelente.

## Como usar isso

- Diante de qualquer método, peça **acerto, ganho médio e perda média**, ou a expectativa em R.
- Desconfie de acerto alto sem essas informações.
- Lembre que expectativa positiva pequena (+0,05R) ainda pode sumir com custos, que é o tema da próxima aula.
""",
    "Custos que somem com o resultado": """\
Todo trade paga três custos, mesmo quando a corretora diz "taxa zero":

- **Spread**: a diferença entre o preço de compra (ask) e o de venda (bid). Você compra mais caro e vende mais barato.
- **Slippage**: a diferença entre o preço que você planejou e o preço executado, principalmente em ordens a mercado e em movimentos rápidos.
- **Comissão**: o valor fixo ou por lote cobrado pela corretora.

## O custo não é fixo

O spread muda ao longo do dia. No ouro, ele costuma abrir na virada do dia do servidor e perto de notícias. Um backtest que usa um spread médio fixo esconde justamente os momentos em que o setup mais dispara.

## Um caso real testado pelo OneB

Reimplementamos um setup de rompimento falso no ouro (Gold Fakeout) e testamos em 2019 a 2026:

- com custos realistas: **−0,116R** por operação
- com custo zero: **+0,008R** por operação

Sem custos, o método empatava. Com custos, perdia. O setup não tinha vantagem nenhuma para "pagar" o spread.

## Regra prática

Compare o custo total de ida e volta com o tamanho do alvo:

- custo de 10% do alvo: o método precisa ser bom para sobreviver
- custo de 30% ou mais do alvo: quase nenhum método sobrevive

## Como usar isso

- Antes de operar um setup, estime o custo de ida e volta em dólares e em R.
- Prefira testar com o spread do horário em que o setup dispara, não com uma média.
- Se um backtest não diz quais custos usou, trate o resultado como sem custos.
""",
    "Backtest honesto: olhar o futuro sem perceber": """\
**Look-ahead** é usar, no teste, uma informação que ainda não existia no momento da decisão. É o erro mais comum em backtest e o mais perigoso, porque produz resultados bonitos.

## Como acontece

Um candle de 5 minutos que começa às 10:00 só tem fechamento conhecido às 10:05. Se o teste registra o sinal às 10:00 e entra no preço das 10:00, ele "sabia" como o candle ia terminar.

## O nosso próprio erro

Na primeira versão do teste do Gold Fakeout, o sinal ficava carimbado na **abertura** da barra, não no fechamento. A linha de base mostrou **+0,34R por operação**, um resultado excelente.

Ao corrigir o carimbo para o fechamento da barra, o ganho desapareceu. Os +0,34R eram inteiramente fruto do erro. Desde então, todo sinal do OneB é registrado no fechamento da barra, e um teste automático compara o replay com o modo ao vivo para garantir que os dois tomam as mesmas decisões.

## Repaint

**Repaint** é quando o indicador muda o sinal depois que ele apareceu: a seta some, muda de lugar ou o nível do stop é redesenhado. No gráfico histórico, só ficam os sinais "bons". Para descobrir, é preciso gravar o que o indicador mostrava **naquele momento**, não o que ele mostra hoje. Foi assim que testamos os indicadores comprados: gravando cada objeto desenhado, barra a barra, no testador do MetaTrader.

## Sinais de alerta

- resultado bom demais (acerto acima de 80% com alvo grande, curva de capital sem quedas)
- entrada no mesmo preço do candle que gerou o sinal
- indicador que "acerta tudo" no gráfico passado

## Como usar isso

- Pergunte em que momento o sinal fica conhecido e em que preço a entrada é possível.
- Quando o resultado parecer ótimo, procure o erro antes de comemorar.
""",
    "Fora da amostra e pré-registro": """\
Se você testar muitas variações de um método, alguma vai dar lucro por puro acaso. Isso se chama **excesso de ajuste** (overfitting). O resultado parece ótimo no passado e falha no futuro.

## Descoberta e confirmação

A defesa é separar os dados em dois períodos:

- **descoberta**: onde você explora e escolhe as variações
- **confirmação**: dados que ninguém olhou, usados **uma única vez** para confirmar

No laboratório do OneB, a descoberta usa 2019 a 2022 e a confirmação usa 2023 a 2026. A confirmação só roda para o que sobreviveu, e o resultado é definitivo.

## Corrigir pelo número de tentativas

Com 20 testes e um critério de 5%, espera-se em média 1 falso positivo. Por isso aplicamos correções estatísticas (Benjamini-Hochberg e Bonferroni) que exigem evidência mais forte quanto mais variações foram testadas.

## Pré-registro

**Pré-registrar** é escrever a regra de aprovação **antes** de ver o resultado: período, custos, critério de aprovação e o que acontece se reprovar. O arquivo fica travado com uma impressão digital (hash). Assim ninguém, nem nós, pode mudar a regra depois de ver o número.

Um exemplo real: no teste da Caixa de Londres, os níveis de entrada no nosso feed de dados ficaram, na mediana, US$ 0,43 diferentes da corretora, e a tolerância registrada era US$ 0,50. Com US$ 1,00, o teste teria passado nessa etapa. Não afrouxamos a regra depois de ver o resultado, e o teste foi classificado como só descritivo.

## Também vale para hoje

Um método que funcionou de 2019 a 2022 pode ter parado de funcionar. Exigimos que o resultado valha também na janela recente. Exemplo: no indicador 100 Pips, 2025 parecia positivo (+0,26R), mas o intervalo de confiança incluía zero e 2026 voltou para perto de zero. Era ruído.

## Como usar isso

- Desconfie de quem mostra só o melhor parâmetro.
- Pergunte quantas variações foram testadas e em que período o resultado foi confirmado.
""",
    "Lendo promessas de sinais": """\
Serviços de sinais vendem confiança: acerto alto, prints de lucro, selos de "auditado". Este checklist ajuda a separar evidência de marketing.

## As perguntas

- **Quem auditou?** "Auditado" sem nome de auditor, método e relatório não é auditoria.
- **O que conta como acerto?** Se atingir o primeiro alvo (TP1) já conta como acerto, o número fica inflado: o TP1 costuma ser curto e o resto da operação pode terminar no stop.
- **Qual a expectativa em R depois de custos?** Sem isso, o acerto não diz nada.
- **Qual o histórico completo?** Peça todas as operações, inclusive perdas e meses ruins, com data e hora em que o sinal foi enviado.
- **Desde quando existe?** Um serviço novo não tem histórico suficiente para provar nada.
- **Quem é a empresa?** Razão social, CNPJ e responsável identificável.

## O que encontramos ao aplicar o checklist

Aplicamos essas perguntas a um serviço de sinais anunciado como "auditado". O site não nomeava o auditor, contava o TP1 como acerto e o domínio tinha poucos meses. Nos nossos próprios dados, um alvo curto o bastante produz **81% de "acerto" numa estratégia que perde dinheiro**.

## O que o OneB faz diferente

- mostra a expectativa em R, o intervalo de confiança e o número de operações
- mostra o veredito mesmo quando é ruim (arquivado, descritivo, degradado)
- não chama de recomendação o que ainda está em pesquisa

## Exercício mental

Se um serviço mostrasse "90% de acerto em 30 dias", quais três perguntas você faria antes de acreditar? Escreva-as nas anotações da aula.
""",
}


# ---- Primeiros passos (módulo inicial da trilha de fundamentos) ----

MODULE_PRIMEIROS_PASSOS = (
    "Primeiros passos",
    [
        ("Abrindo uma conta demo no MetaTrader 5", "Conta de demonstração, a tela do MT5 e cuidados antes de escolher corretora.", 15),
        ("Seu primeiro trade no laboratório", "Planejar, executar e revisar uma operação no simulador do OneB.", 15),
    ],
)

MATERIAL_PRIMEIROS_PASSOS: dict[str, dict] = {
    "Abrindo uma conta demo no MetaTrader 5": {
        "summary": "A conta demo usa dinheiro fictício com as cotações da corretora. Serve para aprender a plataforma sem risco; não serve para provar que uma estratégia funciona.",
        "checklist": [
            "Sei a diferença entre conta demo e conta real.",
            "Conferi se a corretora é autorizada a atender no Brasil.",
            "Encontrei bid, ask, spread e a especificação do contrato.",
            "Sei abrir uma ordem com stop e alvo na conta demo.",
        ],
        "exercise": "Abra uma conta demo, encontre a especificação do ativo que você quer estudar e anote: tamanho do contrato, spread típico e horário de negociação.",
        "required": True,
    },
    "Seu primeiro trade no laboratório": {
        "summary": "O laboratório do OneB reproduz dias reais e pausa nos momentos de decisão. O objetivo é treinar o processo: plano antes, execução sem improviso e revisão depois.",
        "checklist": [
            "Escrevi entrada, stop e alvo antes de clicar.",
            "Usei o risco por operação para calcular a quantidade.",
            "Revisei o resultado em R, não só em dólares.",
            "Repeti em mais de um dia antes de tirar conclusão.",
        ],
        "exercise": "Faça três operações no replay “Nasdaq: dia lateral” e anote, para cada uma, o motivo da entrada e se o plano foi seguido.",
        "required": True,
    },
}

LESSON_BODIES.update({
    "Abrindo uma conta demo no MetaTrader 5": """\
O **MetaTrader 5 (MT5)** é a plataforma usada por muitas corretoras de CFD, forex e índices. Antes de colocar dinheiro, todo aluno deve passar pela **conta demo**: dinheiro fictício, cotações da própria corretora e nenhum risco.

## Demo serve para aprender, não para provar

Na demo não há medo, a execução costuma ser melhor que na conta real e o tamanho não pesa no bolso. Use a demo para aprender a plataforma. Para saber se uma estratégia funciona, o caminho é teste com custos e fora da amostra, como na trilha "Como avaliar um sinal".

## Antes de escolher a corretora

- Verifique se a empresa é autorizada a oferecer o produto a residentes no Brasil. A CVM publica alertas sobre empresas estrangeiras que oferecem forex e CFDs sem autorização.
- Leia quanto custam o spread, a comissão e o **swap** (custo de manter a posição de um dia para o outro).
- Desconfie de "gerente de conta" que liga oferecendo sinais, bônus ou acesso remoto ao seu computador.

## Passo a passo da conta demo

- Baixe o MT5 no site oficial (metatrader5.com) ou no site da corretora. Há versão para computador e para celular.
- No MT5 do computador, abra o menu **Arquivo → Abrir uma conta**.
- Digite o nome da corretora, escolha o servidor de **demonstração** e marque a opção de conta demo.
- Preencha os dados, escolha o depósito fictício e conclua. Anote **login, senha e servidor**; a plataforma mostra esses dados uma vez.

## A tela em 4 partes

- **Observação do mercado**: a lista de ativos com **bid** (preço de venda) e **ask** (preço de compra). A diferença é o spread.
- **Gráfico**: candles do ativo selecionado, com o tempo gráfico escolhido no topo.
- **Nova ordem** (tecla F9): volume, tipo de ordem, **stop loss** e **take profit**.
- **Caixa de ferramentas**, aba Negociação: posições abertas, lucro ou prejuízo e saldo.

Clique com o botão direito num ativo e escolha **Especificação**: ali estão o tamanho do contrato, o spread, o swap e o horário de negociação. Leia antes de operar qualquer ativo.

## Segurança

- Nunca passe sua senha a ninguém, nem para "ajudar a operar".
- Ative a verificação em duas etapas se a corretora oferecer.
- Ninguém sério promete retorno garantido.

O laboratório do OneB usa o mesmo vocabulário do MT5 (bid, ask, stop e alvo), então o que você treinar aqui vale lá.
""",
    "Seu primeiro trade no laboratório": """\
O **Laboratório** da Academia é um simulador com conta fictícia de US$ 10.000. Ele tem dois modos:

- **Replay guiado**: um dia real passa barra a barra, como um vídeo, e para sozinho quando é hora de decidir.
- **Ao vivo**: o mercado de agora, com cotação de 1 minuto e atraso de até 15 minutos.

Ele segue as mesmas regras da pesquisa do OneB: compra no ask, venda no bid, e se o stop e o alvo cabem no mesmo candle, conta o stop.

## Roteiro do primeiro trade

- Abra o replay **"Nasdaq: dia lateral"** e aperte play.
- Quando o replay pausar depois dos primeiros 30 minutos, **escreva o plano** nas anotações: vou comprar ou vender? Onde é o stop? Onde é o alvo? O que me faria não operar?
- Preencha o stop e o alvo na boleta e deixe o risco em 1%. A quantidade é calculada pelo risco até o stop.
- Clique em Comprar ou Vender e deixe o replay seguir. Não mexa no stop.
- No fim, olhe o placar em **R**: +1R é ganhar o que você arriscou; −1R é perder o que arriscou.

## O que observar

- O primeiro rompimento do dia lateral é um bom teste de paciência.
- Uma operação só não diz nada. Repita em vários dias antes de concluir qualquer coisa.
- Se o placar mostrar acerto alto e expectativa negativa, você encontrou na prática a aula "Acerto não é lucro".

## Do laboratório para a conta demo

Depois de cinco ou mais replays com o plano escrito, faça o mesmo roteiro na conta demo do MT5. O objetivo é que o processo seja igual nos dois lugares.
""",
})

from app.lms_bodies_core import CORE_BODIES  # noqa: E402

LESSON_BODIES.update(CORE_BODIES)
from app.lms_bodies_tecnica import PROCESSO_BODIES, TECNICA_BODIES  # noqa: E402

LESSON_BODIES.update(TECNICA_BODIES)
LESSON_BODIES.update(PROCESSO_BODIES)
from app.lms_track_macro import BODIES_MACRO  # noqa: E402

LESSON_BODIES.update(BODIES_MACRO)


LESSON_BODIES.update({
    "64 regras testadas: o que reprovou e por quê": """\
Internet e cursos estão cheios de regras de indicador: cruzamento de médias, RSI, Bollinger, rompimento da abertura, e indicadores vendidos prontos como o Duck. O OneB fez o teste que quase ninguém mostra: **todas de uma vez, com custo real e com as regras decididas antes de olhar o resultado**.

## Como foi o teste

- **8 famílias × 2 variações × 4 ativos = 64 regras**: Tartarugas (Donchian), médias, Bollinger, RSI(2), squeeze, rompimento da abertura, momentum da última hora e Duck (SMA 60 no H4 e no H1 dando a direção e entrada no cruzamento do M5).
- **Ativos**: ouro, Nasdaq, S&P 500 e euro/dólar, velas de 5 minutos.
- **Descoberta só em 2019-2022.** O período de 2023 a 2026 ficou guardado para confirmar quem passasse.
- **Custo real**: spread de cada barra, slippage e comissão.
- **Correção para múltiplos testes**: com 64 tentativas, algumas parecem boas por sorte. A correção desconta isso.

## O resultado

- **Nenhuma das 64 sobreviveu.** Só 4 ficaram positivas, todas perto de zero (no máximo +0,009R por trade).
- **O Duck foi negativo nos 4 ativos**, de −0,08R a −0,38R por trade.
- **Sem custo nenhum**, a regra típica ainda dá cerca de −0,02R: a maioria não tem vantagem nem antes do spread. O custo tira mais uns 0,10R.

## A única exceção, e por que ela também caiu

O **momentum da última hora** (a direção do dia até as 15h de Nova York decide a última hora) tinha vantagem bruta de +0,11R no Nasdaq, como diz o artigo acadêmico de Gao e coautores (2018). Testamos de novo, só em 2023-2026 e com o custo real da corretora:

| Ano | R por trade |
|---|---|
| 2023 | +0,06 |
| 2024 | −0,05 |
| 2025 | −0,08 |
| 2026 | −0,06 |

A vantagem sumiu depois de ficar conhecida. Isso é comum: quando muita gente usa a mesma regra, o ganho vai embora.

## O que levar daqui

- Regra famosa não é regra lucrativa. Quem vende indicador raramente mostra o teste com custo.
- Separe **vantagem bruta** de **vantagem líquida**: o spread decide.
- Um resultado bom em um período só pode ser sorte ou um efeito que já acabou.
- O que **tem** evidência no OneB é medir risco: calendário, volatilidade, custo e tamanho de posição.
""",
    "Horário e spread: quando o custo come o movimento": """\
O spread parece pequeno: alguns décimos de ponto. Mas o que importa é **quanto ele pesa perto do movimento que você quer capturar**. O OneB mediu isso hora a hora, em 2 anos de velas de 5 minutos.

## O mapa de horários

Na aba **Análise › Horários**, cada quadrado é uma hora de um dia útil (horário de Brasília):

- **Movimento**: quanto aquela hora costuma mexer comparada à hora média do ativo (1,0x = normal).
- **Custo do spread**: quanto do movimento típico da hora o spread da corretora consome, na entrada e na saída.

No Nasdaq, a hora mais agitada é das **10h às 11h de Brasília**, logo depois da abertura de Nova York, com até **2,7 vezes** o movimento típico. A madrugada mexe metade do normal.

## O mesmo trade, 25 vezes mais caro

| Símbolo (HonorPro) | Spread | Peso no movimento da hora |
|---|---|---|
| US100.s (Nasdaq) | 0,7 ponto | menos de 1% |
| US500.s (S&P 500) | 5,3 pontos | de 18% a 99% |

Os dois índices andam juntos, mas o custo não. Em proporção ao preço, operar o S&P nessa corretora custa cerca de **25 vezes mais**. Nas regras do laboratório, foi isso que deixou o S&P sempre pior.

## Duas armadilhas

- **Hora parada parece segura, mas o custo pesa mais**, porque o movimento é pequeno e o spread é o mesmo.
- **Hora agitada não é oportunidade garantida.** É risco maior: o stop é atingido com mais facilidade.

## Quanto operar

Na aba **Análise › Quanto operar**, a calculadora faz a conta pelo risco, para todos os ativos de uma vez:

- **lote = (saldo × risco %) ÷ (distância do stop × tamanho do contrato)**, arredondado para baixo;
- ela mostra o custo do spread daquele lote e **avisa quando nem o lote mínimo cabe no seu risco**.

Exemplo: com US$ 1.000 e 1% de risco (US$ 10), um stop de 150 pontos no US100.s arrisca US$ 15 mesmo com o lote mínimo (0,1). A resposta honesta é: **com esse saldo, esse trade não cabe**. A corretora pode mudar o lote mínimo sem aviso; o OneB confere a especificação no MT5.
""",
    "Como conferir o OneB: placar, diário e o que não prometemos": """\
Qualquer serviço pode dizer que acerta. A diferença está em **mostrar o placar completo, com regra definida antes do resultado**. Esta aula mostra onde o OneB faz isso e como você confere sozinho.

## 1. O que é comprovado (e o que não é)

- **Quanto o mercado deve mexer no próximo pregão.** Testado em 2023 a 2026, anos que o modelo nunca viu: erra menos que a média de 14 dias (o ATR), e a faixa de 80% acerta perto de 8 em cada 10 dias.
- **Quanto os eventos mexem.** CPI, payroll e FOMC multiplicam o movimento da primeira meia hora; o OneB avisa antes.
- **A chance real de cada alvo do plano**, medida em milhares de entradas, já com o spread.
- **Direção não.** Nenhuma regra de compra ou venda passou nos testes: indicadores, tendência, horário, nem regras "sem indicador" como as de serviços de sinais. Por isso a IA não diz "compre" ou "venda".

## 2. O placar ao vivo

Todo pregão, a previsão do dia seguinte é **gravada no banco antes do pregão começar** e não muda mais. Depois que o pregão fecha, o OneB compara com o que aconteceu. Na aba **Análise › Ativo** você vê, pregão a pregão, o previsto, a faixa, o realizado e se a previsão foi gravada antes.

O mesmo vale para o **plano das 10:30**: todo dia útil, às 10:30 de Brasília, o OneB registra por regra fixa um plano de compra e um de venda (stop de 1,5 ATR de 1 hora, alvos de 1R, 2R e 3R) e confere se cada alvo veio antes do stop. Ninguém escolhe o dia, a direção ou o resultado.

> Num dia, um lado bate o alvo e o outro bate o stop. Isso é esperado: o que o placar confere é se a **chance anunciada** de cada alvo se confirma ao longo de muitos dias.

## 3. O diário

Em **Análise › Por que confiar**, o diário junta, dia a dia, o que foi registrado antes e o que aconteceu. **Os dias ruins aparecem do mesmo jeito que os bons**: um pregão de CPI que passou da faixa fica marcado com ✗, sem filtro.

## 4. Quanto a sua conta aguenta

Em **Análise › Quanto operar**, informe o saldo da sua conta no MT5 e o risco por operação. O OneB mostra:

- se o **menor lote** de cada ativo cabe no seu risco;
- o lote certo e o risco real em dólar;
- quanto o **spread** come do stop (acima de 10%, o custo é alto);
- o **saldo mínimo** para operar cada ativo.

Se nem o menor lote cabe, a resposta honesta é **não operar esse ativo com esse saldo**.

## 5. O teste que você pode fazer com qualquer serviço

Antes de pagar por sinais, peça:

1. o **resultado médio por trade** já descontando o spread (não a "taxa de acerto");
2. o **histórico completo, sinal a sinal, publicado antes do resultado**;
3. a comparação com **entrar no cara ou coroa** com as mesmas regras.

O OneB fez esse teste: com o alvo curto, entradas aleatórias chegam a 80% a 90% de "acerto" e mesmo assim perdem dinheiro.
""",
})
