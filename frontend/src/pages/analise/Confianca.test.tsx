import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { useApiMock } = vi.hoisted(() => ({ useApiMock: vi.fn() }));
vi.mock('../../hooks/useApi', () => ({ useApi: useApiMock }));

import { Confianca } from './Confianca';

const ready = <T,>(data: T) => ({ data, status: 'ready', error: null, errorStatus: null, lastUpdated: new Date(), refreshing: false, retry: vi.fn(), mutate: vi.fn() });

const cell = (key: string, part: 'live' | 'retro', direction: 'long' | 'short', target_r: number, hits: number, closed: number, consistent: boolean) => ({
  key, label: key, part, direction, status: 'acumulando', target_r, announced: 0.48, hits, closed, consistent,
});

const base = {
  forecast: [{ key: 'NAS100', label: 'Nasdaq 100', error_reduction: 0.12, coverage80: 0.79, test_days: 900 }],
  forecast_pass: true,
  forecast_mean_reduction: 0.1,
  live: [],
  events: [],
  odds: [],
  promise_test: [],
  promise_period: '2025 a 2026',
  not_promised: [{ title: 'Sinais de compra e venda por indicadores', detail: 'nenhuma sobreviveu' }],
  replay: [
    { key: 'NAS100', label: 'Nasdaq 100', rule: 'aleatorio', rule_label: 'cara ou coroa', trades: 4615, mean_r: -0.025, final_balance: 288, passed: false },
    { key: 'XAUUSD', label: 'Ouro', rule: 'acompanha_24h', rule_label: 'acompanhar as últimas 24 h', trades: 4734, mean_r: 0.016, final_balance: 1375, passed: false },
  ],
  replay_passed: [],
  plan_live_start: '2026-10-15',
  plan_live_retro_from: '2026-08-05',
};

describe('Por que confiar', () => {
  beforeEach(() => useApiMock.mockReset());

  it('mostra a conferência retroativa enquanto o placar ao vivo não tem plano encerrado', () => {
    useApiMock.mockReturnValue(ready({ ...base, plan_live: [
      cell('NAS100', 'retro', 'long', 1, 24, 49, true), cell('NAS100', 'retro', 'short', 1, 23, 49, false),
      cell('NAS100', 'live', 'long', 1, 0, 0, false),
    ] }));
    render(<Confianca />);
    expect(screen.getByText('1 de 2 alvos dentro da faixa')).toBeInTheDocument();
    expect(screen.getByText(/O placar ao vivo começa em 15\/10; abaixo, a conferência dos dias anteriores \(desde 05\/08\)/)).toBeInTheDocument();
    expect(screen.getByText(/24 de 49 \(anunciado 48%\) ✓/)).toBeInTheDocument();
    expect(screen.getByText(/23 de 49 \(anunciado 48%\) ✗/)).toBeInTheDocument();
  });

  it('troca para o placar ao vivo quando há plano encerrado e mostra a simulação sem regra aprovada', () => {
    useApiMock.mockReturnValue(ready({ ...base, plan_live: [
      cell('NAS100', 'retro', 'long', 1, 24, 49, true), cell('NAS100', 'live', 'long', 1, 1, 1, true),
    ] }));
    render(<Confianca />);
    expect(screen.getByText(/Placar ao vivo desde 15\/10\./)).toBeInTheDocument();
    expect(screen.getByText('1 de 1 alvos dentro da faixa')).toBeInTheDocument();
    expect(screen.getByText('Nenhuma regra aprovada')).toBeInTheDocument();
    expect(screen.getByText('US$ 288')).toBeInTheDocument();
    expect(screen.getByText('US$ 1.375')).toBeInTheDocument();
  });

  it('mostra o diário com previsto, realizado e os planos do dia', () => {
    useApiMock.mockReturnValue(ready({ ...base, plan_live: [], diary: [
      { date: '2026-10-15', assets: [{ key: 'NAS100', label: 'Nasdaq 100', range: { expected_pct: 1.44, low80_pct: 0.86, high80_pct: 2.42, realized_pct: 2.6, inside80: false, event: true },
        plans: { long: { '1': 'hit', '2': 'hit', '3': 'open' }, short: { '1': 'stop', '2': 'stop', '3': 'stop' } } }] },
    ] }));
    render(<Confianca />);
    expect(screen.getByText('Diário: o que o OneB disse e o que aconteceu')).toBeInTheDocument();
    expect(screen.getByText('1,44% (0,86–2,42%) · evento')).toBeInTheDocument();
    expect(screen.getByText('2,60% ✗')).toBeInTheDocument();
    expect(screen.getByText('alvo / alvo')).toBeInTheDocument();
    expect(screen.getByText('stop / stop')).toBeInTheDocument();
  });
});
