import { describe, expect, it } from 'vitest';
import { parseMoney } from './money';

describe('parseMoney', () => {
  it('aceita formatos brasileiros e simples', () => {
    expect(parseMoney('1.500,50')).toBe(1500.5);
    expect(parseMoney('R$ 2.000')).toBe(2000);
    expect(parseMoney('1500.5')).toBe(1500.5);
    expect(parseMoney('6,5')).toBe(6.5);
    expect(parseMoney('')).toBe(0);
    expect(parseMoney('abc')).toBeNaN();
  });
});
