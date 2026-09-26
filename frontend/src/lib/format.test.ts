import { describe, expect, it } from 'vitest';
import { formatAge, formatCurrency, formatPrice, formatSignedPct, minutesSince } from './format';

describe('format', () => {
  it('formata moeda com símbolo explícito', () => {
    expect(formatCurrency(1234.5, 'USD')).toBe('US$ 1.234,50');
    expect(formatCurrency(5.4231, 'BRL', 4)).toBe('R$ 5,4231');
  });

  it('nunca transforma ausência em zero', () => {
    expect(formatCurrency(null)).toBe('—');
    expect(formatSignedPct(undefined)).toBe('—');
    expect(formatSignedPct(0)).toBe('0,00%');
  });

  it('usa sinal explícito em variações', () => {
    expect(formatSignedPct(1.234)).toBe('+1,23%');
    expect(formatSignedPct(-0.5)).toBe('−0,50%');
  });

  it('calcula idade do dado', () => {
    const now = new Date('2026-09-23T15:00:00Z');
    expect(minutesSince('2026-09-23T14:57:00Z', now)).toBe(3);
    expect(formatAge('2026-09-23T14:57:00Z', now)).toBe('há 3 min');
    expect(formatAge('2026-09-23T12:00:00Z', now)).toBe('há 3 h');
    expect(formatAge(null, now)).toBe('sem dado');
  });

  it('trata ISO sem fuso como UTC', () => {
    const now = new Date('2026-09-23T15:00:00Z');
    expect(formatAge('2026-09-23T14:30:00', now)).toBe('há 30 min');
    expect(formatAge('2026-09-23T14:30:00.123456', now)).toBe('há 30 min');
  });

  it('formata preço conforme o instrumento', () => {
    expect(formatPrice(4.25, 'US10Y')).toBe('4,25%');
    expect(formatPrice(18.2, 'VIX')).toBe('18,20');
    expect(formatPrice(2650, 'GC=F')).toBe('US$ 2.650,00');
  });
});
