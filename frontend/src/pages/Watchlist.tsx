import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Bell, Trash2, X } from 'lucide-react';
import { api, ApiError } from '../api/client';
import { useToast } from '../context/ToastContext';
import { useConfirm } from '../components/ConfirmModal';
import { RuleConditionBuilder } from '../components/RuleConditionBuilder';
import { useRuleConditions } from '../hooks/useRuleConditions';
import { useApi } from '../hooks/useApi';
import { useAction } from '../hooks/useAction';
import { DataAge } from '../components/terminal/DataAge';
import { AsyncContent, Button, ChangeText, EmptyState, ICON, Input, PageHeader, Section, Select, SkeletonLines, Table, type Column } from '../components/ui';
import { formatDateTime, formatPrice, formatSignedPct, minutesSince } from '../lib/format';
import { ptBR } from '../lib/text';
import { ruleTypeLabel } from '../lib/rules';
import { assetHref, normalizeSymbol, SYMBOL_RE } from '../lib/watchlist';
import type { AlertRule, AssetType, BacktestResult, Playbook, WatchlistItem, WatchlistPrice } from '../types';
import styles from './Watchlist.module.css';

const ASSET_TYPE_LABEL: Record<AssetType, string> = {
  equity: 'Ação',
  etf: 'ETF',
  index: 'Índice',
  commodity: 'Commodity',
  fx: 'Câmbio',
  bond_yield: 'Juros',
  macro: 'Macro',
};

interface Row extends WatchlistItem {
  quote: WatchlistPrice | undefined;
}

/**
 * Watchlist e regras de alerta.
 * ?adicionar=SYM preenche o formulário; ?regra=SYM abre o editor de regra do ativo.
 */
