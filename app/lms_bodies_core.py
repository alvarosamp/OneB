"""Texto das aulas de Fundamentos e de Gestão de risco (chaves = títulos do seed, sem acento).

Mesmo formato de app/lms_content.LESSON_BODIES. Afirmações de mercado ficam no
nível do que é verificável; regras práticas aparecem como regras do processo,
não como "o que o mercado faz".
"""
from __future__ import annotations

CORE_BODIES: dict[str, str] = {
    "Como funciona a NASDAQ": """\
A **Nasdaq** é uma bolsa americana totalmente eletrônica, onde negociam empresas como Apple, Microsoft e Nvidia. Quando se fala em "Nasdaq" no dia a dia, quase sempre se fala do **Nasdaq-100**, o índice das 100 maiores empresas não financeiras listadas nela.

## Horário

- **Pregão regular**: 9:30 às 16:00 de Nova York. Em Brasília, normalmente 10:30 às 17:00 durante o horário de verão americano e 11:30 às 18:00 fora dele.
- **Pré e pós-mercado**: existem negociações antes e depois, com menos liquidez e spreads maiores.
- Os **futuros** do índice (NQ) e os CFDs negociam quase 24 horas em dias úteis, com uma pausa diária.

## Ação, ETF, índice e futuro

- **Ação**: uma fração de uma empresa.
- **Índice**: uma conta que resume várias ações. Não se compra o índice diretamente.
- **ETF**: um fundo negociado em bolsa que replica um índice. O **QQQ** replica o Nasdaq-100.
- **Futuro / CFD**: contratos que acompanham o preço do índice. Têm alavancagem, custos de manutenção e regras próprias.

## Dados com atraso

Cotações gratuitas costumam ter **atraso de até 15 minutos** e podem falhar. O OneB mostra a idade do dado; antes de decidir, confira se o preço é recente.

## Como usar isso

- Saiba qual instrumento você está olhando: QQQ, NQ e um CFD de "US100" andam juntos, mas têm custos e horários diferentes.
- Comece com poucos ativos líquidos.
""",
    "Ordens, corretoras e custos": """\
Toda operação paga custos, mesmo quando a propaganda diz "taxa zero".

## Tipos de ordem

- **A mercado**: executa já, no melhor preço disponível. Rápida, mas sujeita a slippage.
- **Limitada**: executa só no preço que você definiu ou melhor. Pode não executar.
- **Stop**: vira ordem a mercado quando o preço atinge o nível. É como o stop loss funciona; num gap, a execução pode ser pior que o nível.

## Os três custos

- **Spread**: diferença entre o preço de compra (ask) e o de venda (bid).
- **Slippage**: diferença entre o preço planejado e o executado.
- **Comissão e financiamento**: taxa por operação e, em CFDs, o **swap** por manter posição de um dia para o outro.

## Exemplo

Alvo de US$ 0,20 por ação, custo total de US$ 0,08: 40% do ganho esperado vai embora antes de você estar certo. Em alvos pequenos, o custo decide o resultado.

## Como usar isso

- Antes de operar, estime o custo de ida e volta em dólares e compare com o alvo.
- Prefira ordens limitadas quando a entrada não for urgente.
- Na trilha "Como avaliar um sinal" você vê o efeito dos custos medido num setup real.
""",
    "O que o OneB pode e nao pode fazer": """\
O OneB é uma ferramenta de **apoio à decisão**: monitora, organiza evidências, alerta e ensina. Ele **não envia ordens** e não substitui o seu julgamento.

## O que ele faz

- Mostra preço, regime, notícias e a leitura de tendência com a idade de cada dado.
- Testa regras e indicadores com custos e fora da amostra, e publica o veredito mesmo quando é ruim.
- Explica, com a IA, o que os números mostram, sempre citando de onde vêm.

## O que ele não faz

- Não promete acerto nem retorno.
- Não chama de recomendação o que ainda está em pesquisa.
- Não opera por você.

## "Sem setup" é uma resposta

Quando os dados são ruins, o contexto é conflitante ou não há evidência, a resposta certa é **não operar**. Esperar também é decisão.

## Como usar isso

- Trate cada leitura como evidência para a sua decisão, não como ordem.
- Confira o selo de evidência e a idade do dado antes de agir.
""",
    "Montando sua watchlist piloto": """\
Uma **watchlist** é a lista de ativos que você acompanha. No começo, menos é mais.

## Por que poucos ativos

- Menos ruído: dá para revisar cada decisão com calma.
- Você aprende o "jeito" de cada ativo: horário de maior movimento, tamanho típico do candle, reação a notícias.

## Critérios

- **Liquidez**: volume alto e spread baixo. Ativo sem liquidez distorce sinais e custos.
- **Dados confiáveis**: cotação disponível e sem buracos.
- **Motivo claro**: escreva por que cada ativo está na lista.

## Uma lista possível para começar

QQQ ou o futuro do Nasdaq, o S&P 500, o ouro e uma ou duas ações grandes que você conheça. Cinco ativos bastam.

## Como usar isso

- Escreva, para cada ativo, o motivo de acompanhar e uma regra simples de alerta.
- Revise a lista uma vez por mês, não todo dia.
""",
    "Leitura diaria antes da abertura": """\
Antes de procurar setup, olhe o **terreno**. Dez minutos bastam.

## Roteiro

- **Futuros e índices**: como estão Nasdaq, S&P 500, dólar, juros e ouro desde o fechamento de ontem?
- **Calendário**: há dado econômico importante hoje (emprego, inflação, juros)? Em que horário?
- **Notícias**: algo relevante sobre os ativos da sua lista?
- **Tendência**: na aba Análise › Tendência, os horizontes de 1, 3 e 12 meses concordam?
- **Risco do dia**: com evento forte no calendário, o dia pede tamanho menor ou espera.

## Regra do processo

Com evento de alto impacto marcado, espere a reação inicial antes de agir. Não é uma previsão do mercado; é uma regra para não operar no momento de maior incerteza.

## Como usar isso

- Escreva três riscos e três pontos de atenção do dia nas anotações.
- Se o contexto estiver confuso, o plano do dia pode ser "observar".
""",
    "Definindo seu risco maximo": """\
Antes de pensar em entrada, defina **quanto você aceita perder**.

## Três limites

- **Por operação**: um percentual pequeno do capital, por exemplo 0,5% a 1%.
- **Por dia**: o máximo que você aceita perder num dia antes de parar, por exemplo 2% a 3%.
- **Na carteira**: a soma do risco de todas as posições abertas.

## A conta

Com US$ 10.000 e 1% por operação, a perda planejada se o stop for atingido é **US$ 100**. Esse número vem antes do alvo e antes da quantidade.

## Por que pequeno

Sequências de perdas acontecem até com métodos bons. Com 1% por operação, dez perdas seguidas custam cerca de 10% do capital; com 10%, a conta quebra.

## Como usar isso

- Escreva seus três limites e deixe à vista.
- Use o simulador da aula e o Laboratório com esses limites.
""",
    "Tamanho de posicao e stop": """\
O tamanho da posição **nasce do stop**, não da vontade.

## A fórmula

- quantidade = risco em dólares ÷ distância até o stop

Exemplo: risco de US$ 100 e stop US$ 2 abaixo da entrada: 100 ÷ 2 = **50 ações**.

## A ordem certa

- Defina onde a ideia fica errada (o stop).
- Calcule a quantidade pelo risco.
- Só então olhe o alvo e a relação risco/retorno.

## Volatilidade muda o tamanho

Com o mesmo risco em dólares, um ativo que oscila mais pede stop mais distante e, portanto, **menos unidades**. O ATR ajuda a medir esse tamanho típico do movimento.

## Como usar isso

- Nunca aumente a quantidade "porque tem convicção".
- Se o stop coerente deixa a quantidade pequena demais para valer a pena, a resposta é não operar.
""",
    "Circuit breakers pessoais": """\
Um **circuit breaker pessoal** é uma regra escrita antes do dia começar, que manda parar quando as coisas dão errado.

## Exemplos

- Parar no dia depois de perder 2% do capital.
- Parar depois de 3 perdas seguidas.
- No máximo 3 operações por dia.

## Por que funciona

Depois de perdas, a tendência é querer "recuperar": aumentar o tamanho, entrar sem plano, mover o stop. A regra corta o ciclo antes de ele começar.

## O que fazer quando dispara

- Fechar a plataforma.
- Registrar no diário o que aconteceu.
- Voltar no dia seguinte, com a mesma regra.

## Como usar isso

- Escreva seu protocolo de parada em três linhas e cole perto da tela.
""",
    "Lidando com FOMO e overtrading": """\
**FOMO** é o medo de ficar de fora. **Overtrading** é operar demais. Os dois trocam o processo pela urgência.

## Sinais de alerta

- Entrar depois de um candle enorme, sem plano escrito.
- Mudar de ativo várias vezes no mesmo dia procurando "ação".
- Sentir que precisa operar para o dia "valer a pena".

## Antídotos

- **Checklist antes da entrada**: tese, gatilho, stop, alvo e invalidação escritos.
- **Limite de operações por dia.**
- **Aceitar perder o movimento**: haverá outros.

## No Laboratório

Faça um replay e conte quantas vezes quis entrar sem plano. Esse número é o seu FOMO medido.

## Como usar isso

- Registre no diário as vezes em que ignorou uma regra e o que aconteceu depois.
""",
    "Quando aceitar o NO_TRADE": """\
**NO_TRADE** (sem setup) é a decisão de não operar. É uma resposta válida e, muitas vezes, a mais lucrativa.

## Motivos objetivos para não operar

- Dados atrasados ou incompletos.
- Sinais conflitantes: tendência diária para um lado, leitura intradiária para o outro.
- Evento de alto impacto marcado para os próximos minutos.
- Stop coerente grande demais para o seu risco.
- Nenhuma evidência testada para o setup.

## Esperar é processo

Quem opera tudo paga custo em tudo. Quem espera só paga quando há motivo.

## Como usar isso

- Registre no diário as decisões de não operar, com o motivo. Elas também mostram disciplina.
""",
}
