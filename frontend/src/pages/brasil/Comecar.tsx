import { Link } from 'react-router-dom';
import { useApi } from '../../hooks/useApi';
import { AsyncContent, EmptyState, Section, SkeletonLines, Stat, buttonClass } from '../../components/ui';
import { formatCurrency, formatDate, formatNumber } from '../../lib/format';
import type { History, Rates } from './types';
import styles from './Brasil.module.css';

const pct = (x: number | null | undefined, d = 2) => (x == null ? '—' : `${formatNumber(x, d)}%`);

const PATH = [
  { title: 'Monte a reserva de emergência', text: '6 meses de gastos em Tesouro Selic ou CDB de liquidez diária. Ela vem antes de tudo.' },
  { title: 'Saia da poupança', text: 'Com a Selic alta, Tesouro Selic e CDB de 100% do CDI rendem bem mais, com a mesma segurança.' },
  { title: 'Dê um objetivo para cada dinheiro', text: 'Prazo curto pede renda fixa; prazo longo aceita uma parte em bolsa e fundos imobiliários.' },
  { title: 'Aporte todo mês e não venda no susto', text: 'Constância e tempo fazem mais que escolher a aplicação perfeita.' },
];

/** Brasil › Começar: taxas de hoje, o caminho em 4 passos e o comparativo de 10 anos. */
export function Comecar() {
  const rates = useApi<Rates>('/api/brasil/rates');
  const history = useApi<History>('/api/brasil/history', { isEmpty: (d) => d.table.length === 0 });
  return (
    <div className={styles.page}>
      <p className={styles.lead}>
        Você não precisa de muito dinheiro nem de entender de economia para começar. Precisa de um plano simples: reserva primeiro, renda fixa bem
        escolhida e, com prazo longo, uma parte em bolsa. O <Link to="/brasil?tab=simulador">simulador</Link> monta esse plano para o seu caso e explica
        cada parte.
      </p>

      <Section title="As taxas de hoje" meta={rates.data ? `${rates.data.source}${rates.data.stale ? ' · pode estar desatualizado' : ''}` : undefined}>
        <AsyncContent state={rates} loading={<SkeletonLines lines={2} />} empty={<EmptyState title="Sem dados agora" />} errorTitle="Taxas indisponíveis">
          {(r) => (
            <div className={styles.stats}>
              <Stat label="Selic (meta)" value={pct(r.selic)} sub={`definida pelo Copom · ${formatDate(r.series.selic?.as_of)}`} />
              <Stat label="CDI" value={pct(r.cdi)} sub="referência dos CDBs" />
              <Stat label="Inflação (IPCA 12 meses)" value={pct(r.ipca_12m)} sub={`até ${formatDate(r.series.ipca_12m?.as_of)}`} />
              <Stat label="Poupança" value={pct(r.poupanca)} sub="ao ano, sem TR" />
              <Stat label="Ganho real do CDI" value={pct(r.real_cdi)} sub="acima da inflação, antes do IR" />
            </div>
          )}
        </AsyncContent>
      </Section>

      <Section title="O caminho em 4 passos">
        <ol className={styles.steps}>
          {PATH.map((s, i) => (
            <li key={s.title}>
              <strong>
                {i + 1}. {s.title}
              </strong>
              <span className={styles.meta}>{s.text}</span>
            </li>
          ))}
        </ol>
        <div className={styles.formActions} style={{ marginTop: 'var(--sp-4)' }}>
          <Link to="/brasil?tab=simulador" className={buttonClass({ variant: 'primary' })}>
            Simular o meu caso
          </Link>
          <Link to="/brasil?tab=aulas" className={buttonClass({ variant: 'secondary' })}>
            Ver as aulas
          </Link>
        </div>
      </Section>

      <Section title="Quanto R$ 1.000 viraram" meta={history.data?.last_month ? `até ${history.data.last_month.split('-').reverse().join('/')}` : undefined}>
        <AsyncContent state={history} loading={<SkeletonLines lines={4} />} empty={<EmptyState title="Sem dados agora" />} errorTitle="Comparativo indisponível">
          {(h) => <HistoryTable h={h} />}
        </AsyncContent>
      </Section>
    </div>
  );
}

const COLS: { key: 'poupanca' | 'cdi' | 'ipca' | 'ibovespa' | 'dolar'; label: string }[] = [
  { key: 'poupanca', label: 'Poupança' },
  { key: 'cdi', label: 'CDI' },
  { key: 'ipca', label: 'Inflação' },
  { key: 'ibovespa', label: 'Ibovespa' },
  { key: 'dolar', label: 'Dólar' },
];

function HistoryTable({ h }: { h: History }) {
  const cols = COLS.filter((c) => h.table.some((r) => r[c.key] != null));
  return (
    <>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <caption className="sr-only">Valor de R$ 1.000 aplicados em cada opção</caption>
          <thead>
            <tr>
              <th scope="col">Aplicado há</th>
              {cols.map((c) => (
                <th scope="col" key={c.key}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {h.table.map((row) => {
              const best = Math.max(...cols.map((c) => row[c.key] ?? -Infinity));
              return (
                <tr key={row.months}>
                  <th scope="row">{row.months === 12 ? '1 ano' : `${row.months / 12} anos`}</th>
                  {cols.map((c) => (
                    <td key={c.key} style={row[c.key] === best ? { fontWeight: 600 } : undefined}>
                      {row[c.key] == null ? '—' : formatCurrency(row[c.key], 'BRL', 0)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className={styles.meta}>{h.note}</p>
    </>
  );
}
