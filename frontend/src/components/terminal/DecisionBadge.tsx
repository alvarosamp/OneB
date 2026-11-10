import { BIAS_LABEL, STATE_LABEL, type Bias, type DecisionState } from '../../lib/decisionState';
import styles from './DecisionBadge.module.css';

interface DecisionBadgeProps {
  state: DecisionState;
  bias?: Bias;
  size?: 'sm' | 'md' | 'lg';
}

/**
 * Estado de leitura: Sem setup / Observar / Setup em formação.
 * Cores fora do verde/vermelho de propósito: estado não é alta nem queda.
 */
export function DecisionBadge({ state, bias = null, size = 'md' }: DecisionBadgeProps) {
  return (
    <span className={[styles.wrap, size !== 'md' ? styles[size] : ''].join(' ')}>
      <span className={[styles.state, state === 'observar' ? styles.observar : state === 'formacao' ? styles.formacao : ''].join(' ')}>
        {STATE_LABEL[state]}
      </span>
      {bias && state !== 'sem-setup' && <span className={styles.bias}>{BIAS_LABEL[bias]}</span>}
    </span>
  );
}
