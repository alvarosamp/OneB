import { Check, Circle, X } from 'lucide-react';
import { useApi } from '../../hooks/useApi';
import { formatDateTime, formatNumber } from '../../lib/format';
import {
  APPROVAL_HINT,
  APPROVAL_LABEL,
  completedSteps,
  isTerminalFailure,
  SETUP_STATE_LABEL,
  SETUP_STEPS,
} from '../../lib/setupState';
import type { Opportunity, OpportunityChanges, SetupVerdict } from '../../types';
import { AsyncContent, Badge, EmptyState, ICON_SM, Section, SkeletonLines } from '../ui';
import { ReliabilityMeter } from '../ReliabilityMeter';
import styles from './OpportunitiesView.module.css';

const SETUP_ID = 'gold_fakeout_open_v1';

interface SetupEvidence {
  setup: string;
  approval: string;
  data: { sessions: number; first: string; last: string; clock: string };
  summary: {
    completed_trades: number;
    expectancy_r: number | null;
    expectancy_ci95: [number, number] | null;
    win_rate: number | null;
    profit_factor: number | null;
    max_drawdown_r: number;
  };
  verdict: SetupVerdict;
  baselines: {
    random_entry: { p05: number; p50: number; p95: number };
    strategy_percentile_vs_random: number | null;
    plain_breakout: { completed_trades: number; expectancy_r: number | null; expectancy_ci95: [number, number] | null };
  };
  sample_size?: { explanation: string };
}

const VERDICT_TEXT: Record<SetupVerdict['status'], string> = {
  COLLECTING: 'Coletando evidência',
  PASSED: 'Passou na regra pré-registrada',
  ARCHIVE: 'Arquivar (sem vantagem)',
};

function r(value: number | null | undefined) {
  return value === null || value === undefined ? '-' : `${value > 0 ? '+' : ''}${formatNumber(value, 2)}R`;
}

function Stepper({ opp }: { opp: Opportunity }) {
  const done = completedSteps(opp.state);
  const failed = isTerminalFailure(opp.state);
  return (
    <ol className={styles.stepper} aria-label={`Estado: ${SETUP_STATE_LABEL[opp.state]}`}>
      {SETUP_STEPS.map((step, i) => {
        const complete = done !== null && i <= done;
        const current = !failed && done !== null && i === done + 1;
        return (
          <li key={step} className={[styles.step, complete ? styles.done : '', current ? styles.current : ''].join(' ')}>
            <span className={styles.stepIcon} aria-hidden="true">
              {complete ? <Check {...ICON_SM} /> : <Circle {...ICON_SM} />}
            </span>
            {SETUP_STATE_LABEL[step]}
          </li>
        );
      })}
      {failed && (
        <li className={[styles.step, styles.failed].join(' ')}>
          <span className={styles.stepIcon} aria-hidden="true">
            <X {...ICON_SM} />
          </span>
          {SETUP_STATE_LABEL[opp.state]}
        </li>
      )}
    </ol>
  );
}

function OpportunityCard({ opp }: { opp: Opportunity }) {
  const plan = opp.levels ?? opp.research_plan;
  const actionable = opp.levels !== null;
  const last = opp.evidence[opp.evidence.length - 1];
  return (
    <article className={styles.card}>
      <header className={styles.cardHead}>
        <div>
          <strong>{opp.symbol}</strong>
          <span className="muted"> · {opp.setup.replace(/_/g, ' ')}</span>
          {opp.direction && <span className="muted"> · {opp.direction === 'long' ? 'alta' : 'baixa'}</span>}
        </div>
        <Badge tone={actionable ? 'positive' : 'neutral'} title={APPROVAL_HINT[opp.approval]}>
          {APPROVAL_LABEL[opp.approval]}
        </Badge>
      </header>
      <p className={styles.state}>
        {SETUP_STATE_LABEL[opp.state]} <span className="muted">· {formatDateTime(opp.data_as_of)}</span>
      </p>
      <Stepper opp={opp} />
      {last && <p className={styles.reason}>{last.text}</p>}
      {plan && (
        <div className={actionable ? styles.levels : [styles.levels, styles.research].join(' ')}>
          <span className={styles.levelsTitle}>{actionable ? 'Plano liberado' : 'Plano de pesquisa (não é recomendação)'}</span>
          <span>Ref. <b className="num">{formatNumber(plan.entry, 2)}</b></span>
          <span>Stop <b className="num">{formatNumber(plan.stop, 2)}</b></span>
          <span>Alvo <b className="num">{formatNumber(plan.target, 2)}</b></span>
          {plan.reward_to_risk !== null && <span>R:R <b className="num">{formatNumber(plan.reward_to_risk, 1)}</b></span>}
        </div>
      )}
      {opp.counter_evidence.length > 0 && (
        <ul className={styles.counter}>
          {opp.counter_evidence.slice(-2).map((e) => (
            <li key={e.evidence_id}>{e.text}</li>
          ))}
        </ul>
      )}
      <ReliabilityMeter value={opp.reliability} />
    </article>
  );
}

