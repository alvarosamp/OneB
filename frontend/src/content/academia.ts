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
  theme: 'Fundamentos' | 'Técnica' | 'Risco' | 'Processo' | 'Evidência' | 'Macro' | 'Assistente';
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
    slug: 'como-avaliar-um-sinal',
    order: 5,
    title: 'Como avaliar um sinal',
    level: 'Intermediário',
    theme: 'Evidência',
    summary: 'Acerto, custos, backtest honesto e promessas de sinais, com os testes reais que o OneB fez em indicadores comprados.',
    goals: [
      'Calcular a expectativa em R e entender por que 55% de acerto pode perder',
      'Estimar quanto spread, slippage e comissão tiram de um setup',
      'Reconhecer look-ahead e repaint num backtest',
      'Separar descoberta de confirmação e desconfiar do “melhor parâmetro”',
      'Aplicar um checklist antes de pagar ou seguir um serviço de sinais',
    ],
    prerequisite: 'Processo, diário e revisão',
    available: true,
  },
  {
    slug: 'leitura-de-regime-e-contexto',
    order: 6,
    title: 'Leitura de regime e contexto macro',
    level: 'Avançado',
    theme: 'Macro',
    summary: 'Calendário, tendência de 1, 3 e 12 meses, dólar, juros, ouro e volatilidade, com os estudos do próprio OneB.',
    goals: [
      'Saber quanto CPI, payroll e FOMC costumam mexer no preço e por quanto tempo',
      'Ler a tendência de 1, 3 e 12 meses e o preço de virada',
      'Usar correlações como contexto, sem confundir com causa',
      'Entender por que a relação entre ouro e juro real mudou',
      'Ajustar o tamanho da posição à volatilidade',
    ],
    prerequisite: 'Análise técnica e price action',
    available: true,
  },
  {
    slug: 'assistente-aplicado',
    order: 7,
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

/** O quiz de cada aula fica no servidor (app/academy_quizzes.json): o gabarito não vai para o navegador. */
export interface LessonExtra {
  /** Ativo para "Praticar no gráfico" (dado real do backend). */
  practiceSymbol: string;
  practiceHint: string;
  /** Replay do Laboratório ligado à aula (app/academy_replays). */
  replaySlug?: string;
}

export const LESSON_EXTRAS: Record<string, LessonExtra> = {
  'Calendário macro: o que mexe e quanto': {
    replaySlug: 'sp500-dia-de-cpi',
    practiceSymbol: 'NQ=F',
    practiceHint: 'Em Mercado › Calendário, veja a coluna Volatilidade típica do próximo CPI ou payroll e calcule o stop de 1 ATR multiplicado por esse número.',
  },
  'Tendência de 1, 3 e 12 meses': {
    practiceSymbol: 'QQQ',
    practiceHint: 'Abra Análise › Tendência e anote, para o Nasdaq, a direção nos três horizontes e o preço de virada de 3 meses.',
  },
  'Dólar, juros e Nasdaq': {
    practiceSymbol: 'QQQ',
    practiceHint: 'Em Análise › Macro, compare a correlação do Nasdaq com os juros de 10 anos em janelas diferentes.',
  },
  'O que move o ouro': {
    practiceSymbol: 'GC=F',
    practiceHint: 'Veja a tendência do ouro em Análise › Tendência e compare com o que aconteceu com os juros reais no mesmo período.',
  },
  'Volatilidade e tamanho de posição': {
    replaySlug: 'eurusd-dia-de-payroll',
    practiceSymbol: 'NQ=F',
    practiceHint: 'Use o Laboratório: faça a mesma operação com stop de 1 ATR e depois com stop de 3 ATR, mantendo 1% de risco, e compare a quantidade.',
  },
  'Abrindo uma conta demo no MetaTrader 5': {
    practiceSymbol: 'QQQ',
    practiceHint: 'Compare o bid e o ask do QQQ no gráfico com o que a sua conta demo mostra para um índice: qual é o spread de cada um?',
    replaySlug: 'nasdaq-dia-lateral',
  },
  'Seu primeiro trade no laboratório': {
    practiceSymbol: 'NQ=F',
    practiceHint: 'Abra a aba Laboratório desta aula e siga o roteiro no replay do dia lateral.',
    replaySlug: 'nasdaq-dia-lateral',
  },
  'Como funciona a NASDAQ': {
    practiceSymbol: 'QQQ',
    practiceHint: 'Observe o QQQ no 1D: repare no volume maior na abertura e no fechamento do pregão regular.',
  },
  'Ordens, corretoras e custos': {
    practiceSymbol: 'NVDA',
    practiceHint: 'Veja a amplitude dos candles de 5 min da NVDA e imagine um spread de alguns centavos em cada entrada e saída.',
  },
  'O que o OneB pode e nao pode fazer': {
    practiceSymbol: 'QQQ',
    practiceHint: 'Abra a leitura do ativo e note que o estado é sempre Sem setup, Observar ou Setup em formação, nunca uma ordem.',
  },
  'Montando sua watchlist piloto': {
    practiceSymbol: 'QQQ',
    practiceHint: 'Compare a liquidez (volume) do QQQ com a de um ativo pequeno que você conheça.',
  },
  'Leitura diaria antes da abertura': {
    practiceSymbol: 'NQ=F',
    practiceHint: 'Veja o NQ=F no 1D antes das 9:30 de Nova York: é o futuro que negocia enquanto o pregão à vista está fechado.',
  },
  'Candles e price action': {
    replaySlug: 'nasdaq-dia-de-tendencia',
    practiceSymbol: 'QQQ',
    practiceHint: 'No 1D, encontre um candle de pavio longo perto de suporte ou resistência e descreva o contexto.',
  },
  'Tendencia, faixa e reversao': {
    replaySlug: 'nasdaq-dia-lateral',
    practiceSymbol: 'NQ=F',
    practiceHint: 'No 6M, compare EMA 20 e EMA 200: onde o preço está e para onde as médias apontam?',
  },
  'Suporte, resistencia e zonas': {
    practiceSymbol: 'AAPL',
    practiceHint: 'Veja as linhas de suporte e resistência no gráfico da AAPL e meça a distância do preço até cada uma.',
  },
  'Medias, RSI e MACD sem excesso de sinal': {
    practiceSymbol: 'NVDA',
    practiceHint: 'Observe o RSI acima de 70 na NVDA: o preço caiu logo depois ou seguiu subindo?',
  },
  'Volume e forca do movimento': {
    practiceSymbol: 'TSLA',
    practiceHint: 'Compare as barras de volume nos candles de rompimento com a média recente.',
  },
  'ATR, Bollinger e volatilidade': {
    practiceSymbol: 'NQ=F',
    practiceHint: 'Na leitura do ativo, veja o ATR e calcule onde ficaria um stop de 1,5 ATR a partir do último preço.',
  },
  'Montando um setup na Mesa Tecnica': {
    practiceSymbol: 'QQQ',
    practiceHint: 'Monte no simulador um setup no QQQ com entrada, stop e alvo, e confira o risco/retorno.',
  },
  'Definindo seu risco maximo': {
    practiceSymbol: 'QQQ',
    practiceHint: 'No simulador, use 1% de risco num capital de US$ 10.000 e veja quantas cotas cabem.',
  },
  'Tamanho de posicao e stop': {
    practiceSymbol: 'NVDA',
    practiceHint: 'Coloque o stop abaixo do suporte da NVDA e deixe o simulador calcular a quantidade.',
  },
  'Circuit breakers pessoais': {
    practiceSymbol: 'QQQ',
    practiceHint: 'Revise seus últimos lançamentos na Carteira e veja se algum dia teria acionado sua regra de parada.',
  },
  'Lidando com FOMO e overtrading': {
    replaySlug: 'nasdaq-dia-de-tendencia',
    practiceSymbol: 'TSLA',
    practiceHint: 'Encontre um candle muito grande na TSLA e pergunte: haveria setup antes dele ou só depois?',
  },
  'Quando aceitar o NO_TRADE': {
    practiceSymbol: 'NQ=F',
    practiceHint: 'Veja a leitura do dia no Hoje: quando o estado é Sem setup, quais evidências explicam isso?',
  },
  'Journaling de decisoes': {
    practiceSymbol: 'QQQ',
    practiceHint: 'Escreva nas anotações da aula a tese de uma decisão que você tomou esta semana.',
  },
  'Tese, gatilho e invalidacao': {
    practiceSymbol: 'NVDA',
    practiceHint: 'Defina no gráfico da NVDA um nível de invalidação objetivo para uma tese de alta.',
  },
  'Revisao de falso positivo': {
    practiceSymbol: 'AMD',
    practiceHint: 'Procure no gráfico um rompimento que falhou e liste o que estava faltando.',
  },
  'Checklist semanal da Mesa': {
    practiceSymbol: 'QQQ',
    practiceHint: 'Veja o QQQ no 1M e resuma a semana em três frases.',
  },
  'Plano de evolucao individual': {
    practiceSymbol: 'QQQ',
    practiceHint: 'Escolha nas anotações o erro mais frequente do mês e a aula que o endereça.',
  },
  'Acerto não é lucro': {
    replaySlug: 'ouro-rompimento-falso-londres',
    practiceSymbol: 'QQQ',
    practiceHint: 'Imagine um alvo de 0,3% e um stop de 1% no QQQ: quantas vezes você precisaria acertar para empatar?',
  },
  'Custos que somem com o resultado': {
    practiceSymbol: 'NQ=F',
    practiceHint: 'Veja a amplitude de um candle de 5 min do NQ=F e compare com um spread de 1 a 2 pontos em cada entrada e saída.',
  },
  'Backtest honesto: olhar o futuro sem perceber': {
    practiceSymbol: 'QQQ',
    practiceHint: 'No 5 min, escolha um candle e anote: em que horário o fechamento dele fica conhecido?',
  },
  'Fora da amostra e pré-registro': {
    practiceSymbol: 'NQ=F',
    practiceHint: 'Escolha uma regra simples e escreva, antes de olhar o gráfico, o que faria você aprovar ou descartar a regra.',
  },
  'Lendo promessas de sinais': {
    practiceSymbol: 'QQQ',
    practiceHint: 'Abra o Assistente e compare como ele mostra o placar de evidência com um anúncio de sinais que você conheça.',
  },
  '64 regras testadas: o que reprovou e por quê': {
    practiceSymbol: 'NQ=F',
    practiceHint: 'Abra Análise › Ativo e leia o bloco "O que já testamos neste ativo" para dois ativos diferentes.',
  },
  'Horário e spread: quando o custo come o movimento': {
    practiceSymbol: 'NQ=F',
    practiceHint: 'Abra Análise › Horários, troque entre Nasdaq e S&P 500 na métrica Custo do spread e depois faça a conta do seu lote em Análise › Ativo.',
  },
};

export function lessonExtra(title: string): LessonExtra | undefined {
  return LESSON_EXTRAS[title];
}
