/**
 * Status de mercado calculado no cliente (Intl + fuso de cada bolsa).
 *
 * Limitações conhecidas (ver relatório):
 * - Feriados vêm de listas configuráveis abaixo (NYSE/Nasdaq e B3 de 2026–2027).
 *   Fora delas, um feriado não listado aparece como "aberto".
 * - COMEX (ouro, CME Globex) usa a grade padrão; feriados e horários especiais da CME não são considerados.
 * - B3: pregão regular do mercado à vista. Durante o horário de verão dos EUA, 10:00–17:00;
 *   fora dele, 10:00–18:00 (horário de Brasília). Leilões e after-market não entram.
 */

export type MarketId = 'nasdaq' | 'comex' | 'b3';

export interface MarketConfig {
  id: MarketId;
  name: string;
  short: string;
  tz: string;
}

export const MARKETS: MarketConfig[] = [
  { id: 'nasdaq', name: 'NASDAQ', short: 'NASDAQ', tz: 'America/New_York' },
  { id: 'comex', name: 'Ouro (COMEX)', short: 'COMEX', tz: 'America/New_York' },
  { id: 'b3', name: 'B3', short: 'B3', tz: 'America/Sao_Paulo' },
];

/** Feriados NYSE/Nasdaq (fonte: NYSE Group, calendário 2025–2027). Datas no fuso de Nova York. */
export const NASDAQ_HOLIDAYS: string[] = [
  '2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25', '2026-06-19', '2026-07-03', '2026-09-07',
  '2026-11-26', '2026-12-25',
  '2027-01-01', '2027-01-18', '2027-02-15', '2027-03-26', '2027-05-31', '2027-06-18', '2027-07-05', '2027-09-06',
  '2027-11-25', '2027-12-24',
];

/** Fechamento antecipado às 13:00 de Nova York. */
export const NASDAQ_EARLY_CLOSE: string[] = ['2026-11-27', '2026-12-24', '2027-11-26'];

/** Feriados sem pregão na B3 (2026). Atualize a cada calendário anual divulgado pela B3. */
export const B3_HOLIDAYS: string[] = [
  '2026-01-01', '2026-02-16', '2026-02-17', '2026-04-03', '2026-04-21', '2026-05-01', '2026-06-04', '2026-09-07',
  '2026-10-12', '2026-11-20', '2026-12-24', '2026-12-25', '2026-12-31',
];

/** Abertura tardia na B3 (Quarta-feira de Cinzas): minuto de abertura no fuso de São Paulo. */
export const B3_LATE_OPEN: Record<string, number> = { '2026-02-18': 13 * 60 };

// ---------------------------------------------------------------------------

interface ZonedParts {
  date: string; // yyyy-mm-dd
  weekday: number; // 0 = domingo
  minutes: number; // minutos desde 00:00
}

const partsCache = new Map<string, Intl.DateTimeFormat>();

function formatter(tz: string) {
  let f = partsCache.get(tz);
  if (!f) {
    f = new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      weekday: 'short',
      hourCycle: 'h23',
    });
    partsCache.set(tz, f);
  }
  return f;
}

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export function zonedParts(date: Date, tz: string): ZonedParts & { y: number; m: number; d: number; h: number; min: number; s: number } {
  const map: Record<string, string> = {};
  for (const p of formatter(tz).formatToParts(date)) map[p.type] = p.value;
  const y = Number(map.year);
  const m = Number(map.month);
  const d = Number(map.day);
  const h = Number(map.hour);
  const min = Number(map.minute);
  const s = Number(map.second);
  return { y, m, d, h, min, s, date: `${map.year}-${map.month}-${map.day}`, weekday: WEEKDAYS.indexOf(map.weekday), minutes: h * 60 + min };
}

/** Deslocamento do fuso (ms) em um instante. */
function tzOffset(date: Date, tz: string): number {
  const p = zonedParts(date, tz);
  const asUtc = Date.UTC(p.y, p.m - 1, p.d, p.h, p.min, p.s);
  return asUtc - Math.floor(date.getTime() / 1000) * 1000;
}

/** Converte uma hora de parede (data + minutos) num fuso para Date. */
export function zonedTime(dateStr: string, minutes: number, tz: string): Date {
  const [y, m, d] = dateStr.split('-').map(Number);
  const guess = Date.UTC(y, m - 1, d, Math.floor(minutes / 60), minutes % 60);
  let t = guess - tzOffset(new Date(guess), tz);
  t = guess - tzOffset(new Date(t), tz);
  return new Date(t);
}

function addDays(dateStr: string, days: number): string {
  const [y, m, d] = dateStr.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d + days));
  return dt.toISOString().slice(0, 10);
}

function weekdayOf(dateStr: string): number {
  const [y, m, d] = dateStr.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d)).getUTCDay();
}

/** Nova York está em horário de verão nesta data? */
export function isUsDst(dateStr: string): boolean {
  const noon = zonedTime(dateStr, 12 * 60, 'America/New_York');
  return tzOffset(noon, 'America/New_York') === -4 * 3600 * 1000;
}

