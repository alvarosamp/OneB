/**
 * Ponte terminal ↔ academia: cada conceito usado no terminal aponta para a
 * aula que o explica. Os títulos de aula são os do seed do backend
 * (app/routers/lms.py), e o link abre o player direto nessa aula.
 */
export interface Concept {
  term: string;
  short: string;
  course: string;
  lesson: string;
}

export const CONCEPTS: Record<string, Concept> = {
  regime: {
    term: 'Regime',
    short: 'Classificação do contexto do ativo (alta, neutro, baixa) combinando tendência das médias, momentum (RSI), força (ADX) e estrutura de máximas e mínimas.',
    course: 'analise-tecnica-avancada',
    lesson: 'Tendencia, faixa e reversao',
  },
  ema: {
    term: 'Médias móveis (EMA)',
    short: 'Média exponencial dos fechamentos. Preço acima de médias ascendentes sugere tendência de alta; médias emboladas sugerem lateralidade.',
    course: 'analise-tecnica-avancada',
    lesson: 'Medias, RSI e MACD sem excesso de sinal',
  },
  rsi: {
    term: 'RSI',
    short: 'Índice de força relativa (0 a 100). Acima de 70 indica movimento esticado; abaixo de 30, sobrevendido. Não é sinal de reversão sozinho.',
    course: 'analise-tecnica-avancada',
    lesson: 'Medias, RSI e MACD sem excesso de sinal',
  },
  macd: {
    term: 'MACD',
    short: 'Diferença entre duas médias exponenciais (12 e 26) comparada à sua média de 9. Mede aceleração do momentum.',
    course: 'analise-tecnica-avancada',
    lesson: 'Medias, RSI e MACD sem excesso de sinal',
  },
  atr: {
    term: 'ATR',
    short: 'Amplitude média real: o tamanho típico de um candle. Serve para dimensionar stop e alvo ao ritmo do ativo.',
    course: 'analise-tecnica-avancada',
    lesson: 'ATR, Bollinger e volatilidade',
  },
  volume: {
    term: 'Volume relativo',
    short: 'Volume atual comparado à média recente. Rompimento com volume baixo merece desconfiança.',
    course: 'analise-tecnica-avancada',
    lesson: 'Volume e forca do movimento',
  },
  'sem-setup': {
    term: 'Sem setup',
    short: 'Não há combinação de contexto e gatilho que justifique uma operação agora. Esperar também é decisão (no backend, NO_TRADE).',
    course: 'gestao-de-risco-e-psicologia',
    lesson: 'Quando aceitar o NO_TRADE',
  },
  suporte: {
    term: 'Suporte e resistência',
    short: 'Regiões onde o preço reagiu antes. Servem de referência para entrada, stop e alvo.',
    course: 'analise-tecnica-avancada',
    lesson: 'Suporte, resistencia e zonas',
  },
  risco: {
    term: 'Tamanho de posição',
    short: 'Quanto arriscar por operação define o tamanho da posição, a partir da distância até o stop.',
    course: 'gestao-de-risco-e-psicologia',
    lesson: 'Tamanho de posicao e stop',
  },
};

export function conceptHref(c: Concept): string {
  return `/aulas/${c.course}?aula=${encodeURIComponent(c.lesson)}`;
}
