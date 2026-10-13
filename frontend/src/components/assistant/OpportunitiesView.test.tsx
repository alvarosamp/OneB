import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { Opportunity } from '../../types';
import { completedSteps } from '../../lib/setupState';

const opportunity: Opportunity = {
  opportunity_id: 'gold:1',
  symbol: 'XAUUSD.s',
  setup: 'gold_fakeout_open',
  setup_version: 'v',
  state: 'WAITING_CONFIRMATION_2',
  direction: 'long',
  approval: 'SHADOW',
  data_as_of: '2026-10-05T10:10:00+00:00',
  progress: 0.7,
  levels: null,
  research_plan: { entry: 4125.1, stop: 4114.8, target: 4140.55, time_stop_minutes: 240, reward_to_risk: 1.5, notice: '' },
  evidence: [{ evidence_id: 'ev:1', kind: 'transition', text: 'Confirmação 1: fechamento manteve o rompimento.', value: null, source: 'ledger', as_of: null }],
  counter_evidence: [],
  reliability: null,
};

const evidence = {
  setup: 'gold_fakeout_open_v1',
  approval: 'SHADOW',
  data: { sessions: 145, first: '2026-04-10T20:25:00', last: '2026-09-25T18:10:00', clock: 'ASSUMED_UNVERIFIED' },
  summary: { completed_trades: 71, expectancy_r: -0.1503, expectancy_ci95: [-0.379, 0.0925], win_rate: 0.3521, profit_factor: 0.7291, max_drawdown_r: 12.2 },
  verdict: { status: 'COLLECTING', reason: 'Amostra abaixo do mínimo.', progress: { sessions: '145/250', trades: '71/100', pct: 58 } },
  baselines: { random_entry: { p05: -0.28, p50: -0.01, p95: 0.19 }, strategy_percentile_vs_random: 20, plain_breakout: { completed_trades: 272, expectancy_r: -0.133, expectancy_ci95: [-0.26, 0.0] } },
};

vi.mock('../../hooks/useApi', () => ({
  useApi: (path: string) => {
    const base = { status: 'ready', error: null, errorStatus: null, lastUpdated: null, refreshing: false, retry: () => {}, mutate: () => {} };
    if (path.startsWith('/api/opportunities/changes')) return { ...base, data: { summary: '0 nova(s), 1 avanço(s) de estado, 0 encerrada(s).' } };
    if (path.includes('/evidence')) return { ...base, data: evidence };
    return { ...base, data: { opportunities: [opportunity] } };
  },
}));

describe('OpportunitiesView', () => {
  it('mostra estado da máquina, plano de pesquisa rotulado e evidência do setup', async () => {
    const { OpportunitiesView } = await import('./OpportunitiesView');
    render(<OpportunitiesView />);
    expect(screen.getAllByText('Aguardando confirmação 2').length).toBeGreaterThan(0);
    expect(screen.getByText('Plano de pesquisa (não é recomendação)')).toBeInTheDocument();
    expect(screen.getByText('Shadow (sem ordens)')).toBeInTheDocument();
    expect(screen.getByText('Coletando evidência')).toBeInTheDocument();
    expect(screen.getByText(/145\/250 sessões/)).toBeInTheDocument();
    expect(screen.getByText(/percentil 20/)).toBeInTheDocument();
  });

  it('conta etapas concluídas e trata falhas como terminais', () => {
    expect(completedSteps('WAITING_CONFIRMATION_2')).toBe(2);
    expect(completedSteps('INVALIDATED')).toBeNull();
  });
});