type Session = [number, number]; // minutos [início, fim) no fuso do mercado

export function sessionsFor(market: MarketId, dateStr: string): Session[] {
  const wd = weekdayOf(dateStr);
  if (market === 'nasdaq') {
    if (wd === 0 || wd === 6 || NASDAQ_HOLIDAYS.includes(dateStr)) return [];
    return [[9 * 60 + 30, NASDAQ_EARLY_CLOSE.includes(dateStr) ? 13 * 60 : 16 * 60]];
  }
  if (market === 'comex') {
    // Globex: domingo 18:00 → sexta 17:00 (NY), pausa diária 17:00–18:00.
    if (wd === 6) return [];
    if (wd === 0) return [[18 * 60, 24 * 60]];
    if (wd === 5) return [[0, 17 * 60]];
    return [
      [0, 17 * 60],
      [18 * 60, 24 * 60],
    ];
  }
  // B3
  if (wd === 0 || wd === 6 || B3_HOLIDAYS.includes(dateStr)) return [];
  const close = isUsDst(dateStr) ? 17 * 60 : 18 * 60;
  return [[B3_LATE_OPEN[dateStr] ?? 10 * 60, close]];
}

export type MarketPhase = 'open' | 'closed' | 'break';

export interface MarketStatus {
  market: MarketConfig;
  phase: MarketPhase;
  /** Próxima mudança de estado (fechamento se aberto; abertura se fechado). */
  nextChange: Date | null;
}

interface Interval {
  start: Date;
  end: Date;
}

/** Sessões contínuas (junta 23:59→00:00) a partir de alguns dias antes de `now`. */
function intervals(market: MarketConfig, now: Date, daysAhead = 10): Interval[] {
  const today = zonedParts(now, market.tz).date;
  const list: Interval[] = [];
  for (let i = -2; i <= daysAhead; i++) {
    const day = addDays(today, i);
    for (const [s, e] of sessionsFor(market.id, day)) {
      const start = zonedTime(day, s, market.tz);
      const end = e >= 24 * 60 ? zonedTime(addDays(day, 1), 0, market.tz) : zonedTime(day, e, market.tz);
      const last = list[list.length - 1];
      if (last && last.end.getTime() === start.getTime()) last.end = end;
      else list.push({ start, end });
    }
  }
  return list;
}

export function getMarketStatus(id: MarketId, now: Date = new Date()): MarketStatus {
  const market = MARKETS.find((m) => m.id === id)!;
  const list = intervals(market, now);
  const current = list.find((iv) => iv.start <= now && now < iv.end);
  if (current) return { market, phase: 'open', nextChange: current.end };
  const next = list.find((iv) => iv.start > now) ?? null;
  // Pausa diária da COMEX: reabre em menos de 2 h no mesmo pregão semanal.
  const isBreak = id === 'comex' && next !== null && next.start.getTime() - now.getTime() <= 60 * 60 * 1000 && zonedParts(now, market.tz).weekday !== 6;
  return { market, phase: isBreak ? 'break' : 'closed', nextChange: next?.start ?? null };
}

// ---- Texto ------------------------------------------------------------------

export function formatDuration(ms: number): string {
  const totalMin = Math.max(0, Math.round(ms / 60000));
  const d = Math.floor(totalMin / 1440);
  const h = Math.floor((totalMin % 1440) / 60);
  const m = totalMin % 60;
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${String(m).padStart(2, '0')}m`;
  return `${m} min`;
}

export function tzLabel(displayTz: string): string {
  return displayTz === 'America/Sao_Paulo' ? 'horário de Brasília' : 'horário local';
}

const WEEKDAY_PT = ['dom.', 'seg.', 'ter.', 'qua.', 'qui.', 'sex.', 'sáb.'];

/**
 * "Aberto, fecha em 2h 14m" / "Fechado, abre às 10:30 (horário de Brasília)" /
 * "Fechado, abre seg. às 10:30 (horário de Brasília)".
 */
export function describeStatus(status: MarketStatus, now: Date, displayTz: string): string {
  if (status.phase === 'open') {
    return status.nextChange ? `Aberto, fecha em ${formatDuration(status.nextChange.getTime() - now.getTime())}` : 'Aberto';
  }
  if (!status.nextChange) return 'Fechado';
  const at = zonedParts(status.nextChange, displayTz);
  const today = zonedParts(now, displayTz);
  const time = `${String(at.h).padStart(2, '0')}:${String(at.min).padStart(2, '0')}`;
  const sameDay = at.date === today.date;
  const tomorrow = at.date === addDays(today.date, 1);
  const when = sameDay ? `às ${time}` : tomorrow ? `amanhã às ${time}` : `${WEEKDAY_PT[at.weekday]} às ${time}`;
  const prefix = status.phase === 'break' ? 'Em pausa, reabre' : 'Fechado, abre';
  return `${prefix} ${when} (${tzLabel(displayTz)})`;
}

export function userTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'America/Sao_Paulo';
  } catch {
    return 'America/Sao_Paulo';
  }
}
