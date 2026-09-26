import type { ReactNode } from 'react';
import { AlertTriangle, RotateCw } from 'lucide-react';
import { Button } from './Button';
import { ICON } from './icon';
import styles from './States.module.css';

interface EmptyStateProps {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
  center?: boolean;
}

/** Estado vazio: diz o que fazer em seguida. */
export function EmptyState({ title, description, action, icon, center }: EmptyStateProps) {
  return (
    <div className={[styles.state, center ? styles.center : ''].join(' ')}>
      <p className={styles.title}>
        {icon}
        {title}
      </p>
      {description && <p className={styles.description}>{description}</p>}
      {action && <div className={styles.actions}>{action}</div>}
    </div>
  );
}

interface ErrorStateProps {
  title?: ReactNode;
  error?: string | null;
  onRetry?: () => void;
  center?: boolean;
}

/** Estado de erro: mostra a causa e oferece "Tentar de novo". */
export function ErrorState({ title = 'Não foi possível carregar', error, onRetry, center }: ErrorStateProps) {
  return (
    <div className={[styles.state, styles.error, center ? styles.center : ''].join(' ')} role="alert">
      <p className={styles.title}>
        <AlertTriangle {...ICON} aria-hidden="true" />
        {title}
      </p>
      {error && <p className={styles.detail}>{error}</p>}
      {onRetry && (
        <div className={styles.actions}>
          <Button size="sm" icon={<RotateCw {...ICON} />} onClick={onRetry}>
            Tentar de novo
          </Button>
        </div>
      )}
    </div>
  );
}
