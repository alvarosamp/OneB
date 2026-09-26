import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { apiGetMock, usePollingMock } = vi.hoisted(() => ({
  apiGetMock: vi.fn(),
  usePollingMock: vi.fn(),
}));

vi.mock('../api/client', () => ({ api: { get: apiGetMock } }));
vi.mock('../hooks/usePolling', () => ({ usePolling: usePollingMock }));

import { Regime } from './Regime';

const report = {
  symbol: 'NASDAQ',
  local_regime: null,
  macro_context: 'NEUTRO',
  cross_asset_relevance: [],
};

const treasury = {
  key: 'US10Y',
  symbol: 'DGS10',
  name: 'Treasury 10 anos (yield)',
  price: 4.25,
  change_pct: null,
  taken_at: null,
  context: 'Referência global de desconto.',
  trend: {
    direction: 'ALTA FORTE',
    score: 72,
    strength: 'FORTE',
    adx14: 31.4,
    change_5d: 5,
    change_20d: -3.2,
    change_60d: null,
    change_unit: 'bps',
    last: 4.25,
    ema20: 4.2,
    ema50: 4.1,
    as_of: '2026-09-14T00:00:00+00:00',
    age_days: 0,
  },
};

const correlationWindow = (sessions: number, correlation: number) => ({
  sessions,
  minimum_observations: 12,
  matrix: [
    { key: 'NASDAQ', values: { NASDAQ: 1, DXY: correlation } },
    { key: 'DXY', values: { NASDAQ: correlation, DXY: 1 } },
  ],
  strongest_positive: [{ left: 'NASDAQ', right: 'SP500', correlation: 0.8, observations: sessions }],
  strongest_negative: [{ left: 'NASDAQ', right: 'DXY', correlation, observations: sessions }],
});

describe('Regime trend radar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiGetMock.mockResolvedValue(report);
    usePollingMock.mockReturnValue({
      data: {
        instruments: [treasury],
        trend_watchlist: [treasury],
        correlation_windows: {
          '20': correlationWindow(20, -0.25),
          '60': correlationWindow(60, -0.72),
        },
        relationship_dynamics: [{
          left: 'GOLD',
          right: 'WTI',
          correlation_20d: -0.55,
          correlation_60d: 0.2,
          delta: -0.75,
          strength_delta: 0.35,
          status: 'INVERSAO',
        }],
        lead_lag_candidates: [{
          leader: 'US10Y',
          follower: 'NASDAQ',
          lag_sessions: 2,
          correlation: -0.61,
          contemporaneous_correlation: -0.2,
          improvement: 0.41,
          observations: 60,
        }],
        history_status: {
          days_recorded: 8,
          latest: {
            snapshot_date: '2026-09-14',
            captured_at: '2026-09-14T21:00:00Z',
            coverage_pct: 91.7,
            fresh_count: 10,
            stale_count: 1,
            missing_count: 1,
          },
          lead_lag_validation: [{
            leader: 'US10Y',
            follower: 'NASDAQ',
            lag_sessions: 2,
            observations_days: 5,
            persistence_pct: 62.5,
            average_correlation: -0.58,
            last_seen: '2026-09-14',
            status: 'RECORRENTE',
          }],
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
            status: 'COLETANDO_HISTORICO',
            correlations: [],
            warnings: [],
          },
        },
        nasdaq_cross_asset_relevance: [],
      },
      lastUpdated: new Date('2026-09-14T12:00:00Z'),
      error: null,
    });
  });

  it('renders direction, strength and horizon changes with the correct yield unit', async () => {
    render(<Regime />);

    expect(screen.getByRole('heading', { name: 'Radar de tendências' })).toBeInTheDocument();
    expect(screen.getByText('Treasury 10 anos (yield)')).toBeInTheDocument();
    expect(screen.getByText('ALTA FORTE (72)')).toHaveClass('up');
    expect(screen.getByText('FORTE · ADX 31.4')).toBeInTheDocument();
    expect(screen.getByText('+5.0 bps')).toHaveClass('up');
    expect(screen.getByText('-3.2 bps')).toHaveClass('down');
    expect(screen.getByText('-', { selector: 'td' })).toHaveClass('muted');
    await waitFor(() => expect(apiGetMock).toHaveBeenCalledWith('/api/regime/NASDAQ'));
  });

  it('loads the detailed report and synchronizes the input when a row is clicked', async () => {
    const user = userEvent.setup();
    render(<Regime />);

    await user.click(screen.getByText('Treasury 10 anos (yield)'));

    await waitFor(() => expect(apiGetMock).toHaveBeenCalledWith('/api/regime/US10Y'));
    expect(screen.getByPlaceholderText('Ex: NASDAQ, AAPL, GOLD, SP500')).toHaveValue('US10Y');
  });

  it('shows the full cross-asset matrix and switches correlation horizon', async () => {
    const user = userEvent.setup();
    render(<Regime />);

    expect(screen.getByRole('heading', { name: 'Correlação móvel' })).toBeInTheDocument();
    expect(screen.getByText('NASDAQ × DXY')).toBeInTheDocument();
    expect(screen.getAllByText('-0.72')).not.toHaveLength(0);
    expect(screen.getByText('GOLD × WTI')).toBeInTheDocument();
    expect(screen.getByText('INVERSAO')).toBeInTheDocument();
    expect(screen.getByText('US10Y → NASDAQ')).toBeInTheDocument();
    expect(screen.getByText('2 sessões')).toBeInTheDocument();
    expect(screen.getByText('8 pregões')).toBeInTheDocument();
    expect(screen.getByText('91.7%')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Notícias × mercado' })).toBeInTheDocument();
    expect(screen.getByText('14')).toBeInTheDocument();
    expect(screen.getByText('4 de alto impacto')).toBeInTheDocument();
    expect(screen.getByText('politica monetaria')).toBeInTheDocument();
    expect(screen.getByText(/8\/20 pares notícia/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '20 sessões' }));

    expect(screen.getAllByText('-0.25')).not.toHaveLength(0);
    expect(screen.queryByText('-0.72')).not.toBeInTheDocument();
  });

  it('keeps the empty state compatible with an older API response', () => {
    usePollingMock.mockReturnValue({
      data: { instruments: [], nasdaq_cross_asset_relevance: [] },
      lastUpdated: null,
      error: null,
    });

    render(<Regime />);

    expect(screen.getByText(/Ainda sem snapshots/)).toBeInTheDocument();
  });

});
