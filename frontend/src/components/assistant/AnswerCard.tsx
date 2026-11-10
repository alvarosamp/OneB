import { useId, useState, type ReactNode } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import type { Bias, DecisionState } from '../../lib/decisionState';
import { DecisionBadge } from '../terminal/DecisionBadge';
import { Button, ICON } from '../ui';
import styles from './AnswerCard.module.css';

export type DataConfidence = 'alta' | 'media' | 'baixa' | null;

const CONFIDENCE_LABEL: Record<Exclude<DataConfidence, null>, string> = {
  alta: 'Dados confiáveis',
  media: 'Dados com ressalvas',
  baixa: 'Dados frágeis',
};

interface AnswerCardProps {
  subject: ReactNode;
  subtitle?: ReactNode;
  state?: DecisionState;
  bias?: Bias;
  confidence?: DataConfidence;
  confidenceDetail?: ReactNode;
  conclusion: ReactNode;
  evidences?: ReactNode[];
  counterpoints?: ReactNode[];
  /** Conteúdo completo exibido em "Ver evidências". */
  details?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}

/**
 * Resposta estruturada do Assistente: estado, confiança dos dados,
 * conclusão em uma frase, evidências curtas e ações.
 */
export function AnswerCard({
  subject,
  subtitle,
  state,
  bias,
  confidence,
  confidenceDetail,
  conclusion,
  evidences = [],
  counterpoints = [],
  details,
  actions,
  children,
}: AnswerCardProps) {
  const [open, setOpen] = useState(false);
  const detailsId = useId();
  return (
    <article className={styles.answer} aria-live="polite">
      <header className={styles.head}>
        <div className={styles.subject}>
          <h2 className={styles.subjectTitle}>{subject}</h2>
          {subtitle && <span className="muted">{subtitle}</span>}
          {state && <DecisionBadge state={state} bias={bias} />}
        </div>
        {confidence && (
          <div className={styles.confidence}>
            <strong>{CONFIDENCE_LABEL[confidence]}</strong>
            {confidenceDetail && <span>{confidenceDetail}</span>}
          </div>
        )}
      </header>

      <p className={styles.conclusion}>{conclusion}</p>

      {(evidences.length > 0 || counterpoints.length > 0) && (
        <div className={counterpoints.length > 0 ? styles.columns : undefined}>
          {evidences.length > 0 && (
            <div>
              <h3 className={styles.label}>Evidências</h3>
              <ul className={styles.list}>
                {evidences.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </div>
          )}
          {counterpoints.length > 0 && (
            <div>
              <h3 className={styles.label}>Contraponto</h3>
              <ul className={styles.list}>
                {counterpoints.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {children}

      {(actions || details) && (
        <div className={styles.actions}>
          {actions}
          {details && (
            <Button
              variant="ghost"
              size="sm"
              icon={open ? <ChevronUp {...ICON} /> : <ChevronDown {...ICON} />}
              aria-expanded={open}
              aria-controls={detailsId}
              onClick={() => setOpen((v) => !v)}
            >
              {open ? 'Ocultar evidências' : 'Ver evidências'}
            </Button>
          )}
        </div>
      )}
      {details && open && (
        <div id={detailsId} className={styles.details}>
          {details}
        </div>
      )}
      <p className={styles.note}>Explicação baseada nos dados coletados pelo OneB. Não é recomendação de compra ou venda.</p>
    </article>
  );
}
