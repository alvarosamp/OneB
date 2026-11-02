import { useApi } from '../../hooks/useApi';
import { AsyncContent, EmptyState, Section, SkeletonLines } from '../../components/ui';
import { formatCurrency, formatNumber } from '../../lib/format';
import type { Outlook, TesouroTitle } from './types';
import styles from './Brasil.module.css';

const br = (iso: string) => iso.split('-').reverse().join('/');

/** Como ler a taxa de cada tipo: no Selic e no IPCA+ ela é somada ao índice. */
function rateText(t: TesouroTitle): string {
  const r = `${formatNumber(t.buy_rate, 2)}%`;
  if (t.name.startsWith('Tesouro Selic')) return `Selic + ${r}`;
  if (t.name.startsWith('Tesouro Prefixado')) return `${r} ao ano`;
  if (t.name.startsWith('Tesouro IGPM')) return `IGP-M + ${r}`;
  return `IPCA + ${r}`;
}

const ORDER = ['Tesouro Selic', 'Tesouro Prefixado', 'Tesouro IPCA+', 'Tesouro Renda+ Aposentadoria Extra', 'Tesouro Educa+'];
const rank = (name: string) => {
  const i = ORDER.indexOf(name);
  return i === -1 ? ORDER.length : i;
};

/** Taxas de compra do Tesouro Direto no último dia publicado pelo Tesouro Transparente. */
export function TesouroHoje() {
  const data = useApi<Outlook>('/api/brasil/outlook', { isEmpty: (d) => !d.tesouro });
  return (
    <Section title="Quanto o Tesouro Direto paga hoje" meta={data.data?.tesouro ? `Tesouro Transparente · ${br(data.data.tesouro.as_of)}` : undefined}>
      <AsyncContent state={data} loading={<SkeletonLines lines={6} />} empty={<EmptyState title="Taxas do Tesouro indisponíveis agora" />} errorTitle="Tesouro indisponível">
        {(d) => {
          const titles = [...(d.tesouro?.titles ?? [])].sort((a, b) => rank(a.name) - rank(b.name) || a.name.localeCompare(b.name) || a.maturity.localeCompare(b.maturity));
          return (
            <>
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <caption className="sr-only">Taxa de compra e investimento mínimo de cada título do Tesouro Direto</caption>
                  <thead>
                    <tr>
                      <th scope="col">Título</th>
                      <th scope="col">Vence em</th>
                      <th scope="col">Rende</th>
                      <th scope="col">Mínimo para começar</th>
                    </tr>
                  </thead>
                  <tbody>
                    {titles.map((t) => (
                      <tr key={`${t.name}-${t.maturity}`}>
                        <th scope="row" style={{ whiteSpace: 'normal' }}>
                          {t.name}
                        </th>
                        <td>{br(t.maturity)}</td>
                        <td>{rateText(t)}</td>
                        <td>{formatCurrency(t.min_investment, 'BRL', 2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className={styles.meta} style={{ marginTop: 'var(--sp-3)' }}>
                Taxa de compra do dia, antes do imposto e da taxa de custódia da B3 (0,20% ao ano). "Selic + 0,06%" quer dizer que o título rende a Selic e mais
                um pouquinho. No Prefixado e no IPCA+, a taxa só é garantida levando até o vencimento: vender antes sai pelo preço do dia, que pode ser maior ou
                menor. Os títulos "com juros semestrais" pagam parte do rendimento a cada 6 meses, o que antecipa o imposto.
              </p>
            </>
          );
        }}
      </AsyncContent>
    </Section>
  );
}
