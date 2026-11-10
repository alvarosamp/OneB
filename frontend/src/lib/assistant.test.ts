import { describe, expect, it } from 'vitest';
import { firstSentence, planStatusLabel, readCopilot, splitAnswer, voteLabel } from './assistant';
import type { CopilotAnalysis } from '../types';

const base = { votes: [{ name: 'Tecnico', vote: 'Comprar', confidence: 70, summary: '', evidence: [] }] } as unknown as CopilotAnalysis;

describe('assistant', () => {
  it('traduz o viés do Copiloto para o vocabulário da UI', () => {
    expect(readCopilot({ ...base, bias: 'OBSERVAR_COMPRA' })).toEqual({ state: 'formacao', bias: 'alta' });
    expect(readCopilot({ ...base, bias: 'AGUARDAR_CONFIRMACAO' })).toEqual({ state: 'observar', bias: 'alta' });
    expect(readCopilot({ ...base, bias: 'EVITAR_POR_ENQUANTO' }).state).toBe('sem-setup');
  });

  it('nunca exibe verbos de ordem', () => {
    expect(voteLabel('Comprar')).toBe('Construtivo');
    expect(voteLabel('Evitar')).toBe('Desfavorável');
    expect(planStatusLabel('NÃO OPERAR')).not.toMatch(/operar/i);
  });

  it('separa conclusão, itens e parágrafos', () => {
    const r = splitAnswer('NVDA subiu com volume. Há risco de earnings.\n- RSI 72\n- Volume 2x\nOutro ponto.');
    expect(r.conclusion).toBe('NVDA subiu com volume.');
    expect(r.points).toEqual(['RSI 72', 'Volume 2x']);
    expect(r.rest).toEqual(['Há risco de earnings.', 'Outro ponto.']);
    expect(firstSentence('Sem ponto final')).toBe('Sem ponto final');
  });
});
