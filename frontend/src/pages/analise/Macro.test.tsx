import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MacroOverview } from '../../types';

const { useApiMock } = vi.hoisted(() => ({ useApiMock: vi.fn() }));
vi.mock('../../hooks/useApi', () => ({ useApi: useApiMock }));

import { formatTrendChange, themeLabel } from '../../lib/macro';
import { Macro } from './Macro';

const treasury = {
  key: 'US10Y',
  symbol: 'DGS10',
  name: 'Treasury 10 anos (yield)',
  price: 4.25,
  change_pct: null,
  taken_at: null,
  context: 'Referência global de desconto.',
  trend: {
    direction: 'ALTA FORTE' as const,
    score: 72,
    strength: 'FORTE' as const,
    adx14: 31.4,
    change_5d: 5,
    change_20d: -3.2,
    change_60d: null,
    change_unit: 'bps' as const,
    last: 4.25,
    ema20: 4.2,
    ema50: 4.1,
    as_of: '2026-09-14T00:00:00+00:00',
    age_days: 0,
  },
};

const windowOf = (sessions: number, correlation: number) => ({
  sessions,
  minimum_observations: 12,
  matrix: [
    { key: 'NASDAQ', values: { NASDAQ: 1, DXY: correlation } },
    { key: 'DXY', values: { NASDAQ: correlation, DXY: 1 } },
  ],
  strongest_positive: [{ left: 'NASDAQ', right: 'SP500', correlation: 0.8, observations: sessions }],
  strongest_negative: [{ left: 'NASDAQ', right: 'DXY', correlation, observations: sessions }],
});

const full: MacroOverview = {
  instruments: [treasury],
  trend_watchlist: [treasury],
  correlation_windows: {
    '20': windowOf(20, -0.25), '60': windowOf(60, -0.72),
    '3m': windowOf(63, -0.5), '6m': windowOf(126, -0.3), '12m': windowOf(252, -0.1),
  },
  relationship_dynamics: [
    { left: 'GOLD', right: 'WTI', correlation_20d: -0.55, correlation_60d: 0.2, delta: -0.75, strength_delta: 0.35, status: 'INVERSAO' },
  ],
  lead_lag_candidates: [
    { leader: 'US10Y', follower: 'NASDAQ', lag_sessions: 2, correlation: -0.61, contemporaneous_correlation: -0.2, improvement: 0.41, observations: 60 },
  ],
  history_status: {
    days_recorded: 8,
    latest: { snapshot_date: '2026-09-14', captured_at: '2026-09-14T21:00:00Z', coverage_pct: 91.7, fresh_count: 10, stale_count: 1, missing_count: 1 },
    lead_lag_validation: [
      { leader: 'US10Y', follower: 'NASDAQ', lag_sessions: 2, observations_days: 5, persistence_pct: 62.5, average_correlation: -0.58, last_seen: '2026-09-14', status: 'RECORRENTE' },
    ],
    latest_news_context: {
      window_start: '2026-09-13T21:00:00Z',
      window_end: '2026-09-14T21:00:00Z',
      article_count: 14,
      high_impact_count: 4,
      impact_sum: 420,
      average_impact: 30,
      maximum_impact: 70,
      mean_sentiment: null,
      sentiment_observations: 0,
      sentiment_coverage_pct: 0,
      theme_counts: { POLITICA_MONETARIA: 5, ENERGIA: 3 },
      top_headlines: [],
    },
    news_market_analysis: {
      method: 'noticias_t_para_movimento_na_coleta_seguinte',
      minimum_observations: 20,
      available_forward_pairs: 8,
      sessions_recorded: 18,
      news_days: 9,
      status: 'COLETANDO_HISTORICO',
      correlations: [],
      warnings: [],
      windows: {
        '3m': { method: 'forward', minimum_observations: 20, available_forward_pairs: 8, sessions_recorded: 18, news_days: 9, expected_sessions_approx: 63, status: 'COLETANDO_HISTORICO', correlations: [], warnings: [] },
        '6m': { method: 'forward', minimum_observations: 20, available_forward_pairs: 12, sessions_recorded: 55, news_days: 13, expected_sessions_approx: 126, status: 'COLETANDO_HISTORICO', correlations: [], warnings: [] },
        '12m': { method: 'forward', minimum_observations: 20, available_forward_pairs: 13, sessions_recorded: 80, news_days: 14, expected_sessions_approx: 252, status: 'COLETANDO_HISTORICO', correlations: [], warnings: [] },
      },
    },
  },
  nasdaq_cross_asset_relevance: [],
};

