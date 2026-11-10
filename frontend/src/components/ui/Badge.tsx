import type { HTMLAttributes, ReactNode } from 'react';
import styles from './Badge.module.css';

export type BadgeTone = 'neutral' | 'positive' | 'negative' | 'warning' | 'info';

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  outline?: boolean;
  dot?: boolean;
  children: ReactNode;
}

export function Badge({ tone = 'neutral', outline, dot, className, children, ...rest }: BadgeProps) {
  const cls = [styles.badge, tone !== 'neutral' ? styles[tone] : '', outline ? styles.outline : '', dot ? styles.dot : '', className ?? '']
    .filter(Boolean)
    .join(' ');
  return (
    <span className={cls} {...rest}>
      {children}
    </span>
  );
}