export function Watchlist() {
  const toast = useToast();
  const confirm = useConfirm();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const items = useApi<WatchlistItem[]>('/api/watchlist');
  const prices = useApi<WatchlistPrice[]>('/api/watchlist/prices', { pollMs: 20_000 });
  const ruleSymbol = params.get('regra');

  const rows = useMemo<Row[]>(() => (items.data ?? []).map((i) => ({ ...i, quote: prices.data?.find((p) => p.id === i.id) })), [items.data, prices.data]);
  const ruleItem = ruleSymbol ? rows.find((r) => r.symbol === normalizeSymbol(ruleSymbol)) ?? null : null;

  function openRules(symbol: string | null) {
    const p = new URLSearchParams(params);
    if (symbol) p.set('regra', symbol);
    else p.delete('regra');
    p.delete('adicionar');
    setParams(p, { replace: true });
  }

  async function remove(item: WatchlistItem) {
    const ok = await confirm(`Remover ${item.symbol} da watchlist? As regras de alerta dele também serão removidas.`);
    if (!ok) return;
    try {
      await api.delete(`/api/watchlist/${item.id}`);
      items.mutate((prev) => (prev ?? []).filter((i) => i.id !== item.id));
      if (ruleItem?.id === item.id) openRules(null);
      toast(`${item.symbol} removido da watchlist`, 'success');
    } catch (err) {
      toast(err instanceof Error ? `Não foi possível remover: ${err.message}` : 'Não foi possível remover', 'error');
    }
  }

  const columns: Column<Row>[] = [
    {
      key: 'ativo',
      header: 'Ativo',
      sortValue: (r) => r.symbol,
      render: (r) => (
        <span className={styles.asset}>
          <strong>{r.symbol}</strong>
          {r.label && <span>{r.label}</span>}
        </span>
      ),
    },
    { key: 'tipo', header: 'Tipo', sortValue: (r) => r.asset_type, render: (r) => <span className="muted">{ASSET_TYPE_LABEL[r.asset_type] ?? r.asset_type}</span> },
    { key: 'preco', header: 'Preço', align: 'right', sortValue: (r) => r.quote?.price ?? null, render: (r) => <span className="num">{formatPrice(r.quote?.price ?? null, r.symbol)}</span> },
    { key: 'dia', header: 'Dia', align: 'right', sortValue: (r) => r.quote?.change_pct ?? null, render: (r) => (r.quote?.price == null ? <span className="muted">—</span> : <ChangeText value={r.quote.change_pct} />) },
    { key: 'dados', header: 'Dados', align: 'right', sortValue: (r) => minutesSince(r.quote?.taken_at ?? null), render: (r) => <DataAge at={r.quote?.taken_at ?? null} staleAfterMin={30} prefix="" /> },
    {
      key: 'acoes',
      header: <span className="sr-only">Ações</span>,
      align: 'right',
      render: (r) => (
        <span className={styles.rowActions} onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
          <Button size="sm" variant="ghost" icon={<Bell {...ICON} />} onClick={() => openRules(r.symbol)}>
            Regras
          </Button>
          <Button size="sm" variant="ghost" iconOnly icon={<Trash2 {...ICON} />} aria-label={`Remover ${r.symbol}`} onClick={() => remove(r)} />
        </span>
      ),
    },
  ];

  return (
    <div className={styles.page}>
      <PageHeader title="Watchlist" description="Ativos monitorados e as regras que disparam alertas. Clique numa linha para abrir o gráfico." />

      <AddForm initial={params.get('adicionar') ?? ''} existing={rows.map((r) => r.symbol)} onAdded={(item) => items.mutate((prev) => [...(prev ?? []).filter((i) => i.id !== item.id), item])} />

      {ruleSymbol !== null && (
        <RulePanel
          symbol={ruleSymbol}
          item={ruleItem}
          loading={items.status === 'loading'}
          onClose={() => openRules(null)}
          onAddAndOpen={async (s) => {
            try {
              const item = await api.post<WatchlistItem>('/api/watchlist', { symbol: s, label: '', asset_type: '' });
              items.mutate((prev) => [...(prev ?? []), item]);
              toast(`${s} adicionado à watchlist`, 'success');
            } catch (err) {
              toast(err instanceof Error ? `Não foi possível adicionar: ${err.message}` : 'Não foi possível adicionar', 'error');
            }
          }}
          choices={rows.map((r) => r.symbol)}
          onChoose={openRules}
        />
      )}

      <Section title="Ativos monitorados" meta={prices.lastUpdated ? <DataAge at={prices.lastUpdated} refreshError={prices.data ? prices.error : null} /> : null}>
        <AsyncContent
          state={items}
          loading={<SkeletonLines lines={8} height={20} />}
          empty={<EmptyState title="Nenhum ativo na watchlist" description="Adicione um símbolo acima (ex.: NVDA, QQQ, GC=F) para começar a monitorar." />}
          errorTitle="Não foi possível carregar a watchlist"
        >
          {() => (
            <Table
              caption="Ativos monitorados"
              columns={columns}
              rows={rows}
              rowKey={(r) => r.id}
              onRowClick={(r) => navigate(assetHref(r.symbol))}
              rowLabel={(r) => `Abrir ${r.symbol}`}
              initialSort={{ key: 'ativo', dir: 'asc' }}
              stickyFirstColumn
            />
          )}
        </AsyncContent>
      </Section>
    </div>
  );
}

function AddForm({ initial, existing, onAdded }: { initial: string; existing: string[]; onAdded: (i: WatchlistItem) => void }) {
  const toast = useToast();
  const [symbol, setSymbol] = useState(initial.toUpperCase());
  const [label, setLabel] = useState('');
  const [assetType, setAssetType] = useState<AssetType | ''>('');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (initial !== '' || window.location.search.includes('adicionar')) {
      setSymbol(initial.toUpperCase());
      ref.current?.focus();
    }
  }, [initial]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const s = normalizeSymbol(symbol);
    if (!SYMBOL_RE.test(s)) {
      setError('Use um símbolo válido, por exemplo NVDA, PETR4.SA ou GC=F.');
      return;
    }
    if (existing.includes(s)) {
      setError(`${s} já está na watchlist.`);
      return;
    }
    setError(null);
    setSaving(true);
    try {
      const item = await api.post<WatchlistItem>('/api/watchlist', { symbol: s, label, asset_type: assetType });
      onAdded(item);
      toast(`${s} adicionado à watchlist`, 'success');
      setSymbol('');
      setLabel('');
      setAssetType('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível adicionar');
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className={styles.addForm} onSubmit={submit} aria-label="Adicionar ativo">
      <Input ref={ref} label="Símbolo" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} placeholder="NVDA" error={error} className={styles.symbol} autoComplete="off" spellCheck={false} />
      <Input label="Nome (opcional)" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="NVIDIA" className={styles.label} />
      <Select label="Tipo" value={assetType} onChange={(e) => setAssetType(e.target.value as AssetType | '')} className={styles.type}>
        <option value="">Detectar pelo símbolo</option>
        {Object.entries(ASSET_TYPE_LABEL).map(([v, t]) => (
          <option key={v} value={v}>
            {t}
          </option>
        ))}
      </Select>
      <Button type="submit" variant="primary" loading={saving}>
        Adicionar à watchlist
      </Button>
    </form>
  );
}

