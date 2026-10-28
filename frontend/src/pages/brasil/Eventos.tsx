import { useApi } from '../../hooks/useApi';
import { AsyncContent, EmptyState, Badge, Section, SkeletonLines, Stat, type BadgeTone } from '../../components/ui';
import { formatNumber, formatSignedPct } from '../../lib/format';

/** AAAA-MM-DD → DD/MM/AAAA (com ano: a agenda cruza a virada do ano e o histórico vem de 2016). */
const br = (iso?: string) => (iso ? iso.split('-').reverse().join('/') : '—');
import type { BrEvent, EventsData, ImpactGroup } from './types';
import styles from './Brasil.module.css';

const IMPACT_TONE: Record<string, BadgeTone> = { 'muito alto': 'negative', alto: 'warning', médio: 'info', baixo: 'neutral' };
const KIND_LABEL: Record<BrEvent['kind'], string> = { copom: 'Copom', fomc: 'EUA', eleicao: 'Eleição', ipca: 'Inflação', vencimento: 'B3' };

/** Brasil › Eventos: agenda do que mexe com a bolsa e o tamanho do movimento medido em 10 anos. */
export function Eventos() {
  const data = useApi<EventsData>('/api/brasil/events');
  return (
    <div className={styles.page}>
      <p className={styles.lead}>
        Eleição, Copom, inflação e juros dos EUA mexem com a bolsa e com a renda fixa. Saber quando eles acontecem ajuda a não tomar decisão no susto.
        Ninguém sabe a direção antes; o que dá para medir é o tamanho do movimento.
      </p>
      <AsyncContent state={data} loading={<SkeletonLines lines={8} />} empty={<EmptyState title="Sem dados agora" />} errorTitle="Agenda indisponível">
        {(d) => (
          <>
            <Section title="Próximos eventos" meta="próximos 4 meses">
              <ul className={styles.eventList}>
                {d.upcoming.map((e) => (
                  <li key={`${e.date}-${e.kind}`} className={styles.event}>
                    <span className={styles.eventDate}>
                      {e.approximate ? '≈ ' : ''}
                      {br(e.date)}
                    </span>
                    <div>
                      <strong>{e.title}</strong> <Badge outline>{KIND_LABEL[e.kind]}</Badge>{' '}
                      <Badge tone={IMPACT_TONE[e.impact] ?? 'neutral'}>impacto {e.impact}</Badge>
                      <p>{e.why}</p>
                    </div>
                  </li>
                ))}
              </ul>
              <p className={styles.meta} style={{ marginTop: 'var(--sp-3)' }}>
                ≈ data aproximada (o IBGE publica o IPCA por volta do dia 10). Copom: calendário oficial do Banco Central. Eleições: TSE.
              </p>
            </Section>
            {d.impact.available && <Impact impact={d.impact} />}
          </>
        )}
      </AsyncContent>
    </div>
  );
}

function Impact({ impact }: { impact: EventsData['impact'] }) {
  const ratio = (g?: ImpactGroup) => (g?.ratio ? `${formatNumber(g.ratio, 1)}× um dia comum` : undefined);
  return (
    <Section title="Quanto o Ibovespa se mexe nesses dias" meta={`medido desde ${br(impact.since)}`} divided>
      <div className={styles.stats}>
        <Stat label="Dia comum" value={`${formatNumber(impact.normal_abs_pct, 2)}%`} sub="movimento médio, para cima ou para baixo" />
        <Stat label={`Depois do Copom (${impact.copom?.n ?? 0})`} value={`${formatNumber(impact.copom?.mean_abs_pct, 2)}%`} sub={ratio(impact.copom)} />
        <Stat label={`Depois de cada turno de eleição (${impact.eleicao?.n ?? 0})`} value={`${formatNumber(impact.eleicao?.mean_abs_pct, 2)}%`} sub={ratio(impact.eleicao)} />
      </div>
      {impact.eleicao && impact.eleicao.rows.length > 0 && (
        <div className={styles.tableWrap} style={{ marginTop: 'var(--sp-4)' }}>
          <table className={styles.table}>
            <caption className="sr-only">Ibovespa no pregão seguinte a cada turno de eleição</caption>
            <thead>
              <tr>
                <th scope="col">Eleição</th>
                <th scope="col">Pregão</th>
                <th scope="col">Ibovespa no dia</th>
              </tr>
            </thead>
            <tbody>
              {impact.eleicao.rows.map((r) => (
                <tr key={r.event_date}>
                  <th scope="row">{r.label}</th>
                  <td>{br(r.session)}</td>
                  <td className={r.return_pct >= 0 ? styles.up : styles.down}>{formatSignedPct(r.return_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className={styles.meta} style={{ marginTop: 'var(--sp-3)' }}>
        {impact.note} O Copom anuncia depois do fechamento, então contamos o pregão seguinte. Para quem investe a longo prazo, a lição é simples: dinheiro
        que você vai usar perto de uma eleição não deveria estar em bolsa.
      </p>
    </Section>
  );
}
