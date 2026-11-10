import { Link, useSearchParams } from 'react-router-dom';
import { BellPlus, MessagesSquare } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { RULE_META } from '../hooks/useRuleConditions';
import { DataAge } from '../components/terminal/DataAge';
import { AsyncContent, Badge, EmptyState, ICON, PageHeader, Select, SkeletonLines, Table, type Column } from '../components/ui';
import { buttonClass } from '../components/ui/buttonClass';
import { formatDateTime } from '../lib/format';
import { ruleTypeLabel } from '../lib/rules';
import { ptBR } from '../lib/text';
import { assetHref } from '../lib/watchlist';
import type { AlertLog, WatchlistItem } from '../types';
import styles from './Alertas.module.css';

/** Histórico de alertas disparados, filtrável por ativo e tipo de regra (?symbol=, ?tipo=). */
export function Alertas() {
  const [params, setParams] = useSearchParams();
  const symbol = params.get('symbol') ?? '';
  const ruleType = params.get('tipo') ?? '';
  const query = new URLSearchParams({ limit: '100' });
  if (symbol) query.set('symbol', symbol);
  if (ruleType) query.set('rule_type', ruleType);
  const alerts = useApi<AlertLog[]>(`/api/alerts?${query.toString()}`, { pollMs: 60_000 });
  const watchlist = useApi<WatchlistItem[]>('/api/watchlist');

  function setFilter(key: string, value: string) {
    const p = new URLSearchParams(params);
    if (value) p.set(key, value);
    else p.delete(key);
    setParams(p, { replace: true });
  }

  const columns: Column<AlertLog>[] = [
    { key: 'quando', header: 'Quando', sortValue: (a) => a.triggered_at, render: (a) => <time className="num" dateTime={a.triggered_at}>{formatDateTime(a.triggered_at)}</time> },
    { key: 'ativo', header: 'Ativo', sortValue: (a) => a.symbol, render: (a) => <Link to={assetHref(a.symbol)} onClick={(e) => e.stopPropagation()}><strong>{a.symbol}</strong></Link> },
    { key: 'mensagem', header: 'Mensagem', wrap: true, render: (a) => ptBR(a.message) },
    { key: 'regra', header: 'Regra', render: (a) => <span className="muted">{ruleTypeLabel(a.rule_type)}</span> },
    { key: 'telegram', header: 'Telegram', render: (a) => (a.delivered_telegram ? <Badge tone="info">enviado</Badge> : <span className="muted">—</span>) },
    {
      key: 'explicar',
      header: <span className="sr-only">Ações</span>,
      align: 'right',
      render: (a) => (
        <Link to={`/assistente?modo=alerta&alerta=${a.id}`} className={buttonClass({ size: 'sm', variant: 'ghost' })} onClick={(e) => e.stopPropagation()}>
          <MessagesSquare {...ICON} aria-hidden="true" />
          Explicar alerta
        </Link>
      ),
    },
  ];

  return (
    <div className={styles.page}>
      <PageHeader
        title="Alertas"
        description="Alertas disparados pelas regras da sua watchlist. São sinais técnicos, não recomendação."
        actions={
          <Link to="/watchlist?regra=" className={buttonClass({ size: 'sm', variant: 'primary' })}>
            <BellPlus {...ICON} aria-hidden="true" />
            Criar alerta
          </Link>
        }
      />
      <div className={styles.filters}>
        <Select label="Ativo" value={symbol} onChange={(e) => setFilter('symbol', e.target.value)} className={styles.filter}>
          <option value="">Todos os ativos</option>
          {(watchlist.data ?? [])
            .map((w) => w.symbol)
            .sort()
            .map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
        </Select>
        <Select label="Tipo de regra" value={ruleType} onChange={(e) => setFilter('tipo', e.target.value)} className={styles.filter}>
          <option value="">Todos os tipos</option>
          {Object.entries(RULE_META).map(([rt, m]) => (
            <option key={rt} value={rt}>
              {m.name}
            </option>
          ))}
        </Select>
        {alerts.lastUpdated && <DataAge at={alerts.lastUpdated} refreshing={alerts.refreshing} />}
      </div>
      <AsyncContent
        state={alerts}
        loading={<SkeletonLines lines={8} height={20} />}
        empty={
          symbol || ruleType ? (
            <EmptyState title="Nenhum alerta com esses filtros" description="Limpe os filtros para ver todos os alertas." />
          ) : (
            <EmptyState
              title="Nenhum alerta disparado"
              description="Crie regras na watchlist para ser avisado quando preço, RSI, médias ou volume cruzarem seus níveis."
              action={
                <Link to="/watchlist?regra=" className={buttonClass({ size: 'sm' })}>
                  Criar alerta
                </Link>
              }
            />
          )
        }
        errorTitle="Não foi possível carregar os alertas"
      >
        {(list) => <Table caption="Alertas disparados" columns={columns} rows={list} rowKey={(a) => a.id} initialSort={{ key: 'quando', dir: 'desc' }} stickyFirstColumn />}
      </AsyncContent>
    </div>
  );
}
