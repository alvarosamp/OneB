import { useState } from 'react';
import { ArrowUpRight } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { TabbedPage } from '../components/terminal/TabbedPage';
import { DataAge } from '../components/terminal/DataAge';
import { AsyncContent, Badge, ChangeText, ChipGroup, EmptyState, ICON_SM, Input, Section, SkeletonLines, Table, type Column } from '../components/ui';
import { formatCurrency, formatDateTime, formatLongDate, formatNumber, formatPrice, isNum } from '../lib/format';
import { ptBR } from '../lib/text';
import type { EarningsEvent, EconomicEvent, FxQuote, GlobalNewsItem, MacroInstrument, MacroOverview, NewsItem, WatchlistItem } from '../types';
import styles from './Mercado.module.css';

type Tab = 'noticias' | 'calendario' | 'cambio' | 'resultados';

/** Mercado: notícias, calendário econômico, câmbio e juros, resultados. */
export function Mercado() {
  return (
    <TabbedPage<Tab>
      title="Mercado"
      fallback="noticias"
      tabs={[
        { value: 'noticias', label: 'Notícias', render: () => <News /> },
        { value: 'calendario', label: 'Calendário', render: () => <Calendar /> },
        { value: 'cambio', label: 'Câmbio e juros', render: () => <FxRates /> },
        { value: 'resultados', label: 'Resultados', render: () => <Earnings /> },
      ]}
    />
  );
}

