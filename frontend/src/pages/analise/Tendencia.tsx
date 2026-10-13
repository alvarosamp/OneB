import { useApi } from '../../hooks/useApi';
import { AsyncContent, Badge, EmptyState, Section, SkeletonLines } from '../../components/ui';
import type { BadgeTone } from '../../components/ui/Badge';
import { formatNumber } from '../../lib/format';
import type { TrendAsset, TrendEvidence, TrendReadings } from '../../types';
import styles from './Tendencia.module.css';

const STATUS: Record<TrendEvidence['status'], { label: string; tone: BadgeTone }> = {
  PENDING: { label: 'Teste pendente', tone: 'neutral' },
  PASSED: { label: 'Evidência aprovada', tone: 'positive' },
  DEGRADED: { label: 'Evidência degradada', tone: 'warning' },
  NOT_SIGNIFICANT: { label: 'Sem evidência', tone: 'neutral' },
  FAILED: { label: 'Reprovado', tone: 'negative' },
};

const pct = (x: number, d = 1) => `${x >= 0 ? '+' : ''}${formatNumber(x * 100, d)}%`;

/** Análise › Tendência: direção de 1, 3 e 12 meses, o preço que vira cada uma e o selo do teste. */
export function Tendencia() {
  const data = useApi<TrendReadings>('/api/trend/readings', { isEmpty: (d) => d.assets.length === 0 });
  return (
    <AsyncContent state={data} loading={<SkeletonLines lines={8} />} empty={<EmptyState title="Sem leitura de tendência" description="Os dados diários ainda não carregaram." />}>
      {(d) => (
        <div className={styles.page}>
          <EvidenceBox ev={d.evidence} />
          <div className={styles.grid}>
            {d.assets.map((a) => (
              <AssetCard key={a.key} asset={a} asEvidence={d.evidence.as_evidence} />
            ))}
          </div>
          <p className={styles.meta}>{d.note} Fonte do preço: histórico diário de futuros/câmbio do app; o teste usa CFDs da Dukascopy.</p>
        </div>
      )}
    </AsyncContent>
  );
}

function EvidenceBox({ ev }: { ev: TrendEvidence }) {
  const s = STATUS[ev.status];
  return (
    <Section title="Funciona a tendência?" meta={<Badge tone={s.tone}>{s.label}</Badge>}>
      <p className={styles.reading}>
        Seguir a tendência de 1, 3 e 12 meses é a regra com mais evidência acadêmica em mercados de índices, commodities e moedas. Antes de mostrar a direção como
        evidência, o OneB testa a regra com custos, num teste pré-registrado (tsmom_v1).
      </p>
      <p className={styles.reading}>{ev.reason}</p>
      {ev.primary && (
        <ul className={styles.facts}>
          <li>
            Retorno médio por mês, depois de custos: <strong>{pct(ev.primary.mean_monthly, 2)}</strong> (IC 95%: {pct(ev.primary.ci95[0], 2)} a {pct(ev.primary.ci95[1], 2)}), em{' '}
            {ev.primary.months} meses e {ev.universe_size} instrumentos.
          </li>
          {ev.primary.sharpe_annual !== null && <li>Sharpe anual {formatNumber(ev.primary.sharpe_annual, 2)}; maior queda {pct(ev.primary.max_drawdown)}.</li>}
          {ev.recent && <li>Período recente (desde 2023): {pct(ev.recent.mean_monthly, 2)} por mês.</li>}
          {ev.beyond_long_only && (
            <li>
              Além de só ficar comprado: alfa de {pct(ev.beyond_long_only.alpha_monthly, 2)} por mês (IC {pct(ev.beyond_long_only.alpha_ci95[0], 2)} a{' '}
              {pct(ev.beyond_long_only.alpha_ci95[1], 2)}){ev.beyond_long_only.badge ? ', acima de zero.' : ', não distinguível de zero.'}
            </li>
          )}
        </ul>
      )}
      {!ev.as_evidence && <p className={styles.meta}>Enquanto o teste não for aprovado, as direções abaixo descrevem o preço; não são sinal.</p>}
    </Section>
  );
}

function AssetCard({ asset, asEvidence }: { asset: TrendAsset; asEvidence: boolean }) {
  if (!asset.available || !asset.horizons) {
    return (
      <article className={styles.card}>
        <h3 className={styles.cardTitle}>{asset.label}</h3>
        <p className={styles.meta}>Sem histórico diário suficiente agora.</p>
      </article>
    );
  }
  const tone: BadgeTone = asset.agreement === 'todos em alta' ? 'positive' : asset.agreement === 'todos em baixa' ? 'negative' : 'neutral';
  return (
    <article className={styles.card} aria-label={`Tendência de ${asset.label}`}>
      <header className={styles.cardHead}>
        <h3 className={styles.cardTitle}>{asset.label}</h3>
        <Badge tone={tone}>{asset.agreement}</Badge>
      </header>
      <p className={styles.meta}>
        {asset.symbol}, fechamento de {asset.as_of?.split('-').reverse().join('/')}: {formatNumber(asset.last ?? null, 2)}
      </p>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">Horizonte</th>
            <th scope="col">Direção</th>
            <th scope="col">Variação</th>
            <th scope="col">Vira abaixo/acima de</th>
          </tr>
        </thead>
        <tbody>
          {asset.horizons.map((h) => (
            <tr key={h.days}>
              <td>{h.label}</td>
              <td className={h.direction === 'alta' ? styles.up : styles.down}>{h.direction}</td>
              <td>{pct(h.change)}</td>
              <td>
                {formatNumber(h.flip_price, 2)} <span className={styles.meta}>({pct(-h.distance_to_flip / (1 + h.distance_to_flip))} do preço)</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {asset.volatility_annual != null && (
        <p className={styles.meta}>
          Volatilidade anualizada {pct(asset.volatility_annual)}
          {asset.volatility_percentile != null ? `, maior que em ${formatNumber(asset.volatility_percentile * 100, 0)}% dos dias dos últimos 2 anos` : ''}. Volatilidade alta pede posição
          menor para o mesmo risco.
        </p>
      )}
      {asset.backtest_instrument && (
        <p className={styles.meta}>
          No teste, este ativo rendeu {pct(asset.backtest_instrument.mean_monthly, 2)} por mês com a regra ({asset.backtest_instrument.months} meses; resultado de um ativo só é ruído, vale o do conjunto).
        </p>
      )}
      {!asEvidence && <p className={styles.meta}>Descrição do preço, não sinal.</p>}
    </article>
  );
}
