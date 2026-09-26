import { useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { useApi } from '../hooks/useApi';
import { useRadar, type RadarRow } from '../hooks/useRadar';
import { AttentionLevel } from '../components/terminal/AttentionLevel';
import { DataAge } from '../components/terminal/DataAge';
import { DecisionBadge } from '../components/terminal/DecisionBadge';
import { AsyncContent, ChangeText, ChipGroup, EmptyState, PageHeader, SkeletonLines, Table, Tooltip, type Column } from '../components/ui';
import { buttonClass } from '../components/ui/buttonClass';
import { fromBackendAction, STATE_LABEL, type DecisionRead, type DecisionState } from '../lib/decisionState';
import { formatPrice, minutesSince } from '../lib/format';
import { ptBR } from '../lib/text';
import { assetHref } from '../lib/watchlist';
import type { DailyMarketAsset, DailyMarketSummary, DecisionDesk } from '../types';
import styles from './Radar.module.css';

type Filter = 'todos' | DecisionState;
const FILTERS: { value: Filter; label: string }[] = [
  { value: 'todos', label: 'Todos' },
  { value: 'formacao', label: STATE_LABEL.formacao },
  { value: 'observar', label: STATE_LABEL.observar },
  { value: 'sem-setup', label: STATE_LABEL['sem-setup'] },
];

interface Row extends RadarRow {
  daily: DailyMarketAsset | null;
  decision: DecisionRead | null;
}

/** Nota técnica mais específica do resumo diário (proximidade de nível, RSI esticado, volume). */
function setupNote(asset: DailyMarketAsset | null): string | null {
  if (!asset || asset.notes.length === 0) return null;
  const specific = asset.notes.find((n) => /perto|romp|esticad|sobrevend|volume/i.test(n));
  return ptBR((specific ?? asset.notes[0]).replace(/\.$/, ''));
}

const STATE_ORDER: Record<DecisionState, number> = { formacao: 0, observar: 1, 'sem-setup': 2 };

/** Radar: tabela densa e ordenável da watchlist, com atenção explicável e estado. */
export function Radar() {
  const { summary, rows, partialError } = useRadar();
  const daily = useApi<DailyMarketSummary>('/api/reports/daily-summary', { pollMs: 15 * 60_000 });
  const desk = useApi<DecisionDesk>('/api/decision-desk/recommendations', { pollMs: 10 * 60_000 });
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const filter = (FILTERS.some((f) => f.value === params.get('estado')) ? params.get('estado') : 'todos') as Filter;

  const merged = useMemo<Row[]>(() => {
    const assets = daily.data ? [...daily.data.opportunities, ...daily.data.watch, ...daily.data.risks] : [];
    return rows.map((r) => {
      const rec = desk.data?.recommendations.find((x) => x.symbol === r.symbol);
      return { ...r, daily: assets.find((a) => a.symbol === r.symbol) ?? null, decision: rec ? fromBackendAction(rec.action) : null };
    });
  }, [rows, daily.data, desk.data]);

  const counts = merged.reduce<Record<DecisionState, number>>((acc, r) => (r.decision ? ((acc[r.decision.state] += 1), acc) : acc), { formacao: 0, observar: 0, 'sem-setup': 0 });
  const visible = filter === 'todos' ? merged : merged.filter((r) => r.decision?.state === filter);

  function setFilter(f: Filter) {
    const p = new URLSearchParams(params);
    if (f === 'todos') p.delete('estado');
    else p.set('estado', f);
    setParams(p, { replace: true });
  }

  const columns: Column<Row>[] = [
    {
      key: 'ativo',
      header: 'Ativo',
      sortValue: (r) => r.symbol,
      render: (r) => (
        <span className={styles.asset}>
          <strong>{r.symbol}</strong>
          {r.label && r.label !== r.symbol && <span>{r.label}</span>}
        </span>
      ),
    },
    { key: 'preco', header: 'Preço', align: 'right', sortValue: (r) => r.price, render: (r) => <span className="num">{formatPrice(r.price, r.symbol)}</span> },
    { key: 'dia', header: 'Dia', align: 'right', sortValue: (r) => r.change_pct, render: (r) => (r.price === null ? <span className="muted">—</span> : <ChangeText value={r.change_pct} />) },
    {
      key: 'tendencia',
      header: 'Tendência',
      sortValue: (r) => r.daily?.score ?? null,
      render: (r) => (r.daily ? <span>{ptBR(r.daily.trend)}</span> : <span className="muted">sem leitura</span>),
    },
    { key: 'setup', header: 'Setup', wrap: true, render: (r) => <span className={styles.setup}>{setupNote(r.daily) ?? '—'}</span> },
    { key: 'atencao', header: 'Atenção', sortValue: (r) => r.attention.total, render: (r) => <AttentionLevel score={r.attention} /> },
    {
      key: 'dados',
      header: 'Dados',
      align: 'right',
      sortValue: (r) => minutesSince(r.taken_at),
      render: (r) => <DataAge at={r.taken_at} staleAfterMin={30} prefix="" />,
    },
    {
      key: 'estado',
      header: 'Estado',
      sortValue: (r) => (r.decision ? STATE_ORDER[r.decision.state] : 9),
      render: (r) =>
        r.decision ? (
          <DecisionBadge state={r.decision.state} bias={r.decision.bias} size="sm" />
        ) : desk.status === 'loading' ? (
          <span className="muted">calculando…</span>
        ) : (
          <Tooltip content={desk.error ?? 'A mesa de decisão não avaliou este ativo.'}>
            <span className="muted" tabIndex={0}>
              sem leitura
            </span>
          </Tooltip>
        ),
    },
  ];

  return (
    <div className={styles.page}>
      <PageHeader
        title="Radar"
        description="Ativos da watchlist ordenados por atenção. Clique numa linha para abrir o gráfico."
        actions={summary.lastUpdated ? <DataAge at={summary.lastUpdated} refreshing={summary.refreshing} refreshError={summary.data ? summary.error : null} /> : null}
      />

      <ChipGroup
        label="Filtrar por estado"
        items={FILTERS.map((f) => ({ ...f, count: f.value === 'todos' ? merged.length : counts[f.value] }))}
        value={filter}
        onChange={setFilter}
      />

      {(partialError || daily.status === 'error' || desk.status === 'error') && (
        <p className={styles.partial}>
          {[partialError, daily.status === 'error' ? 'Tendência e setup indisponíveis (resumo diário falhou).' : null, desk.status === 'error' ? 'Estado indisponível (mesa de decisão falhou).' : null]
            .filter(Boolean)
            .join(' ')}
        </p>
      )}

      <AsyncContent
        state={summary}
        loading={<SkeletonLines lines={10} height={20} />}
        empty={
          <EmptyState
            title="Nenhum ativo monitorado"
            description="Adicione um ativo à watchlist para ver o radar."
            action={
              <Link to="/watchlist" className={buttonClass({ variant: 'primary', size: 'sm' })}>
                Adicionar à watchlist
              </Link>
            }
          />
        }
        errorTitle="Não foi possível carregar o radar"
      >
        {() => (
          <Table
            caption="Radar de ativos"
            columns={columns}
            rows={visible}
            rowKey={(r) => r.id}
            onRowClick={(r) => navigate(assetHref(r.symbol))}
            rowLabel={(r) => `Abrir ${r.symbol}`}
            initialSort={{ key: 'atencao', dir: 'desc' }}
            stickyFirstColumn
            empty={<EmptyState title={`Nenhum ativo em “${FILTERS.find((f) => f.value === filter)?.label}”`} description="Troque o filtro para ver os demais ativos." />}
          />
        )}
      </AsyncContent>
      <p className={styles.note}>
        Atenção combina movimento do dia, notícias, alertas, eventos e qualidade do dado; passe o mouse ou o foco no nível para ver as contribuições. Estado vem da mesa de decisão do backend.
      </p>
    </div>
  );
}
