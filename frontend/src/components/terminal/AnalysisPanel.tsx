import type { ReactNode } from 'react';
import { AlertTriangle, Minus, TrendingDown, TrendingUp } from 'lucide-react';
import type { Evidence } from '../../lib/marketRead';
import type { Bias, DecisionState } from '../../lib/decisionState';
import { ICON_SM } from '../ui';
import { DecisionBadge } from './DecisionBadge';
import { ConceptLink } from './ConceptLink';
import styles from './AnalysisPanel.module.css';

export interface Fact {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  concept?: string;
}

interface AnalysisPanelProps {
  title: string;
  meta?: ReactNode;
  state?: DecisionState;
  bias?: Bias;
  evidences?: Evidence[];
  facts?: Fact[];
  summary?: ReactNode;
  footer?: ReactNode;
  headingLevel?: 2 | 3;
}

const EVIDENCE_ICON = {
  positive: TrendingUp,
  negative: TrendingDown,
  warning: AlertTriangle,
  neutral: Minus,
};

/** Leitura estruturada: estado, evidências curtas, fatos com justificativa e ações. */
export function AnalysisPanel({ title, meta, state, bias, evidences = [], facts = [], summary, footer, headingLevel = 2 }: AnalysisPanelProps) {
  const H = headingLevel === 2 ? 'h2' : 'h3';
  return (
    <section className={styles.panel} aria-label={title}>
      <div className={styles.header}>
        <H className={styles.title}>{title}</H>
        {meta}
      </div>
      {state && (
        <div className={styles.state}>
          <span className={styles.stateRow}>
            <DecisionBadge state={state} bias={bias} size="lg" />
            {state === 'sem-setup' && <ConceptLink concept="sem-setup" />}
          </span>
          {evidences.length > 0 && (
            <ul className={styles.evidences} aria-label="Evidências">
              {evidences.map((e) => {
                const Icon = EVIDENCE_ICON[e.tone];
                return (
                  <li key={e.text} className={[styles.evidence, styles[e.tone]].join(' ')}>
                    <Icon {...ICON_SM} aria-hidden="true" />
                    <span>{e.text}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
      {summary && <p className={styles.summary}>{summary}</p>}
      {facts.length > 0 && (
        <dl className={styles.facts}>
          {facts.map((f) => (
            <div key={f.label} className={styles.fact}>
              <dt>
                {f.label}
                {f.concept && <ConceptLink concept={f.concept} />}
              </dt>
              <dd className={styles.factValue}>{f.value}</dd>
              {f.note && <dd className={styles.factNote}>{f.note}</dd>}
            </div>
          ))}
        </dl>
      )}
      {footer && <div className={styles.footer}>{footer}</div>}
    </section>
  );
}
