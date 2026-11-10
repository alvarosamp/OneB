/**
 * Conteúdo da Academia que o backend (app/routers/lms.py) ainda não fornece:
 * metadados de trilha (nível, tema, objetivos, pré-requisito), exercícios
 * objetivos por aula e o ativo usado em "Praticar no gráfico".
 *
 * As chaves de aula são os títulos do seed do backend (sem acento, como vêm da API).
 * TODO(backend): mover para o LMS (tabelas de trilha, questão e prática).
 */

export interface TrackMeta {
  slug: string;
  order: number;
  title: string;
  level: 'Iniciante' | 'Intermediário' | 'Avançado';
  theme: 'Fundamentos' | 'Técnica' | 'Risco' | 'Processo' | 'Macro' | 'Assistente';
  summary: string;
  goals: string[];
  prerequisite: string | null;
  /** false = trilha ainda sem curso no backend (aparece como "em produção"). */
  available: boolean;
}

export const TRACKS: TrackMeta[] = [
  {
    slug: 'fundamentos',
    order: 1,
    title: 'Fundamentos do mercado americano',
    level: 'Iniciante',
    theme: 'Fundamentos',
    summary: 'Como a NASDAQ funciona, quanto custa operar e o que o OneB faz (e não faz) por você.',
    goals: [
      'Explicar a diferença entre ação, ETF, índice e contrato futuro',
      'Estimar o efeito de spread, taxas e slippage num setup',
      'Montar uma watchlist piloto com poucos ativos e motivo claro',
      'Fazer a leitura diária antes da abertura em menos de 10 minutos',
    ],
    prerequisite: null,
    available: true,
  },
  {
    slug: 'gestao-de-risco-e-psicologia',
    order: 2,
    title: 'Gestão de risco e psicologia',
    level: 'Iniciante',
    theme: 'Risco',
    summary: 'Proteger capital vem antes de achar entradas: risco por operação, tamanho de posição e disciplina.',
    goals: [
      'Definir risco máximo por operação, por dia e por carteira',
      'Calcular o tamanho da posição a partir da distância até o stop',
      'Criar regras pessoais para parar depois de perdas seguidas',
      'Reconhecer FOMO e overtrading e aceitar o “sem setup”',
    ],
    prerequisite: 'Fundamentos do mercado americano',
    available: true,
  },
  {
    slug: 'analise-tecnica-avancada',
    order: 3,
    title: 'Análise técnica e price action',
    level: 'Intermediário',
    theme: 'Técnica',
    summary: 'Contexto, candles, médias, momentum e volatilidade para montar setups simples e testáveis.',
    goals: [
      'Classificar o regime (tendência, faixa ou reversão) antes de escolher um setup',
      'Marcar suporte, resistência e zonas sem excesso de subjetividade',
      'Usar médias, RSI, MACD e volume como evidência, não como gatilho isolado',
      'Dimensionar stop e alvo pelo ATR',
      'Montar um setup completo com tese, entrada, stop, alvo e invalidação',
    ],
    prerequisite: 'Gestão de risco e psicologia',
    available: true,
  },
  {
    slug: 'processo-diario-e-revisao',
    order: 4,
    title: 'Processo, diário e revisão',
    level: 'Intermediário',
    theme: 'Processo',
    summary: 'Registrar decisões, revisar erros e transformar operações em aprendizado mensurável.',
    goals: [
      'Escrever tese, gatilho e invalidação antes de agir',
      'Manter um diário de decisões que permita auditoria',
      'Revisar falsos positivos e ajustar regras',
      'Fechar a semana com um checklist e um plano de evolução',
    ],
    prerequisite: 'Análise técnica e price action',
    available: true,
  },
  {
    slug: 'leitura-de-regime-e-contexto',
    order: 5,
    title: 'Leitura de regime e contexto macro',
    level: 'Avançado',
    theme: 'Macro',
    summary: 'Dólar, juros, ouro e volatilidade como contexto para a Nasdaq.',
    goals: ['Ler correlações entre Nasdaq, dólar, juros e ouro', 'Identificar quando o contexto macro confirma ou diverge do gráfico'],
    prerequisite: 'Análise técnica e price action',
    available: false,
  },
  {
    slug: 'assistente-aplicado',
    order: 6,
    title: 'Assistente aplicado à rotina',
    level: 'Avançado',
    theme: 'Assistente',
    summary: 'Como usar a Visão do mercado, a revisão de setup e a explicação de alertas sem terceirizar a decisão.',
    goals: ['Revisar um setup com o Assistente e contestar a resposta', 'Usar o placar de confiabilidade para calibrar a confiança'],
    prerequisite: 'Processo, diário e revisão',
    available: false,
  },
];