function SetupEvidencePanel({ data }: { data: SetupEvidence }) {
  const s = data.summary;
  const pct = data.verdict.progress.pct ?? 0;
  return (
    <div className={styles.evidence}>
      <div className={styles.evidenceHead}>
        <Badge tone={data.verdict.status === 'PASSED' ? 'positive' : data.verdict.status === 'ARCHIVE' ? 'negative' : 'warning'}>
          {VERDICT_TEXT[data.verdict.status]}
        </Badge>
        <span className="muted">
          {data.data.sessions} sessões · {formatDateTime(data.data.first)} a {formatDateTime(data.data.last)} · relógio {data.data.clock === 'VERIFIED' ? 'verificado' : 'não verificado'}
        </span>
      </div>
      <div className={styles.progress} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label="Progresso até a amostra mínima pré-registrada">
        <div style={{ width: `${pct}%` }} />
      </div>
      <p className="muted">
        Amostra: {data.verdict.progress.sessions} sessões e {data.verdict.progress.trades} trades. {data.verdict.reason}
      </p>
      <dl className={styles.stats}>
        <div>
          <dt>Expectância líquida</dt>
          <dd className="num">{r(s.expectancy_r)}</dd>
        </div>
        <div>
          <dt>IC 95%</dt>
          <dd className="num">{s.expectancy_ci95 ? `${r(s.expectancy_ci95[0])} a ${r(s.expectancy_ci95[1])}` : '-'}</dd>
        </div>
        <div>
          <dt>Acerto</dt>
          <dd className="num">{s.win_rate !== null ? `${formatNumber(s.win_rate * 100, 1)}%` : '-'}</dd>
        </div>
        <div>
          <dt>Fator de lucro</dt>
          <dd className="num">{s.profit_factor !== null ? formatNumber(s.profit_factor, 2) : '-'}</dd>
        </div>
        <div>
          <dt>Vs. entrada aleatória</dt>
          <dd className="num">{data.baselines.strategy_percentile_vs_random !== null ? `percentil ${formatNumber(data.baselines.strategy_percentile_vs_random, 0)}` : '-'}</dd>
        </div>
        <div>
          <dt>Rompimento simples</dt>
          <dd className="num">{r(data.baselines.plain_breakout.expectancy_r)}</dd>
        </div>
      </dl>
      {data.sample_size && <p className={styles.footnote}>{data.sample_size.explanation}</p>}
    </div>
  );
}

/** Modo "Oportunidades": estado das máquinas de setup (ledger shadow) e a evidência de cada setup. */
export function OpportunitiesView() {
  const opps = useApi<{ opportunities: Opportunity[] }>('/api/opportunities', { pollMs: 30_000, isEmpty: (d) => d.opportunities.length === 0 });
  const changes = useApi<OpportunityChanges>('/api/opportunities/changes?since_minutes=30', { pollMs: 30_000 });
  const evidence = useApi<SetupEvidence>(`/api/opportunities/setups/${SETUP_ID}/evidence`);

  return (
    <div className={styles.view}>
      {changes.data && (
        <p className={styles.changes}>
          <b>Últimos 30 min:</b> {changes.data.summary}
        </p>
      )}
      <AsyncContent
        state={opps}
        loading={<SkeletonLines lines={6} />}
        empty={
          <EmptyState
            title="Nenhuma oportunidade viva"
            description="O executor shadow grava aqui cada rompimento, confirmação e saída. Se nada aparece durante a janela 07:00–11:00 BRT, confira se scripts/run_shadow.py está rodando."
          />
        }
        errorTitle="Não foi possível ler o ledger de oportunidades"
      >
        {(data) => (
          <div className={styles.grid}>
            {data.opportunities.map((o) => (
              <OpportunityCard key={o.opportunity_id} opp={o} />
            ))}
          </div>
        )}
      </AsyncContent>
      <Section title="Evidência do setup · Gold Fakeout (reimplementação aberta v1)" divided>
        {evidence.data ? (
          <SetupEvidencePanel data={evidence.data} />
        ) : evidence.status === 'loading' ? (
          <SkeletonLines lines={4} />
        ) : (
          <p className="muted">Sem relatório de replay. Rode scripts/run_setup_replay.py.</p>
        )}
      </Section>
    </div>
  );
}
