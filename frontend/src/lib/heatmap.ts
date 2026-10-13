/** Utilidades do mapa de horários: faixas de cor, hora de NY e conversão para Brasília. */

export type HeatMetric = 'ratio' | 'cost_share';

export const WEEKDAYS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex'];

/** 5 faixas fixas por métrica. Custo usa limites absolutos para comparar ativos entre si. */
export const CELL_BINS: Record<HeatMetric, { upTo: number; label: string }[]> = {
  ratio: [
    { upTo: 0.5, label: 'abaixo de 0,5x' },
    { upTo: 0.8, label: '0,5x–0,8x' },
    { upTo: 1.25, label: '0,8x–1,25x (típica)' },
    { upTo: 2, label: '1,25x–2x' },
    { upTo: Infinity, label: '2x ou mais' },
  ],
  cost_share: [
    { upTo: 0.02, label: 'até 2%' },
    { upTo: 0.05, label: '2%–5%' },
    { upTo: 0.1, label: '5%–10%' },
    { upTo: 0.2, label: '10%–20%' },
    { upTo: Infinity, label: '20% ou mais' },
  ],
};

export function binOf(metric: HeatMetric, value: number): number {
  const i = CELL_BINS[metric].findIndex((b) => value < b.upTo);
  return i === -1 ? CELL_BINS[metric].length - 1 : i;
}

function zonedParts(date: Date, timeZone: string) {
  const parts = new Intl.DateTimeFormat('en-US', { timeZone, weekday: 'short', hour: 'numeric', hourCycle: 'h23' }).formatToParts(date);
  const weekday = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].indexOf(parts.find((p) => p.type === 'weekday')!.value);
  return { weekday, hour: Number(parts.find((p) => p.type === 'hour')!.value) };
}

/** Dia útil (0 = segunda) e hora em Nova York agora. */
export function nowNy(date = new Date()) {
  return zonedParts(date, 'America/New_York');
}

/** Diferença em horas de Brasília menos Nova York na data (1 com horário de verão americano, 2 sem). */
export function brasiliaOffset(date = new Date()): number {
  const ny = zonedParts(date, 'America/New_York').hour;
  const br = zonedParts(date, 'America/Sao_Paulo').hour;
  return (br - ny + 24) % 24;
}

export function brasiliaHour(nyHour: number, date = new Date()): number {
  return (nyHour + brasiliaOffset(date)) % 24;
}

/** Dia útil (0 = segunda) e hora em Brasília agora. */
export function nowBrasilia(date = new Date()) {
  return zonedParts(date, 'America/Sao_Paulo');
}

/** Célula de NY que corresponde a um dia/hora de Brasília (a meia-noite pode cair no dia anterior em NY). */
export function nyFromBrasilia(brWeekday: number, brHour: number, date = new Date()): { weekday: number; hour: number } {
  const ny = brHour - brasiliaOffset(date);
  return ny >= 0 ? { weekday: brWeekday, hour: ny } : { weekday: brWeekday - 1, hour: ny + 24 };
}
