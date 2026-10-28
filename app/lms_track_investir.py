"""Trilha "Investir no Brasil": para quem nunca investiu, ligada à seção Brasil do app.

Números citados foram medidos em 28/10/2026 com dados do Banco Central (SGS) e do Yahoo
(Ibovespa de retorno total) pelos módulos app/brasil/market.py e app/brasil/events.py.
Regras de IR e FGC conferidas em 10/2026. Se a lei ou os números mudarem, revisar.
"""
from __future__ import annotations

TRACK_INVESTIR = (
    "investir-no-brasil",
    "Investir no Brasil",
    "Do zero à primeira carteira: reserva, renda fixa, imposto, bolsa e os eventos que mexem com o mercado brasileiro.",
    [
        (
            "Primeiros passos",
            [
                ("Todo mundo pode investir", "Juros compostos, começar com pouco e por que a poupança fica para trás.", 10),
                ("Reserva de emergência primeiro", "Quanto guardar, onde deixar e por que ela vem antes de tudo.", 9),
            ],
        ),
        (
            "Renda fixa sem mistério",
            [
                ("Selic, CDI e IPCA: as três taxas que importam", "O que cada uma mede e como elas definem quanto seu dinheiro rende.", 11),
                ("Tesouro, CDB, LCI e LCA: como escolher", "Comparar taxa, prazo, liquidez e garantia sem cair em armadilha.", 12),
                ("Imposto de renda e FGC na prática", "Tabela regressiva, isenções e o limite de R$ 250 mil.", 10),
            ],
        ),
        (
            "Bolsa com os pés no chão",
            [
                ("Ações, ETFs e FIIs", "Ser sócio de empresas e receber aluguel de imóveis com pouco dinheiro.", 12),
                ("Eleição, Copom e eventos: o que mexe na bolsa", "Quanto o Ibovespa se move nesses dias, medido em 10 anos.", 12),
                ("Diversificar e não vender na queda", "Bolsa x CDI em 10 anos e o erro que mais custa ao investidor.", 11),
            ],
        ),
    ],
)

