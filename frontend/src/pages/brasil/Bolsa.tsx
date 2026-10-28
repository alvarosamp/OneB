import { useState } from 'react';
import { useApi } from '../../hooks/useApi';
import { AsyncContent, EmptyState, ChipGroup, ChangeText, Section, SkeletonLines, Table, type Column } from '../../components/ui';
import { formatNumber } from '../../lib/format';
import type { MarketRow, MarketSnapshot } from './types';
import styles from './Brasil.module.css';

type Group = MarketRow['group'];

const GROUPS: { value: Group; label: string; explain: string }[] = [
  { value: 'indice', label: 'Índices', explain: 'O termômetro do mercado: Ibovespa e dólar.' },
  { value: 'etf', label: 'ETFs', explain: 'Cestas de ações numa cota só. O jeito mais simples de começar na bolsa.' },
  { value: 'acao', label: 'Ações', explain: 'As mais negociadas da B3. Uma empresa sozinha oscila muito mais que um índice.' },
  { value: 'fii', label: 'Fundos imobiliários', explain: 'Pagam aluguel todo mês. Compare o rendimento com o risco do fundo.' },
];

const pct = (x: number | null | undefined, d = 1) => (x == null ? '—' : `${formatNumber(x, d)}%`);

const COLUMNS: Column<MarketRow>[] = [
  {
    key: 'symbol',
    header: 'Ativo',
    wrap: true,
    render: (r) => (
      <>
        <strong>{r.label}</strong>
        <span className={styles.meta}> · {r.description}</span>
        {r.data_break && <span className={styles.meta}> · medido desde {r.data_break.split('-').reverse().join('/')} (quebra nos dados)</span>}
      </>
    ),
    sortValue: (r) => r.label,
  },
  { key: 'price', header: 'Preço', align: 'right', render: (r) => formatNumber(r.price, (r.price ?? 0) < 10 ? 3 : 2), sortValue: (r) => r.price },
  { key: 'day', header: 'Dia', align: 'right', render: (r) => <ChangeText value={r.change_pct} />, sortValue: (r) => r.change_pct },
  { key: 'ret', header: '12 meses', align: 'right', render: (r) => <ChangeText value={r.return_12m_pct} />, sortValue: (r) => r.return_12m_pct },
  { key: 'dd', header: 'Maior queda (12m)', align: 'right', render: (r) => pct(r.max_drawdown_pct), sortValue: (r) => r.max_drawdown_pct },
  { key: 'vol', header: 'Oscilação anual', align: 'right', render: (r) => pct(r.volatility_pct), sortValue: (r) => r.volatility_pct },
  { key: 'dy', header: 'Proventos (12m)', align: 'right', render: (r) => pct(r.dividend_yield_pct), sortValue: (r) => r.dividend_yield_pct },
];

/** Brasil › Bolsa: retrato dos ativos mais negociados da B3, só com dados (não é indicação de compra). */
export function Bolsa() {
  const [group, setGroup] = useState<Group>('etf');
  const data = useApi<MarketSnapshot>('/api/brasil/market', { isEmpty: (d) => d.rows.length === 0, pollMs: 15 * 60_000 });
  const info = GROUPS.find((g) => g.value === group)!;
  return (
    <div className={styles.page}>
      <Section title="Bolsa brasileira hoje" meta={data.data?.source}>
        <ChipGroup label="Grupo" value={group} onChange={setGroup} items={GROUPS.map(({ value, label }) => ({ value, label }))} />
        <p className={styles.meta} style={{ margin: 'var(--sp-3) 0' }}>
          {info.explain}
        </p>
        <AsyncContent state={data} loading={<SkeletonLines lines={8} />} empty={<EmptyState title="Sem dados agora" />} errorTitle="Dados da B3 indisponíveis">
          {(d) => (
            <>
              <Table
                columns={COLUMNS}
                rows={d.rows.filter((r) => r.group === group && r.available)}
                rowKey={(r) => r.symbol}
                caption={`${info.label} da B3`}
                initialSort={{ key: 'ret', dir: 'desc' }}
                dense
                stickyFirstColumn
              />
              <p className={styles.meta} style={{ marginTop: 'var(--sp-3)' }}>
                {d.note} "Maior queda" é quanto o preço chegou a cair desde o topo nos últimos 12 meses: é o susto que você teria passado. "Oscilação
                anual" é a volatilidade; quanto maior, mais o preço pula. Proventos são dividendos e rendimentos pagos em 12 meses sobre o preço atual; ETFs
                que reinvestem aparecem com "—".
              </p>
            </>
          )}
        </AsyncContent>
      </Section>
    </div>
  );
}
