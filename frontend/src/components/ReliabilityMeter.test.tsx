import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { Reliability } from '../types';
import { ReliabilityChip, ReliabilityMeter } from './ReliabilityMeter';

const reliability: Reliability = {
  method: 'reliability_v1',
  score: 38,
  raw_score: 64,
  grade: 'INSUFICIENTE',
  label: 'Evidência insuficiente',
  components: [
    { key: 'backtest', label: 'Histórico do padrão', weight: 30, available: true, score: 70, detail: '40/60 acertos' },
    { key: 'model', label: 'Modelo validado', weight: 20, available: false, score: null, detail: 'Nenhum modelo' },
  ],
  caps: [{ key: 'EVIDENCE_SAMPLES', limit: 40, reason: 'Só 12 casos de evidência; mínimo 30.' }],
  limiting_factor: 'Só 12 casos de evidência; mínimo 30.',
  evidence_samples: 12,
  disclaimer: 'Mede quanta evidência sustenta o sinal; não é probabilidade de acerto.',
};

describe('ReliabilityMeter', () => {
  it('mostra nota, fator limitante, componentes sem evidência e travas', () => {
    render(<ReliabilityMeter value={reliability} />);
    expect(screen.getByRole('meter')).toHaveAttribute('aria-valuenow', '38');
    expect(screen.getByText(/Insuficiente/)).toBeInTheDocument();
    expect(screen.getAllByText(/Só 12 casos de evidência/).length).toBeGreaterThan(0);
    expect(screen.getByText('sem evidência')).toBeInTheDocument();
    expect(screen.getByText('máx. 40')).toBeInTheDocument();
    expect(screen.getByText(/não é probabilidade de acerto/)).toBeInTheDocument();
  });

  it('não renderiza nada sem dado e o chip mostra traço', () => {
    const { container } = render(<ReliabilityMeter value={null} />);
    expect(container).toBeEmptyDOMElement();
    render(<ReliabilityChip value={undefined} />);
    expect(screen.getByText('-')).toBeInTheDocument();
  });
});