function News() {
  const global = useApi<GlobalNewsItem[]>('/api/global-news?limit=60', { pollMs: 5 * 60_000 });
  const perAsset = useApi<NewsItem[]>('/api/news?limit=40', { pollMs: 5 * 60_000 });
  const [minImpact, setMinImpact] = useState<'0' | '20' | '40'>('0');
  return (
    <div className={styles.split}>
      <Section title="Mundo e macro" meta={global.lastUpdated ? <DataAge at={global.lastUpdated} /> : null}
        actions={
          <ChipGroup
            label="Impacto mínimo"
            value={minImpact}
            onChange={setMinImpact}
            items={[
              { value: '0', label: 'Todas' },
              { value: '20', label: 'Impacto médio' },
              { value: '40', label: 'Impacto alto' },
            ]}
          />
        }
      >
        <AsyncContent state={global} loading={<SkeletonLines lines={8} />} empty={<EmptyState title="Sem notícias globais" description="O coletor busca notícias a cada 30 minutos." />} errorTitle="Notícias indisponíveis">
          {(items) => {
            const list = items.filter((n) => n.impact_score >= Number(minImpact));
            return list.length ? (
              <ul className={styles.feed}>
                {list.map((n) => (
                  <li key={n.url}>
                    <a href={n.url} target="_blank" rel="noreferrer" className={styles.headline}>
                      {n.headline}
                      <ArrowUpRight {...ICON_SM} aria-hidden="true" />
                      <span className="sr-only">(abre em nova aba)</span>
                    </a>
                    {n.summary && <p className={styles.summary}>{n.summary}</p>}
                    <span className={styles.meta}>
                      <span>{n.source}</span>
                      <time dateTime={n.published_at}>{formatDateTime(n.published_at)}</time>
                      <span>{ptBR(n.category)}</span>
                      {n.impact_score >= 40 ? <Badge tone="warning">impacto {n.impact_score}</Badge> : <span>impacto {n.impact_score}</span>}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="Nada com esse impacto" description="Reduza o filtro de impacto." />
            );
          }}
        </AsyncContent>
      </Section>
      <Section title="Por ativo da watchlist" meta={perAsset.lastUpdated ? <DataAge at={perAsset.lastUpdated} /> : null}>
        <AsyncContent state={perAsset} loading={<SkeletonLines lines={8} />} empty={<EmptyState title="Sem notícias dos seus ativos" description="Adicione ativos à watchlist para acompanhar notícias por símbolo." />} errorTitle="Notícias indisponíveis">
          {(items) => (
            <ul className={styles.feed}>
              {items.map((n) => (
                <li key={n.url}>
                  <span className={styles.symbol}>{n.symbol}</span>
                  <a href={n.url} target="_blank" rel="noreferrer" className={styles.headline}>
                    {n.headline}
                    <ArrowUpRight {...ICON_SM} aria-hidden="true" />
                    <span className="sr-only">(abre em nova aba)</span>
                  </a>
                  <span className={styles.meta}>
                    <span>{n.source}</span>
                    <time dateTime={n.published_at}>{formatDateTime(n.published_at)}</time>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </AsyncContent>
      </Section>
    </div>
  );
}

const IMPACT: Record<string, { label: string; tone: 'warning' | 'neutral' }> = {
  high: { label: 'alto', tone: 'warning' },
  medium: { label: 'médio', tone: 'neutral' },
  low: { label: 'baixo', tone: 'neutral' },
};

function Calendar() {
  const econ = useApi<EconomicEvent[]>('/api/economic-events?days_ahead=14&limit=80', { pollMs: 30 * 60_000 });
  const [impact, setImpact] = useState<'todos' | 'high'>('todos');
  const columns: Column<EconomicEvent>[] = [
    { key: 'data', header: 'Data', sortValue: (e) => e.event_date, render: (e) => <time className="num" dateTime={e.event_date}>{formatDateTime(e.event_date)}</time> },
    { key: 'evento', header: 'Evento', wrap: true, render: (e) => e.event_name },
    { key: 'pais', header: 'País', render: (e) => e.country },
    { key: 'impacto', header: 'Impacto', sortValue: (e) => (e.impact === 'high' ? 3 : e.impact === 'medium' ? 2 : 1), render: (e) => (IMPACT[e.impact] ? <Badge tone={IMPACT[e.impact].tone}>{IMPACT[e.impact].label}</Badge> : e.impact) },
    { key: 'proj', header: 'Projeção', align: 'right', render: (e) => <span className="num">{e.forecast || '—'}</span> },
    { key: 'ant', header: 'Anterior', align: 'right', render: (e) => <span className="num">{e.previous || '—'}</span> },
  ];
  return (
    <Section
      title="Calendário econômico"
      meta="próximos 14 dias, horário local"
      actions={<ChipGroup label="Impacto" value={impact} onChange={setImpact} items={[{ value: 'todos', label: 'Todos' }, { value: 'high', label: 'Só alto impacto' }]} />}
    >
      <AsyncContent state={econ} loading={<SkeletonLines lines={10} height={20} />} empty={<EmptyState title="Nenhum evento nos próximos 14 dias" description="O calendário é atualizado diariamente." />} errorTitle="Calendário indisponível">
        {(list) => <Table caption="Calendário econômico" columns={columns} rows={impact === 'high' ? list.filter((e) => e.impact === 'high') : list} rowKey={(e) => `${e.event_name}-${e.event_date}`} initialSort={{ key: 'data', dir: 'asc' }} dense />}
      </AsyncContent>
    </Section>
  );
}

const FX_KEYS = ['EURUSD', 'EURBRL', 'DXY'];
const RATE_KEYS = ['US2Y', 'US5Y', 'US10Y', 'US30Y'];
const COMMODITY_KEYS = ['GOLD', 'WTI', 'BRENT'];

function FxRates() {
  const macro = useApi<MacroOverview>('/api/regime/macro', { pollMs: 60_000, isEmpty: (d) => d.instruments.length === 0 });
  const fx = useApi<FxQuote>('/api/fx/usd-brl', { pollMs: 5 * 60_000 });
  const [brl, setBrl] = useState('1000');
  const columns: Column<MacroInstrument>[] = [
    { key: 'nome', header: 'Instrumento', render: (i) => ptBR(i.name) },
    { key: 'simbolo', header: 'Fonte', render: (i) => <span className="muted">{i.symbol}</span> },
    { key: 'preco', header: 'Último', align: 'right', render: (i) => <span className="num">{RATE_KEYS.includes(i.key) ? (isNum(i.price) ? `${formatNumber(i.price, 2)}%` : '—') : formatPrice(i.price, i.key === 'GOLD' ? 'GC=F' : i.key)}</span> },
    { key: 'var', header: 'Variação', align: 'right', render: (i) => (i.price === null ? <span className="muted">—</span> : <ChangeText value={i.change_pct} />) },
    { key: 'idade', header: 'Dados', align: 'right', render: (i) => <DataAge at={i.taken_at} staleAfterMin={60 * 24 * 3} prefix="" /> },
  ];
  const pick = (keys: string[]) => (macro.data?.instruments ?? []).filter((i) => keys.includes(i.key));
  const amount = Number(brl.replace(',', '.'));

  return (
    <div className={styles.fxGrid}>
      <Section title="Dólar comercial">
        <AsyncContent state={fx} loading={<SkeletonLines lines={3} />} empty={<EmptyState title="Sem cotação do USD/BRL" description={fx.error ?? 'O provedor não retornou a cotação agora.'} />} errorTitle="Cotação indisponível">
          {(q) => (
            <div className={styles.fx}>
              <div>
                <span className={styles.fxLabel}>USD/BRL</span>
                <span className={styles.fxPrice}>{formatCurrency(q.rate, 'BRL', 4)}</span>
                <ChangeText value={q.change_pct} />
                <DataAge at={q.updated_at} staleAfterMin={60 * 24} />
              </div>
              <div className={styles.converter}>
                <Input label="Valor em reais (R$)" type="number" min="0" step="0.01" value={brl} onChange={(e) => setBrl(e.target.value)} />
                <p className={styles.converted}>
                  = <strong className="num">{isNum(amount) && amount >= 0 ? formatCurrency(amount / q.rate, 'USD') : '—'}</strong>
                </p>
              </div>
            </div>
          )}
        </AsyncContent>
      </Section>
      <AsyncContent state={macro} loading={<SkeletonLines lines={8} />} empty={<EmptyState title="Sem instrumentos macro" description="O coletor de macro ainda não gravou cotações." />} errorTitle="Macro indisponível">
        {() => (
          <>
            <Section title="Juros dos EUA (Treasuries)" meta="séries diárias do FRED">
              <Table caption="Juros" columns={columns} rows={pick(RATE_KEYS)} rowKey={(i) => i.key} dense />
            </Section>
            <Section title="Moedas e índice do dólar">
              <Table caption="Moedas" columns={columns} rows={pick(FX_KEYS)} rowKey={(i) => i.key} dense />
            </Section>
            <Section title="Commodities">
              <Table caption="Commodities" columns={columns} rows={pick(COMMODITY_KEYS)} rowKey={(i) => i.key} dense />
            </Section>
          </>
        )}
      </AsyncContent>
    </div>
  );
}

function Earnings() {
  const earnings = useApi<EarningsEvent[]>('/api/earnings-events?days_ahead=14&limit=80', { pollMs: 30 * 60_000 });
  const watch = useApi<WatchlistItem[]>('/api/watchlist');
  const [scope, setScope] = useState<'watchlist' | 'todos'>('watchlist');
  const symbols = new Set((watch.data ?? []).map((w) => w.symbol));
  const columns: Column<EarningsEvent>[] = [
    { key: 'data', header: 'Data', sortValue: (e) => e.event_date, render: (e) => <span className="num">{formatLongDate(e.event_date)}</span> },
    { key: 'ativo', header: 'Ativo', sortValue: (e) => e.symbol, render: (e) => <strong>{e.symbol}</strong> },
    { key: 'lpa', header: 'LPA estimado', align: 'right', render: (e) => <span className="num">{formatCurrency(e.eps_estimate)}</span> },
    { key: 'receita', header: 'Receita estimada', align: 'right', render: (e) => <span className="num">{isNum(e.revenue_estimate) ? `US$ ${formatNumber(e.revenue_estimate / 1e9, 1)} bi` : '—'}</span> },
  ];
  return (
    <Section
      title="Resultados trimestrais"
      meta="próximos 14 dias"
      actions={<ChipGroup label="Escopo" value={scope} onChange={setScope} items={[{ value: 'watchlist', label: 'Da watchlist' }, { value: 'todos', label: 'Todos' }]} />}
    >
      <AsyncContent state={earnings} loading={<SkeletonLines lines={8} />} empty={<EmptyState title="Nenhum resultado nos próximos 14 dias" description="Datas de balanço aparecem aqui assim que divulgadas." />} errorTitle="Resultados indisponíveis">
        {(list) => {
          const rows = scope === 'watchlist' && symbols.size ? list.filter((e) => symbols.has(e.symbol)) : list;
          return rows.length ? (
            <Table caption="Resultados" columns={columns} rows={rows} rowKey={(e) => `${e.symbol}-${e.event_date}`} initialSort={{ key: 'data', dir: 'asc' }} dense />
          ) : (
            <EmptyState title="Nenhum ativo da watchlist divulga resultado nos próximos 14 dias" description="Veja todos os resultados no filtro ao lado." />
          );
        }}
      </AsyncContent>
    </Section>
  );
}
