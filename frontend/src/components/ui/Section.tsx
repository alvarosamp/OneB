import type { ReactNode } from 'react';
import styles from './Section.module.css';

interface SectionProps {
  title: ReactNode;
  /** Metadados curtos ao lado do título (ex.: idade do dado). */
  meta?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  /** Linha de separação no topo, quando a seção precisa se destacar da anterior. */
  divided?: boolean;
  className?: string;
  as?: 'section' | 'div' | 'aside';
  headingLevel?: 2 | 3;
  id?: string;
}

/** Bloco de conteúdo sem caixa: hierarquia vem do título, não de bordas. */
export function Section({ title, meta, actions, children, divided, className, as: Tag = 'section', headingLevel = 2, id }: SectionProps) {
  const H = headingLevel === 2 ? 'h2' : 'h3';
  return (
    <Tag className={[styles.section, divided ? styles.divided : '', className ?? ''].join(' ')} aria-labelledby={id ? `${id}-title` : undefined}>
      <div className={styles.header}>
        <div className={styles.titleGroup}>
          <H className={styles.title} id={id ? `${id}-title` : undefined}>
            {title}
          </H>
          {meta && <span className={styles.meta}>{meta}</span>}
        </div>
        {actions && <div className={styles.actions}>{actions}</div>}
      </div>
      {children}
    </Tag>
  );
}

export function PageHeader({ title, description, actions }: { title: ReactNode; description?: ReactNode; actions?: ReactNode }) {
  return (
    <header className={styles.pageHeader}>
      <div>
        <h1 className={styles.pageTitle}>{title}</h1>
        {description && <p className={styles.pageDescription}>{description}</p>}
      </div>
      {actions && <div className={styles.actions}>{actions}</div>}
    </header>
  );
}