interface RulePanelProps {
  symbol: string;
  item: WatchlistItem | null;
  loading: boolean;
  onClose: () => void;
  onAddAndOpen: (symbol: string) => Promise<void>;
  choices: string[];
  onChoose: (symbol: string) => void;
}

function RulePanel({ symbol, item, loading, onClose, onAddAndOpen, choices, onChoose }: RulePanelProps) {
  const s = normalizeSymbol(symbol);
  return (
    <section className={styles.rulePanel} aria-labelledby="rule-title">
      <header className={styles.ruleHeader}>
        <h2 id="rule-title" className={styles.ruleTitle}>
          {item ? `Alertas de ${item.symbol}` : 'Criar alerta'}
        </h2>
        <Button variant="ghost" size="sm" iconOnly icon={<X {...ICON} />} aria-label="Fechar regras" onClick={onClose} />
      </header>
      {loading ? (
        <SkeletonLines lines={3} />
      ) : item ? (
        <RuleEditor item={item} />
      ) : s && SYMBOL_RE.test(s) ? (
        <EmptyState
          title={`${s} ainda não está na watchlist`}
          description="Alertas são regras sobre ativos monitorados. Adicione o ativo para criar a regra."
          action={
            <Button size="sm" variant="primary" onClick={() => void onAddAndOpen(s)}>
              Adicionar {s} à watchlist
            </Button>
          }
        />
      ) : (
        <div className={styles.choose}>
          <p className="muted">Escolha o ativo da regra:</p>
          <div className={styles.chooseList}>
            {choices.length ? (
              choices.map((c) => (
                <Button key={c} size="sm" onClick={() => onChoose(c)}>
                  {c}
                </Button>
              ))
            ) : (
              <span className="muted">Adicione um ativo à watchlist primeiro.</span>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function RuleEditor({ item }: { item: WatchlistItem }) {
  const toast = useToast();
  const confirm = useConfirm();
  const builder = useRuleConditions();
  const rules = useApi<AlertRule[]>(`/api/watchlist/${item.id}/rules`);
  const playbooks = useApi<Playbook[]>('/api/intelligence/playbooks');
  const [playbookId, setPlaybookId] = useState('');
  const backtest = useAction(() =>
    api.post<BacktestResult>('/api/watchlist/rules/backtest', {
      symbol: item.symbol,
      logic: builder.logic,
      conditions: builder.conditions,
      period: '3mo',
      interval: '1d',
      forward_bars: 5,
    }),
  );
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      const rule = await api.post<AlertRule>(`/api/watchlist/${item.id}/rules`, {
        watchlist_item_id: item.id,
        logic: builder.logic,
        cooldown_minutes: builder.cooldownMinutes,
        conditions: builder.conditions,
      });
      rules.mutate((prev) => [...(prev ?? []), rule]);
      builder.reset();
      backtest.reset();
      toast(`Alerta criado para ${item.symbol}`, 'success');
    } catch (err) {
      toast(err instanceof ApiError ? `Não foi possível criar o alerta: ${err.message}` : 'Não foi possível criar o alerta', 'error');
    } finally {
      setSaving(false);
    }
  }

  async function removeRule(rule: AlertRule) {
    if (!(await confirm('Remover esta regra de alerta?'))) return;
    try {
      await api.delete(`/api/watchlist/rules/${rule.id}`);
      rules.mutate((prev) => (prev ?? []).filter((r) => r.id !== rule.id));
      toast('Regra removida', 'success');
    } catch (err) {
      toast(err instanceof Error ? `Não foi possível remover: ${err.message}` : 'Não foi possível remover', 'error');
    }
  }

  async function applyPlaybook() {
    if (!playbookId) return;
    try {
      await api.post(`/api/intelligence/playbooks/${playbookId}/apply/${item.id}`);
      rules.retry();
      toast('Playbook aplicado', 'success');
    } catch (err) {
      toast(err instanceof Error ? `Não foi possível aplicar: ${err.message}` : 'Não foi possível aplicar', 'error');
    }
  }

  const b = backtest.data;
  return (
    <div className={styles.ruleBody}>
      <div>
        <h3 className={styles.subTitle}>Regras ativas</h3>
        <AsyncContent state={rules} loading={<SkeletonLines lines={2} />} empty={<p className="muted">Nenhuma regra ainda. Crie a primeira abaixo.</p>}>
          {(list) => (
            <ul className={styles.ruleList}>
              {list.map((r) => (
                <li key={r.id}>
                  <span>
                    {r.conditions.map((c) => `${ruleTypeLabel(c.rule_type)}${c.threshold ? ` ${String(c.threshold).replace('.', ',')}` : ''}`).join(r.logic === 'ALL' ? ' e ' : ' ou ')}
                    <span className={styles.ruleMeta}>
                      intervalo de {r.cooldown_minutes} min{r.last_triggered_at ? `, último disparo ${formatDateTime(r.last_triggered_at)}` : ', nunca disparou'}
                    </span>
                  </span>
                  <Button size="sm" variant="ghost" iconOnly icon={<Trash2 {...ICON} />} aria-label="Remover regra" onClick={() => removeRule(r)} />
                </li>
              ))}
            </ul>
          )}
        </AsyncContent>
      </div>

      <div>
        <h3 className={styles.subTitle}>Nova regra</h3>
        <RuleConditionBuilder builder={builder} />
        <div className={styles.ruleActions}>
          <Button onClick={() => void backtest.run()} loading={backtest.status === 'running'}>
            Testar nos últimos 3 meses
          </Button>
          <Button variant="primary" onClick={save} loading={saving}>
            Criar alerta
          </Button>
        </div>
        {backtest.status === 'error' && <p className={styles.error}>Teste indisponível: {backtest.error}</p>}
        {b && (
          <dl className={styles.backtest} aria-label="Resultado do teste">
            <div>
              <dt>Disparos</dt>
              <dd className="num">{b.trigger_count}</dd>
            </div>
            <div>
              <dt>Retorno médio em 5 pregões</dt>
              <dd className="num">{formatSignedPct(b.avg_forward_return_pct)}</dd>
            </div>
            <div>
              <dt>Acerto</dt>
              <dd className="num">{b.win_rate_pct === null ? '—' : `${b.win_rate_pct.toFixed(1).replace('.', ',')}%`}</dd>
            </div>
            <div>
              <dt>Profit factor</dt>
              <dd className="num">{b.profit_factor === null ? '—' : b.profit_factor === 999 ? 'sem perdas' : b.profit_factor.toFixed(2).replace('.', ',')}</dd>
            </div>
            <div>
              <dt>Drawdown máximo</dt>
              <dd className="num">{formatSignedPct(b.max_drawdown_pct)}</dd>
            </div>
            <div>
              <dt>Manter o ativo no período</dt>
              <dd className="num">{formatSignedPct(b.buy_hold_return_pct)}</dd>
            </div>
          </dl>
        )}
      </div>

      {playbooks.data && playbooks.data.length > 0 && (
        <div>
          <h3 className={styles.subTitle}>Aplicar um playbook</h3>
          <div className={styles.ruleActions}>
            <Select label="Playbook" hideLabel value={playbookId} onChange={(e) => setPlaybookId(e.target.value)} className={styles.playbook}>
              <option value="">Escolha um playbook</option>
              {playbooks.data.map((p) => (
                <option key={p.id} value={p.id}>
                  {ptBR(p.name)}
                </option>
              ))}
            </Select>
            <Button onClick={applyPlaybook} disabled={!playbookId}>
              Aplicar playbook
            </Button>
          </div>
          {playbookId && <p className="muted">{ptBR(playbooks.data.find((p) => String(p.id) === playbookId)?.description ?? '')}</p>}
        </div>
      )}
    </div>
  );
}