export function trackMeta(slug: string): TrackMeta | undefined {
  return TRACKS.find((t) => t.slug === slug);
}

export interface QuizQuestion {
  question: string;
  options: string[];
  correct: number;
  why: string;
}

export interface LessonExtra {
  quiz: QuizQuestion[];
  /** Ativo para "Praticar no gráfico" (dado real do backend). */
  practiceSymbol: string;
  practiceHint: string;
}

const Q = (question: string, options: string[], correct: number, why: string): QuizQuestion => ({ question, options, correct, why });

export const LESSON_EXTRAS: Record<string, LessonExtra> = {
  'Como funciona a NASDAQ': {
    practiceSymbol: 'QQQ',
    practiceHint: 'Observe o QQQ no 1D: repare no volume maior na abertura e no fechamento do pregão regular.',
    quiz: [
      Q('Qual é o horário do pregão regular da NASDAQ?', ['9:30 às 16:00 de Nova York', '10:00 às 17:00 de Brasília, o ano todo', '24 horas em dias úteis'], 0, 'O pregão regular vai das 9:30 às 16:00 no horário de Nova York; em Brasília, isso muda com o horário de verão americano.'),
      Q('O QQQ é…', ['Uma ação da Nasdaq Inc.', 'Um ETF que replica o Nasdaq-100', 'Um contrato futuro'], 1, 'O QQQ é um ETF: uma cota negociada em bolsa que acompanha o índice Nasdaq-100.'),
    ],
  },
  'Ordens, corretoras e custos': {
    practiceSymbol: 'NVDA',
    practiceHint: 'Veja a amplitude dos candles de 5 min da NVDA e imagine um spread de alguns centavos em cada entrada e saída.',
    quiz: [
      Q('O que é slippage?', ['A taxa fixa da corretora', 'A diferença entre o preço esperado e o preço executado', 'O intervalo entre compra e venda de um mesmo dia'], 1, 'Slippage é a diferença entre o preço que você planejou e o preço em que a ordem de fato foi executada.'),
      Q('Um setup com alvo de US$ 0,20 e custo total de US$ 0,08 por ação…', ['Continua ótimo, custo não importa', 'Perde 40% do potencial só com custos', 'Fica melhor com mais alavancagem'], 1, 'Custos comem uma parte fixa do resultado; em alvos pequenos, o impacto proporcional é grande.'),
    ],
  },
  'O que o OneB pode e nao pode fazer': {
    practiceSymbol: 'QQQ',
    practiceHint: 'Abra a leitura do ativo e note que o estado é sempre Sem setup, Observar ou Setup em formação, nunca uma ordem.',
    quiz: [
      Q('O OneB envia ordens para a sua corretora?', ['Sim, quando o estado é Setup em formação', 'Não, ele só monitora, alerta e explica', 'Só com o Assistente ativo'], 1, 'O OneB é ferramenta de monitoramento e apoio à decisão; não executa ordens.'),
      Q('“Sem setup” significa…', ['Que o sistema falhou', 'Que não há combinação de contexto e gatilho que justifique agir agora', 'Que o ativo vai cair'], 1, 'Sem setup é uma resposta válida: esperar também é decisão.'),
    ],
  },
  'Montando sua watchlist piloto': {
    practiceSymbol: 'QQQ',
    practiceHint: 'Compare a liquidez (volume) do QQQ com a de um ativo pequeno que você conheça.',
    quiz: [
      Q('Por que começar com poucos ativos?', ['Porque o sistema cobra por ativo', 'Para reduzir ruído e conseguir revisar cada decisão', 'Porque poucos ativos sempre sobem'], 1, 'Menos ativos significam menos ruído e revisão de melhor qualidade.'),
      Q('Qual critério é mais importante para um ativo da watchlist piloto?', ['Ter liquidez e dados confiáveis', 'Ter subido muito no último mês', 'Ser citado em redes sociais'], 0, 'Sem liquidez e dados confiáveis, sinais e custos ficam distorcidos.'),
    ],
  },
  'Leitura diaria antes da abertura': {
    practiceSymbol: 'NQ=F',
    practiceHint: 'Veja o NQ=F no 1D antes das 9:30 de Nova York: é o futuro que negocia enquanto o pregão à vista está fechado.',
    quiz: [
      Q('Antes da abertura, o que olhar primeiro?', ['Índices futuros, calendário do dia e notícias de impacto', 'Só o preço da sua ação favorita', 'O resultado de ontem da sua carteira'], 0, 'Contexto primeiro: futuros, eventos e notícias mostram o terreno antes do setup.'),
      Q('Um evento macro de alto impacto às 9:30 sugere…', ['Aumentar o tamanho da posição', 'Esperar a reação antes de agir', 'Ignorar, porque é só macro'], 1, 'Eventos de alto impacto aumentam volatilidade e gaps; esperar a reação reduz risco.'),
    ],
  },
  'Candles e price action': {
    practiceSymbol: 'QQQ',
    practiceHint: 'No 1D, encontre um candle de pavio longo perto de suporte ou resistência e descreva o contexto.',
    quiz: [
      Q('Um candle de pavio inferior longo significa…', ['Compra garantida', 'Houve rejeição de preços mais baixos naquele período', 'Tendência de alta confirmada'], 1, 'O pavio mostra rejeição, mas sem contexto não é sinal final.'),
      Q('Por que não usar um candle isolado como gatilho?', ['Porque candles não mostram preço', 'Porque o significado depende do contexto e do nível', 'Porque só vale no diário'], 1, 'O mesmo candle significa coisas diferentes em tendência, faixa ou perto de níveis.'),
    ],
  },
  'Tendencia, faixa e reversao': {
    practiceSymbol: 'NQ=F',
    practiceHint: 'No 6M, compare EMA 20 e EMA 200: onde o preço está e para onde as médias apontam?',
    quiz: [
      Q('Em regime de faixa (lateral), rompimentos…', ['Costumam ser confiáveis', 'Falham com mais frequência; exigem confirmação', 'Não existem'], 1, 'Em lateralidade, muitos rompimentos voltam para dentro da faixa.'),
      Q('No OneB, o regime combina…', ['Só o preço de fechamento', 'Médias, RSI, força da tendência (ADX) e estrutura', 'Notícias e redes sociais'], 1, 'O regime diário usa EMA 20/50, RSI, ADX e máximas/mínimas recentes.'),
    ],
  },
  'Suporte, resistencia e zonas': {
    practiceSymbol: 'AAPL',
    practiceHint: 'Veja as linhas de suporte e resistência no gráfico da AAPL e meça a distância do preço até cada uma.',
    quiz: [
      Q('Por que tratar suporte como zona, e não como linha exata?', ['Porque o preço raramente respeita um valor exato', 'Porque zonas são mais bonitas', 'Porque linhas não aparecem no gráfico'], 0, 'O mercado reage em regiões; zonas evitam stops apertados demais.'),
      Q('Uma resistência rompida frequentemente…', ['Desaparece', 'Passa a funcionar como suporte', 'Vira sinal de venda'], 1, 'É a troca de polaridade: resistência rompida tende a virar suporte.'),
    ],
  },
  'Medias, RSI e MACD sem excesso de sinal': {
    practiceSymbol: 'NVDA',
    practiceHint: 'Observe o RSI acima de 70 na NVDA: o preço caiu logo depois ou seguiu subindo?',
    quiz: [
      Q('RSI acima de 70 indica…', ['Venda imediata', 'Movimento esticado, que pode continuar em tendência forte', 'Erro nos dados'], 1, 'RSI alto mostra força esticada; em tendência forte ele pode ficar alto por muito tempo.'),
      Q('MACD cruzando acima da linha de sinal mostra…', ['Aceleração do momentum de alta', 'Que o volume subiu', 'Que o preço está barato'], 0, 'O MACD mede aceleração entre médias; o cruzamento indica ganho de momentum.'),
    ],
  },
  'Volume e forca do movimento': {
    practiceSymbol: 'TSLA',
    practiceHint: 'Compare as barras de volume nos candles de rompimento com a média recente.',
    quiz: [
      Q('Rompimento com volume abaixo da média…', ['É mais confiável', 'Merece desconfiança', 'Não tem relação com volume'], 1, 'Sem participação, o rompimento tem mais chance de falhar.'),
      Q('Volume relativo de 2,0x significa…', ['O dobro do volume médio recente', 'Metade do volume médio', 'Que o preço dobrou'], 0, 'Volume relativo compara o volume atual à média recente.'),
    ],
  },
  'ATR, Bollinger e volatilidade': {
    practiceSymbol: 'NQ=F',
    practiceHint: 'Na leitura do ativo, veja o ATR e calcule onde ficaria um stop de 1,5 ATR a partir do último preço.',
    quiz: [
      Q('Para que serve o ATR no plano?', ['Escolher a direção', 'Dimensionar stop e alvo ao tamanho típico do movimento', 'Medir notícias'], 1, 'O ATR mostra a amplitude típica; stops menores que isso são atingidos por ruído.'),
      Q('Com ATR maior, mantendo o mesmo risco em dólares, a posição deve…', ['Aumentar', 'Diminuir', 'Ficar igual'], 1, 'Stop mais distante com o mesmo risco exige menos unidades.'),
    ],
  },
  'Montando um setup na Mesa Tecnica': {
    practiceSymbol: 'QQQ',
    practiceHint: 'Monte no simulador um setup no QQQ com entrada, stop e alvo, e confira o risco/retorno.',
    quiz: [
      Q('O que precisa existir antes da entrada?', ['Tese, gatilho, stop, alvo e invalidação', 'Só o alvo', 'Uma notícia positiva'], 0, 'Um setup auditável tem todas essas partes definidas antes de agir.'),
      Q('Risco/retorno abaixo de 1,5R sugere…', ['Aumentar a posição', 'Rever o plano ou aceitar Sem setup', 'Tirar o stop'], 1, 'Relação ruim entre risco e retorno é motivo legítimo para não agir.'),
    ],
  },
  'Definindo seu risco maximo': {
    practiceSymbol: 'QQQ',
    practiceHint: 'No simulador, use 1% de risco num capital de US$ 10.000 e veja quantas cotas cabem.',
    quiz: [
      Q('Com US$ 10.000 e risco de 1% por operação, a perda máxima planejada é…', ['US$ 10', 'US$ 100', 'US$ 1.000'], 1, '1% de 10.000 é 100: é quanto você aceita perder se o stop for atingido.'),
      Q('Um limite de perda diário serve para…', ['Parar antes que decisões emocionais aumentem o prejuízo', 'Aumentar o número de operações', 'Evitar impostos'], 0, 'Limites diários interrompem sequências emocionais.'),
    ],
  },
  'Tamanho de posicao e stop': {
    practiceSymbol: 'NVDA',
    practiceHint: 'Coloque o stop abaixo do suporte da NVDA e deixe o simulador calcular a quantidade.',
    quiz: [
      Q('Risco de US$ 100 e stop a US$ 2 da entrada: quantas ações?', ['20', '50', '200'], 1, 'Quantidade = risco em dólares ÷ distância até o stop = 100 ÷ 2 = 50.'),
      Q('O que vem primeiro?', ['Escolher o alvo', 'Definir o stop e o tamanho', 'Escolher a alavancagem'], 1, 'O tamanho nasce do stop; o alvo vem depois.'),
    ],
  },
  'Circuit breakers pessoais': {
    practiceSymbol: 'QQQ',
    practiceHint: 'Revise seus últimos lançamentos na Carteira e veja se algum dia teria acionado sua regra de parada.',
    quiz: [
      Q('Um circuit breaker pessoal é…', ['Uma regra que interrompe a operação após perdas definidas', 'Um tipo de ordem da bolsa', 'Um indicador técnico'], 0, 'É uma regra escrita antes, para parar depois de X perdas ou Y% no dia.'),
      Q('Depois de 3 perdas seguidas, a regra mais saudável é…', ['Dobrar o tamanho para recuperar', 'Parar e revisar', 'Trocar de ativo imediatamente'], 1, 'Parar e revisar evita o ciclo de recuperação emocional.'),
    ],
  },
  'Lidando com FOMO e overtrading': {
    practiceSymbol: 'TSLA',
    practiceHint: 'Encontre um candle muito grande na TSLA e pergunte: haveria setup antes dele ou só depois?',
    quiz: [
      Q('FOMO costuma levar a…', ['Entradas atrasadas, sem plano, depois do movimento', 'Stops mais bem posicionados', 'Menos operações'], 0, 'O medo de ficar de fora faz entrar tarde e sem plano.'),
      Q('Um bom antídoto para overtrading é…', ['Limitar o número de operações por dia', 'Operar mais ativos', 'Seguir mais pessoas'], 0, 'Limites objetivos reduzem decisões impulsivas.'),
    ],
  },
  'Quando aceitar o NO_TRADE': {
    practiceSymbol: 'NQ=F',
    practiceHint: 'Veja a leitura do dia no Hoje: quando o estado é Sem setup, quais evidências explicam isso?',
    quiz: [
      Q('Quando regime diário e leitura intradiária discordam, o estado tende a ser…', ['Setup em formação', 'Sem setup', 'Observar com viés forte'], 1, 'Sinais conflitantes pedem espera: Sem setup.'),
      Q('Aceitar Sem setup é…', ['Perder oportunidade', 'Uma decisão profissional quando falta confluência', 'Um erro do sistema'], 1, 'Esperar faz parte do processo quando o contexto não sustenta a entrada.'),
    ],
  },
  'Journaling de decisoes': {
    practiceSymbol: 'QQQ',
    practiceHint: 'Escreva nas anotações da aula a tese de uma decisão que você tomou esta semana.',
    quiz: [
      Q('O que registrar no diário?', ['Só o resultado financeiro', 'Tese, gatilho, invalidação, risco e resultado', 'Apenas as operações vencedoras'], 1, 'Sem o processo registrado, não há como revisar a decisão.'),
      Q('Registrar decisões de não agir…', ['É desnecessário', 'Também é importante para avaliar o processo', 'Atrapalha a estatística'], 1, 'Decisões de espera também mostram disciplina e qualidade de leitura.'),
    ],
  },
  'Tese, gatilho e invalidacao': {
    practiceSymbol: 'NVDA',
    practiceHint: 'Defina no gráfico da NVDA um nível de invalidação objetivo para uma tese de alta.',
    quiz: [
      Q('Invalidação é…', ['O ponto em que a tese deixa de fazer sentido', 'O alvo da operação', 'O preço médio'], 0, 'É o que prova que você estava errado, e define o stop.'),
      Q('“Vou entrar se romper 180 com volume acima da média” é…', ['Uma tese', 'Um gatilho', 'Uma invalidação'], 1, 'Gatilho é o evento objetivo que dispara a entrada.'),
    ],
  },
  'Revisao de falso positivo': {
    practiceSymbol: 'AMD',
    practiceHint: 'Procure no gráfico um rompimento que falhou e liste o que estava faltando.',
    quiz: [
      Q('Um falso positivo é…', ['Um sinal que parecia bom e falhou', 'Um lucro inesperado', 'Um erro de cotação'], 0, 'É o sinal que cumpriu as regras e ainda assim não funcionou.'),
      Q('Ao revisar um falso positivo, o objetivo é…', ['Achar um culpado', 'Descobrir se falta um filtro ou se foi variância normal', 'Parar de operar'], 1, 'Nem todo erro é de regra; às vezes é a variância natural do método.'),
    ],
  },
  'Checklist semanal da Mesa': {
    practiceSymbol: 'QQQ',
    practiceHint: 'Veja o QQQ no 1M e resuma a semana em três frases.',
    quiz: [
      Q('O checklist semanal serve para…', ['Revisar processo, sinais e risco com regularidade', 'Escolher ações da semana que vem', 'Substituir o diário'], 0, 'É a revisão periódica do processo, complementar ao diário.'),
      Q('Drawdown é…', ['A maior queda do capital a partir de um pico', 'O lucro da semana', 'O volume médio'], 0, 'Drawdown mede a pior sequência de perdas a partir de um topo.'),
    ],
  },
  'Plano de evolucao individual': {
    practiceSymbol: 'QQQ',
    practiceHint: 'Escolha nas anotações o erro mais frequente do mês e a aula que o endereça.',
    quiz: [
      Q('Como escolher a próxima aula?', ['Pelo erro mais recente ou mais frequente', 'Pela aula mais curta', 'Aleatoriamente'], 0, 'Estudar o que corrige seu erro atual dá o maior retorno.'),
      Q('Um bom objetivo de evolução é…', ['Ganhar mais dinheiro', 'Reduzir entradas sem invalidação definida para zero em 4 semanas', 'Operar todos os dias'], 1, 'Objetivos de processo são mensuráveis e controláveis.'),
    ],
  },
};

export function lessonExtra(title: string): LessonExtra | undefined {
  return LESSON_EXTRAS[title];
}
