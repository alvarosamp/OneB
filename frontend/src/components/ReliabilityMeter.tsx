import type { Reliability, ReliabilityGrade } from '../types';
import styles from './ReliabilityMeter.module.css';

const GRADE_TEXT: Record<ReliabilityGrade, string> = {
  ALTA: 'Alta',
  MEDIA: 'Média',
  BAIXA: 'Baixa',
  INSUFICIENTE: 'Insuficiente',
  SEM_SINAL: 'Sem sinal',
};

function gradeClass(grade: ReliabilityGrade) {
  return styles[grade.toLowerCase()];
}

/** Versão compacta para tabelas: ponto colorido + nota + valor. */
export function ReliabilityChip({ value }: { value: Reliability | null | undefined }) {
  if (!value) return <span className="muted">-</span>;
  return (
    <span className={styles.chip} title={`${value.limiting_factor} ${value.disclaimer}`}>
      <i className={[styles.dot, gradeClass(value.grade)].join(' ')} aria-hidden="true" />
      {GRADE_TEXT[value.grade]}
      {value.score !== null && ` · ${value.score}`}
    </span>
  );
}

/** Índice de confiabilidade com barra, o fator que mais limita e o detalhamento por componente. */
export function ReliabilityMeter({ value }: { value: Reliability | null | undefined }) {
  if (!value) return null;
  const score = value.score ?? 0;
  return (
    <section className={styles.meter} aria-label="Confiabilidade do sinal">
      <div className={styles.head}>
        <span className={styles.title}>Confiabilidade</span>
        <span className={styles.value}>
          {value.score !== null ? score : '-'}
          <small>/100 · {GRADE_TEXT[value.grade]}</small>
        </span>
      </div>
      <div
        className={styles.track}
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={score}
        aria-valuetext={`${value.label}, ${score} de 100`}
      >
        <div className={[styles.fill, gradeClass(value.grade)].join(' ')} style={{ width: `${score}%` }} />
      </div>
      <p className={styles.limit}>
        <b>O que mais limita:</b> {value.limiting_factor}
      </p>
      {value.components.length > 0 && (
        <details className={styles.details}>
          <summary>Como foi calculado</summary>
          <ul className={styles.list}>
            {value.components.map((component) => (
              <li key={component.key} className={styles.item}>
                <span>
                  {component.label} <span className="muted">(peso {component.weight})</span>
                </span>
                <span>{component.available ? `${component.score}/100` : 'sem evidência'}</span>
                <p>{component.detail}</p>
              </li>
            ))}
            {value.caps.map((cap) => (
              <li key={cap.key} className={styles.item}>
                <span>Trava: {cap.reason}</span>
                <span>máx. {cap.limit}</span>
              </li>
            ))}
          </ul>
          <p className={styles.disclaimer}>{value.disclaimer}</p>
        </details>
      )}
    </section>
  );
}
