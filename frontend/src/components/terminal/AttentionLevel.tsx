import { BASE_SCORE, LEVEL_LABEL, type AttentionScore } from '../../lib/attentionScore';
import { formatSigned } from '../../lib/format';
import { Tooltip } from '../ui';
import styles from './AttentionLevel.module.css';

/** Contribuições do score: o "por quê" do nível de atenção. */
export function AttentionWhy({ score }: { score: AttentionScore }) {
  return (
    <span className={styles.why}>
      <span className={styles.whyTitle}>Por que {LEVEL_LABEL[score.level].toLowerCase()}</span>
      <span className={styles.whyRow}>
        Ponto de partida
        <span className="num">{BASE_SCORE}</span>
      </span>
      {score.components.map((c) => (
        <span key={c.key} className={styles.whyRow}>
          {c.label}
          <span className={c.value > 0 ? styles.plus : c.value < 0 ? styles.minus : styles.zero}>{c.value === 0 ? '0' : formatSigned(c.value, 0)}</span>
          <small>{c.detail}</small>
        </span>
      ))}
      <span className={styles.total}>
        Total (0 a 100)
        <span className="num">{score.total}</span>
      </span>
    </span>
  );
}

/** Nível de atenção (alta/média/baixa) com a explicação em hover e foco. Sem barra de progresso. */
export function AttentionLevel({ score }: { score: AttentionScore }) {
  return (
    <Tooltip content={<AttentionWhy score={score} />} placement="bottom">
      <button type="button" className={styles.trigger} onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
        <span className={[styles.bars, styles[score.level]].join(' ')} aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        {LEVEL_LABEL[score.level]}
      </button>
    </Tooltip>
  );
}
