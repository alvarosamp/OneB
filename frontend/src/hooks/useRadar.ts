import { useMemo } from 'react';
import { useApi } from './useApi';
import { attentionScore, type AttentionScore } from '../lib/attentionScore';
import type { DashboardRow, DashboardSummary, EarningsEvent, NewsItem } from '../types';

export interface RadarRow extends DashboardRow {
  attention: AttentionScore;
  newsCount: number;
  alertCount: number;
  hasEarnings: boolean;
}

function count<T extends { symbol: string }>(items: T[] | null, symbol: string) {
  return items ? items.filter((i) => i.symbol === symbol).length : 0;
}

/**
 * Linhas do radar com score de atenção. Notícias e earnings são opcionais:
 * se falharem, o radar continua (com esses componentes zerados) e o erro
 * fica disponível para aviso.
 */
export function useRadar() {
  const summary = useApi<DashboardSummary>('/api/dashboard-summary', { pollMs: 20_000, isEmpty: (d) => d.rows.length === 0 });
  const news = useApi<NewsItem[]>('/api/news?limit=30', { pollMs: 5 * 60_000 });
  const earnings = useApi<EarningsEvent[]>('/api/earnings-events?days_ahead=7&limit=50', { pollMs: 30 * 60_000 });

  const rows = useMemo<RadarRow[]>(() => {
    const data = summary.data;
    if (!data) return [];
    return data.rows
      .map((row) => {
        const newsCount = count(news.data, row.symbol);
        const alertCount = count(data.alerts, row.symbol);
        const hasEarnings = count(earnings.data, row.symbol) > 0;
        return {
          ...row,
          newsCount,
          alertCount,
          hasEarnings,
          attention: attentionScore({ symbol: row.symbol, price: row.price, changePct: row.change_pct, takenAt: row.taken_at, newsCount, alertCount, hasEarnings }),
        };
      })
      .sort((a, b) => b.attention.total - a.attention.total);
  }, [summary.data, news.data, earnings.data]);

  const partialError = news.status === 'error' || earnings.status === 'error' ? 'Notícias ou earnings indisponíveis: o score ignora esses componentes.' : null;
  return { summary, rows, partialError };
}