MATERIAL_INVESTIR: dict[str, dict] = {
    "Todo mundo pode investir": {
        "summary": "Investir não exige muito dinheiro: o Tesouro Selic começa com cerca de R$ 150 e muitos CDBs com R$ 1. O que faz diferença é a constância e o tempo, por causa dos juros compostos.",
        "checklist": ["Sei o que são juros compostos.", "Sei que posso começar com pouco.", "Comparei a poupança com o CDI.", "Defini um valor mensal que cabe no meu orçamento."],
        "exercise": "No Simulador da seção Brasil, coloque R$ 0 de valor inicial e R$ 100 por mês por 10 anos. Anote quanto daria na poupança e na divisão sugerida, e a diferença.",
        "required": True,
    },
    "Reserva de emergência primeiro": {
        "summary": "A reserva de emergência (em geral 6 meses de gastos) fica em investimento seguro com resgate no mesmo dia. Ela evita que um imprevisto obrigue você a vender outro investimento no prejuízo ou a pegar empréstimo caro.",
        "checklist": ["Calculei meus gastos mensais.", "Sei o tamanho da minha reserva (6 meses).", "Sei onde deixar: Tesouro Selic ou CDB de liquidez diária.", "Não coloco a reserva em bolsa nem em LCI/LCA com carência."],
        "exercise": "Some seus gastos de um mês típico, multiplique por 6 e veja no Simulador (objetivo: reserva de emergência) em quantos meses você chega lá.",
        "required": True,
    },
    "Selic, CDI e IPCA: as três taxas que importam": {
        "summary": "A Selic é a taxa básica definida pelo Copom. O CDI anda colado nela e é a referência dos CDBs. O IPCA mede a inflação. Rendimento bom é o que fica acima do IPCA depois do imposto.",
        "checklist": ["Sei quem define a Selic e de quanto em quanto tempo.", "Sei que o CDI fica quase igual à Selic.", "Sei o que é ganho real (acima da inflação).", "Encontrei as taxas atuais na seção Brasil."],
        "exercise": "Na aba Começar da seção Brasil, anote a Selic, o CDI e o IPCA de hoje e calcule o ganho real aproximado do CDI.",
        "required": True,
    },
    "Tesouro, CDB, LCI e LCA: como escolher": {
        "summary": "Cada produto de renda fixa tem uma função: Tesouro Selic e CDB de liquidez diária para a reserva; LCI/LCA para dinheiro parado por mais de um ano; prefixado e IPCA+ para objetivos com data.",
        "checklist": ["Comparo produtos depois do IR.", "Confiro a liquidez antes de aplicar.", "Sei que prefixado e IPCA+ oscilam se eu vender antes.", "Escolho vencimento perto da data do objetivo."],
        "exercise": "Compare um CDB de 100% do CDI com uma LCI de 90% do CDI para 2 anos: qual rende mais depois do imposto?",
        "required": True,
    },
    "Imposto de renda e FGC na prática": {
        "summary": "Na renda fixa, o IR cai com o tempo: 22,5% até 180 dias e 15% depois de 2 anos, só sobre o lucro. Poupança, LCI e LCA são isentas. O FGC devolve até R$ 250 mil por CPF e por instituição se o banco quebrar.",
        "checklist": ["Sei as quatro faixas da tabela regressiva.", "Sei quais produtos são isentos.", "Sei que o IR é só sobre o lucro.", "Respeito o limite do FGC por instituição."],
        "exercise": "Você lucrou R$ 1.000 num CDB em 1 ano e meio. Quanto paga de IR? E se fosse uma LCA?",
        "required": True,
    },
    "Ações, ETFs e FIIs": {
        "summary": "Ação é um pedaço de uma empresa. ETF é uma cesta de ações comprada de uma vez. FII é um fundo de imóveis que paga aluguel mensal. Para começar, ETFs e FIIs diversificados reduzem o risco de depender de uma empresa só.",
        "checklist": ["Sei a diferença entre ação, ETF e FII.", "Sei que renda variável pode cair 30% ou mais.", "Sei que ETF paga 15% de IR sem a isenção de R$ 20 mil.", "Desconfio de dividendo alto demais."],
        "exercise": "Na aba Bolsa da seção Brasil, escolha um ETF e um FII e anote o retorno em 12 meses, a maior queda e os dividendos. O que esses números dizem sobre o risco?",
        "required": True,
    },
    "Eleição, Copom e eventos: o que mexe na bolsa": {
        "summary": "Alguns dias movem a bolsa muito mais que outros. Nos últimos 10 anos, o pregão depois de cada turno de eleição moveu o Ibovespa cerca de 6 vezes mais que um dia comum. O Copom move pouco a mais. Ninguém sabe a direção antes.",
        "checklist": ["Sei quais eventos mexem com a B3.", "Sei que eleição é o evento de maior movimento.", "Não tento adivinhar a direção do resultado.", "Olho a agenda de eventos antes de aplicar ou resgatar."],
        "exercise": "Na aba Eventos da seção Brasil, veja os próximos 3 eventos e escreva o que você faria (ou não faria) com sua carteira em cada um.",
        "required": True,
    },
    "Diversificar e não vender na queda": {
        "summary": "Em 10 anos (até 09/2026), R$ 1.000 viraram cerca de R$ 3.193 no Ibovespa e R$ 2.443 no CDI. Mas em 5 anos o CDI ganhou da bolsa. Diversificar e manter o plano nas quedas é o que transforma oscilação em resultado.",
        "checklist": ["Sei que bolsa pode perder do CDI por anos.", "Divido o dinheiro por função (segurança, inflação, crescimento).", "Tenho regra para não vender no susto.", "Reviso a carteira uma vez por ano, não todo dia."],
        "exercise": "Escreva sua regra pessoal para uma queda de 20% na bolsa: o que você faz e o que não faz?",
        "required": True,
    },
}

