import { describe, expect, it } from 'vitest';
import { biasFromLabel, fromBackendAction, STATE_LABEL } from './decisionState';

describe('decisionState', () => {
  it('traduz as ações do backend sem verbos de ordem', () => {
    expect(fromBackendAction('BUY_CONTROLLED')).toEqual({ state: 'formacao', bias: 'alta' });
    expect(fromBackendAction('SELL_SHORT')).toEqual({ state: 'formacao', bias: 'baixa' });
    expect(fromBackendAction('WATCH_BUY')).toEqual({ state: 'observar', bias: 'alta' });
    expect(fromBackendAction('WATCH_SHORT')).toEqual({ state: 'observar', bias: 'baixa' });
    expect(fromBackendAction('NO_TRADE').state).toBe('sem-setup');
    expect(fromBackendAction(undefined).state).toBe('sem-setup');
    for (const label of Object.values(STATE_LABEL)) {
      expect(label).not.toMatch(/operar|comprar|vender/i);
    }
  });

  it('lê viés de rótulos variados', () => {
    expect(biasFromLabel('ALTISTA')).toBe('alta');
    expect(biasFromLabel('STRONG BEAR')).toBe('baixa');
    expect(biasFromLabel('NEUTRO')).toBeNull();
  });
});