function ready(data: MacroOverview) {
  return { data, status: 'ready', error: null, errorStatus: null, lastUpdated: Date.now(), refreshing: false, retry: vi.fn(), mutate: vi.fn() };
}

function Where() {
  const loc = useLocation();
  return <p data-testid="where">{loc.pathname + loc.search}</p>;
}

function renderMacro() {
  return render(
    <MemoryRouter initialEntries={['/analise?tab=macro']}>
      <Routes>
        <Route path="/analise" element={<><Macro /><Where /></>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Análise › Macro', () => {
  beforeEach(() => useApiMock.mockReturnValue(ready(full)));

  it('formata variação de juros em pontos-base e demais em percentual', () => {
    expect(formatTrendChange(5, 'bps')).toBe('+5,0 bps');
    expect(formatTrendChange(-3.2, 'bps')).toMatch(/^[-−]3,2 bps$/);
    expect(formatTrendChange(1.234, '%')).toBe('+1,23%');
    expect(formatTrendChange(null, '%')).toBe('—');
    expect(themeLabel('POLITICA_MONETARIA')).toBe('política monetária');
  });

  it('mostra direção, força e horizontes no radar de tendências', () => {
    renderMacro();
    const table = screen.getByRole('table', { name: 'Radar de tendências' });
    const row = within(table).getByText('Treasury 10 anos (yield)').closest('tr')!;
    expect(within(row).getByText(/Alta forte/)).toHaveClass('up');
    expect(within(row).getByText('Forte')).toBeInTheDocument();
    expect(within(row).getByText(/ADX 31,4/)).toBeInTheDocument();
    expect(within(row).getByText('+5,0 bps')).toHaveClass('up');
    expect(within(row).getByText(/3,2 bps/)).toHaveClass('down');
    expect(within(row).getByText('hoje')).toBeInTheDocument();
  });

  it('abre o regime do instrumento ao clicar na linha', async () => {
    const user = userEvent.setup();
    renderMacro();
    await user.click(within(screen.getByRole('table', { name: 'Radar de tendências' })).getByText('Treasury 10 anos (yield)'));
    expect(screen.getByTestId('where')).toHaveTextContent('/analise?tab=regime&symbol=US10Y');
  });

  it('mostra matriz, mudanças, antecedências e troca a janela', async () => {
    const user = userEvent.setup();
    renderMacro();
    expect(screen.getAllByText('NASDAQ × DXY').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/0,72/).length).toBeGreaterThan(0);
    expect(screen.getByText('GOLD × WTI')).toBeInTheDocument();
    expect(screen.getByText('Inversão')).toBeInTheDocument();
    expect(screen.getByText('US10Y antecede NASDAQ')).toBeInTheDocument();
    expect(screen.getByText('8 pregões')).toBeInTheDocument();
    expect(screen.getByText('91,7%')).toBeInTheDocument();
    expect(screen.getByText('4 de alto impacto')).toBeInTheDocument();
    expect(screen.getByText('política monetária')).toBeInTheDocument();
    expect(screen.getByText('8 de 20')).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: '20 sessões' }));
    expect(screen.getAllByText(/0,25/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/0,72/)).not.toBeInTheDocument();
  });

  it('continua compatível com a resposta antiga da API', () => {
    useApiMock.mockReturnValue(ready({ instruments: [treasury], nasdaq_cross_asset_relevance: [] }));
    renderMacro();
    expect(screen.getAllByText(/Ainda sem snapshots/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Ainda não há histórico comum/)).toBeInTheDocument();
  });

  it('seleciona semestres para preços e um ano para notícias na página ativa', async () => {
    const user = userEvent.setup();
    renderMacro();

    await user.click(within(screen.getByRole('tablist', { name: 'Janela de correlação' })).getByRole('tab', { name: '6 meses' }));
    expect(screen.getAllByText(/0,30/).length).toBeGreaterThan(0);

    await user.click(within(screen.getByRole('tablist', { name: 'Período de notícias' })).getByRole('tab', { name: '12 meses' }));
    expect(screen.getByText(/80 pregões registrados de aproximadamente 252/)).toBeInTheDocument();
    expect(screen.getByText(/13 de 20/)).toBeInTheDocument();
  });
});