BODIES_INVESTIR: dict[str, str] = {
    "Todo mundo pode investir": """\
Investir é deixar o dinheiro trabalhar por você. Não é coisa de rico: dá para começar com R$ 1 em muitos CDBs e com cerca de R$ 150 no Tesouro Selic.

## Juros compostos

O rendimento de um mês passa a render no mês seguinte. No começo parece pouco; com o tempo, o rendimento passa a ser maior que o próprio aporte.

- R$ 100 por mês durante 10 anos são **R$ 12.000** aplicados.
- Com o CDI de outubro de 2026 (13,65% ao ano), isso vira mais de R$ 24 mil antes do IR.
- Na poupança (6,17% ao ano hoje), fica perto de R$ 16,4 mil.

## Por que a poupança fica para trás

Quando a Selic passa de 8,5% ao ano, a poupança fica travada em 0,5% ao mês. Com a Selic em 13,75%, o Tesouro Selic e um CDB de 100% do CDI rendem bem mais, **mesmo depois do imposto**, com a mesma segurança.

## O que importa de verdade

- **Constância**: aporte todo mês, de preferência no dia do salário.
- **Tempo**: quanto antes começar, mais os juros compostos trabalham.
- **Simplicidade**: começar com o básico bem feito vale mais que buscar a aplicação "perfeita".

Use o **Simulador** da seção Brasil para ver o seu caso.
""",
    "Reserva de emergência primeiro": """\
A reserva de emergência é o dinheiro para o imprevisto: perder o emprego, uma conta de saúde, o carro quebrado. Ela vem **antes** de qualquer investimento que oscile.

## Quanto guardar

- A regra mais usada é **6 meses de gastos** (não de salário).
- Quem tem renda instável (autônomo, comissão) pode mirar 9 a 12 meses.

## Onde deixar

Precisa de duas coisas: **segurança** e **resgate no mesmo dia**.

- **Tesouro Selic**: risco do governo federal, resgate em dia útil.
- **CDB de liquidez diária com 100% do CDI**: coberto pelo FGC até R$ 250 mil por banco.

## Onde NÃO deixar

- **Bolsa**: a emergência costuma chegar justo quando o mercado está em queda.
- **LCI/LCA**: têm carência de 9 a 12 meses.
- **Tesouro prefixado ou IPCA+**: o preço oscila se você vender antes do vencimento.

## Por que isso aumenta o seu rendimento

Sem reserva, um imprevisto obriga você a vender outro investimento na pior hora ou a pagar juros de cartão. Com reserva, o resto da carteira pode ficar quieto e render.
""",
    "Selic, CDI e IPCA: as três taxas que importam": """\
Três números explicam quase tudo na renda fixa brasileira.

## Selic

É a taxa básica de juros, definida pelo **Copom** do Banco Central a cada cerca de 45 dias (8 reuniões por ano). Em outubro de 2026 estava em **13,75% ao ano**, depois de cortes seguidos ao longo do ano.

## CDI

É a taxa dos empréstimos de um dia entre bancos. Anda colada na Selic (13,65% em outubro de 2026). Quando um CDB paga "100% do CDI", ele rende o mesmo que essa taxa.

## IPCA

É a inflação oficial, medida pelo IBGE. Em 12 meses até setembro de 2026: **4,58%**.

## Ganho real

O que importa é quanto o dinheiro cresce **acima da inflação**:

- ganho real ≈ (1 + taxa) ÷ (1 + inflação) − 1;
- com CDI de 13,65% e IPCA de 4,58%: cerca de **8,7% ao ano** de ganho real antes do IR.

Esse ganho real é alto para padrões mundiais. Ele não dura para sempre: quando a Selic cai, a renda fixa pós-fixada passa a render menos. Por isso vale travar parte do dinheiro em IPCA+ ou prefixado para objetivos longos.

As taxas atualizadas ficam na aba **Começar** da seção Brasil, direto do Banco Central.
""",
    "Tesouro, CDB, LCI e LCA: como escolher": """\
Na renda fixa, a pergunta certa não é "qual rende mais", e sim "para quê é esse dinheiro".

## Para a reserva e o curto prazo

- **Tesouro Selic** e **CDB de liquidez diária (100% do CDI ou mais)**.

## Para dinheiro parado por mais de 1 ano

- **LCI e LCA**: isentas de IR, cobertas pelo FGC, com carência de 9 a 12 meses.
- Compare depois do imposto: 90% do CDI isento equivale a cerca de **106% a 116% do CDI** de um CDB, conforme o prazo.

## Para objetivo com data

- **Tesouro Prefixado**: você sabe quanto terá no vencimento.
- **Tesouro IPCA+**: garante ganho acima da inflação, bom para prazos longos e aposentadoria.
- Os dois **oscilam** se você vender antes. A taxa contratada só vale levando até o fim, então escolha o vencimento perto da data do objetivo.

## Armadilhas comuns

- CDB de banco pequeno pagando muito acima do CDI: o risco é maior e o FGC tem limite.
- Comparar taxa bruta com taxa isenta sem descontar o IR.
- Ignorar a liquidez e precisar do dinheiro antes da carência.
""",
    "Imposto de renda e FGC na prática": """\
## Tabela regressiva (CDB, Tesouro, fundos de renda fixa)

O IR incide **só sobre o lucro**, cobrado no resgate e pela idade de cada aplicação:

| Prazo | Alíquota |
|---|---|
| até 180 dias | 22,5% |
| 181 a 360 dias | 20% |
| 361 a 720 dias | 17,5% |
| acima de 720 dias | 15% |

Resgates em menos de 30 dias também pagam **IOF**, que diminui dia a dia até zerar.

## Isentos para pessoa física

- Poupança, LCI, LCA, CRI e CRA.
- Rendimentos mensais de FIIs (regra atual; a venda das cotas com lucro paga 20%).

## Renda variável

- Ações: 15% sobre o lucro, mas vendas de até **R$ 20 mil por mês** em ações são isentas.
- ETFs: 15% sobre o lucro, **sem** a isenção de R$ 20 mil.

## FGC

O Fundo Garantidor de Créditos devolve até **R$ 250 mil por CPF e por instituição** se o banco quebrar (teto global de R$ 1 milhão a cada 4 anos). Cobre poupança, CDB, LCI e LCA. **Não** cobre Tesouro Direto (que tem a garantia do governo), ações, FIIs e fundos.

O Simulador da seção Brasil já desconta o IR de cada aporte pela sua idade.
""",
    "Ações, ETFs e FIIs": """\
## Ação

Um pedaço de uma empresa. Você ganha se a empresa cresce (valorização) e quando ela distribui lucro (dividendos). Uma empresa sozinha pode ir muito mal: em 12 meses até outubro de 2026, entre as ações mais negociadas, houve alta de mais de 90% e quedas de mais de 15%.

## ETF

Uma cesta de ações comprada numa cota só. Um ETF do Ibovespa tem dezenas de empresas. Para quem começa, é o jeito mais simples de ter bolsa sem depender de acertar empresa.

## FII (fundo imobiliário)

Cotas de fundos donos de galpões, shoppings, escritórios ou de títulos de crédito imobiliário. Pagam rendimento todo mês, hoje isento de IR para pessoa física.

- Rendimento muito acima dos outros costuma vir com risco maior.
- Fundos grandes e diversificados, ou um ETF de FIIs, diluem o risco de um imóvel vazio.

## O que esperar

- Renda variável **oscila**: quedas de 20% a 30% acontecem com alguma frequência.
- O prazo mínimo razoável é de **5 anos**.
- Só entra dinheiro que não é da reserva.

Na aba **Bolsa** da seção Brasil você vê retorno, maior queda, volatilidade e dividendos dos ativos mais negociados. É uma lista para estudo, não uma indicação de compra.
""",
    "Eleição, Copom e eventos: o que mexe na bolsa": """\
O OneB mediu, com 10 anos de dados do Ibovespa (de 2016 a outubro de 2026), quanto o índice se move no pregão que reage a cada tipo de evento. É uma medida do **tamanho** do movimento, não da direção.

## Dia comum

O Ibovespa se move em média **cerca de 1%** por dia (para cima ou para baixo).

## Copom

O Copom anuncia a Selic depois do fechamento; a bolsa reage no dia seguinte. Em 79 reuniões, o movimento médio foi **1,2%**: só um pouco acima do normal. O mercado costuma antecipar a decisão.

## Eleições

O pregão depois de cada turno de eleição foi, de longe, o mais agitado:

| Eleição | Movimento no pregão seguinte |
|---|---|
| 2018 · 1º turno | +4,6% |
| 2018 · 2º turno | −2,2% |
| 2022 · 1º turno | +5,5% |
| 2022 · 2º turno | +1,3% |
| 2026 · 1º turno | +7,7% |
| 2026 · 2º turno | −13,9% |

Média de **5,9%** em módulo, cerca de **6 vezes** um dia comum. A direção mudou de eleição para eleição.

## Outros eventos

- **IPCA** (por volta do dia 10): muda a expectativa para a Selic.
- **Fed** (juros dos EUA): mexe no dólar e no dinheiro estrangeiro na B3.
- **Temporada de balanços**: cada empresa oscila mais no dia do resultado.

## Como usar isso

- Para quem investe a longo prazo, o principal é **não tomar decisão no susto** desses dias.
- Se você precisa de um dinheiro numa data próxima a uma eleição, ele não deveria estar em bolsa.
- A agenda atualizada fica na aba **Eventos** da seção Brasil.
""",
    "Diversificar e não vender na queda": """\
## Bolsa x CDI: o que os números mostram

R$ 1.000 aplicados até setembro de 2026 (antes de IR):

| Período | CDI | IPCA | Ibovespa | Poupança |
|---|---|---|---|---|
| 1 ano | R$ 1.145 | R$ 1.046 | R$ 1.274 | R$ 1.083 |
| 5 anos | R$ 1.813 | R$ 1.295 | R$ 1.679 | R$ 1.452 |
| 10 anos | R$ 2.443 | R$ 1.623 | R$ 3.193 | R$ 1.789 |

Em 5 anos, o CDI ganhou da bolsa. Em 10 anos, a bolsa ganhou. Ninguém sabia antes qual período seria qual. E em outubro de 2026 o Ibovespa caiu cerca de 14% em um único pregão depois da eleição.

## Diversificar

Dividir o dinheiro por função reduz a chance de tudo ir mal ao mesmo tempo:

- **segurança**: Tesouro Selic, CDB;
- **inflação**: Tesouro IPCA+;
- **crescimento**: ETFs de ações brasileiras e de fora, FIIs.

## O erro que mais custa

Vender depois de uma queda transforma uma oscilação em perda definitiva e costuma deixar você de fora da recuperação. Antes de investir em bolsa, escreva o que você vai fazer numa queda de 20%. Se a resposta for "vender", a parte de bolsa deve ser pequena, e o Simulador leva isso em conta.

## Rotina

- Aporte todo mês.
- Uma vez por ano, veja se a divisão ainda está parecida com a planejada e corrija **com os aportes novos**.
""",
}
