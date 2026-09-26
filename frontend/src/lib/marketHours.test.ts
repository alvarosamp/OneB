import { describe, expect, it } from 'vitest';
import { describeStatus, formatDuration, getMarketStatus, isUsDst, zonedTime } from './marketHours';

const BRT = 'America/Sao_Paulo';
const text = (id: 'nasdaq' | 'comex' | 'b3', iso: string, tz = BRT) => {
  const now = new Date(iso);
  return describeStatus(getMarketStatus(id, now), now, tz);
};

describe('marketHours', () => {
  it('converte hora de parede com fuso', () => {
    expect(zonedTime('2026-09-23', 9 * 60 + 30, 'America/New_York').toISOString()).toBe('2026-09-23T13:30:00.000Z');
    expect(zonedTime('2026-12-02', 9 * 60 + 30, 'America/New_York').toISOString()).toBe('2026-12-02T14:30:00.000Z');
    expect(isUsDst('2026-09-23')).toBe(true);
    expect(isUsDst('2026-12-02')).toBe(false);
  });

  it('NASDAQ aberta em dia útil, com contagem até o fechamento', () => {
    expect(getMarketStatus('nasdaq', new Date('2026-09-23T14:00:00Z')).phase).toBe('open');
    expect(text('nasdaq', '2026-09-23T17:46:00Z')).toBe('Aberto, fecha em 2h 14m');
  });

  it('NASDAQ fechada no fim de semana abre na segunda (horário de Brasília)', () => {
    expect(text('nasdaq', '2026-09-26T15:00:00Z')).toBe('Fechado, abre seg. às 10:30 (horário de Brasília)');
  });

  it('antes da abertura no mesmo dia', () => {
    expect(text('nasdaq', '2026-09-23T12:00:00Z')).toBe('Fechado, abre às 10:30 (horário de Brasília)');
  });

  it('respeita feriados e fechamento antecipado', () => {
    expect(getMarketStatus('nasdaq', new Date('2026-09-07T15:00:00Z')).phase).toBe('closed');
    expect(text('nasdaq', '2026-11-26T15:00:00Z')).toBe('Fechado, abre amanhã às 11:30 (horário de Brasília)');
    expect(text('nasdaq', '2026-11-27T15:00:00Z')).toBe('Aberto, fecha em 3h 00m');
  });

  it('COMEX: pausa diária e abertura de domingo', () => {
    expect(text('comex', '2026-09-23T21:30:00Z')).toBe('Em pausa, reabre às 19:00 (horário de Brasília)');
    expect(getMarketStatus('comex', new Date('2026-09-27T22:30:00Z')).phase).toBe('open');
    expect(getMarketStatus('comex', new Date('2026-09-26T15:00:00Z')).phase).toBe('closed');
    // quarta 10:00 NY: sessão contínua até 17:00
    expect(text('comex', '2026-09-23T14:00:00Z')).toBe('Aberto, fecha em 7h 00m');
  });

  it('B3 muda o fechamento com o horário de verão dos EUA', () => {
    expect(text('b3', '2026-09-23T14:00:00Z')).toBe('Aberto, fecha em 6h 00m');
    expect(text('b3', '2026-12-02T20:30:00Z')).toBe('Aberto, fecha em 30 min');
    expect(getMarketStatus('b3', new Date('2026-09-23T20:30:00Z')).phase).toBe('closed');
  });

  it('usa "horário local" fora de Brasília', () => {
    expect(text('nasdaq', '2026-09-23T12:00:00Z', 'Europe/Lisbon')).toBe('Fechado, abre às 14:30 (horário local)');
  });

  it('formata durações', () => {
    expect(formatDuration(45 * 60000)).toBe('45 min');
    expect(formatDuration((26 * 60 + 5) * 60000)).toBe('1d 2h');
  });
});
