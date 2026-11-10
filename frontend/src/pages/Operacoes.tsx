import type { ReactNode } from 'react';
import { useApi } from '../hooks/useApi';
import { DataAge } from '../components/terminal/DataAge';
import { AsyncContent, Badge, EmptyState, Section, SkeletonLines, Stat } from '../components/ui';
import { formatCurrency, formatDateTime, formatNumber } from '../lib/format';
import { ptBR } from '../lib/text';
import type { OperationalHealth } from '../types';
import styles from './Configuracoes.module.css';

const pct = (v: number | null) => (v === null ? '—' : `${formatNumber(v * 100, 2)}%`);

function Pairs({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className={styles.pairs}>
      {rows.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Configurações › Sistema (antiga página Operações): saúde de dados, jobs, modelo e auditoria. */
export function Operacoes() {
  const health = useApi<OperationalHealth>('/api/operations/health', { pollMs: 60_000 });
  return (
    <AsyncContent state={health} loading={<SkeletonLines lines={12} />} empty={<EmptyState title="Diagnóstico indisponível" />} errorTitle="Não foi possível carregar o diagnóstico">
      {(h) => (
        <div className={styles.stack}>
          <div className={styles.statsRow}>
            <Stat
              label="Status geral"
              value={<Badge tone={h.status === 'ok' ? 'info' : 'warning'}>{h.status === 'ok' ? 'operacional' : ptBR(h.status)}</Badge>}
              sub={<DataAge at={h.generated_at} prefix="verificado" />}
            />
            <Stat label="Último snapshot de preço" value={formatDateTime(h.latest_snapshot_at)} sub={h.snapshot_age_minutes !== null ? `${h.snapshot_age_minutes} min atrás` : undefined} />
            <Stat label="Carteira simulada" value={formatCurrency(h.paper_simulator.portfolio_value)} sub={ptBR(h.paper_simulator.status)} />
            <Stat label="Cache de candles" value={h.market_cache.ready ? 'pronto' : 'incompleto'} />
          </div>
          <div className={styles.twoCol}>
            <Section title="Prontidão">
              <p className="muted">{ptBR(h.readiness.recommendation)}</p>
              <Pairs
                rows={[
                  ['Nível', ptBR(h.readiness.level)],
                  ['Automação de ordens', h.readiness.trade_automation_allowed ? 'liberada' : 'bloqueada'],
                  ['Bloqueios', h.readiness.blockers.length ? h.readiness.blockers.map(ptBR).join('; ') : 'nenhum'],
                  ['Veredito da automação', ptBR(h.automation.verdict)],
                ]}
              />
            </Section>
            <Section title="Modelo de probabilidade">
              <p className="muted">{ptBR(h.probability_model.recommendation)}</p>
              <Pairs
                rows={[
                  ['Status', ptBR(h.probability_model.status)],
                  ['Amostras de treino', h.probability_model.train_samples ?? '—'],
                  ['Acerto fora da amostra', pct(h.probability_model.holdout_accuracy)],
                  ['Linha de base', pct(h.probability_model.holdout_baseline_accuracy)],
                ]}
              />
            </Section>
            <Section title="Simulação (paper trading)">
              <Pairs
                rows={[
                  ['Capital inicial', formatCurrency(h.paper_simulator.initial_capital)],
                  ['Caixa', formatCurrency(h.paper_simulator.cash)],
                  ['Posições abertas', h.paper_simulator.open_positions],
                  ['Trades fechados', h.paper_simulator.closed_trades],
                ]}
              />
            </Section>
            <Section title="Qualidade das cotações">
              <Pairs
                rows={[
                  ['Alta', h.data_quality.HIGH],
                  ['Média', h.data_quality.MEDIUM],
                  ['Baixa', h.data_quality.LOW],
                ]}
              />
            </Section>
            <Section title="Fontes de dados">
              <Pairs rows={Object.entries(h.providers).map(([k, v]) => [k, v ? <Badge tone="info">disponível</Badge> : <Badge tone="warning">indisponível</Badge>])} />
            </Section>
            <Section title="Jobs agendados">
              <Pairs rows={Object.entries(h.jobs).map(([k, v]) => [ptBR(k.replaceAll('_', ' ')), String(v)])} />
            </Section>
            <Section title="Banco de dados">
              <Pairs rows={Object.entries(h.db.counts).map(([k, v]) => [ptBR(k.replaceAll('_', ' ')), formatNumber(v, 0)])} />
            </Section>
            <Section title="Cache de candles">
              <Pairs rows={h.market_cache.rows.map((r) => [r.symbol, `${r.rows} candles${r.has_ohlcv ? '' : ', sem OHLCV'}`])} />
            </Section>
          </div>
          <div className={styles.twoCol}>
            <Section title="Alertas recentes">
              {h.recent_alerts.length ? (
                <ul className={styles.items}>
                  {h.recent_alerts.map((a) => (
                    <li key={`${a.symbol}-${a.triggered_at}`}>
                      <span>
                        <strong>{a.symbol}</strong> {ptBR(a.message)}
                      </span>
                      <span className="muted num">{formatDateTime(a.triggered_at)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">Nenhum.</p>
              )}
            </Section>
            <Section title="Auditoria">
              {h.recent_audit_logs.length ? (
                <ul className={styles.items}>
                  {h.recent_audit_logs.map((l) => (
                    <li key={`${l.action}-${l.created_at}-${l.entity_id}`}>
                      <span>
                        {ptBR(l.action)} <span className="muted">
                          {l.entity_type} {l.entity_id}
                        </span>
                      </span>
                      <span className="muted num">{formatDateTime(l.created_at)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">Nenhum registro.</p>
              )}
            </Section>
          </div>
        </div>
      )}
    </AsyncContent>
  );
}
