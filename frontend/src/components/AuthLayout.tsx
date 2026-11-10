import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { BrandMark } from './terminal/Sidebar';
import styles from './AuthLayout.module.css';

/** Moldura das telas de entrada e cadastro. */
export function AuthLayout({ title, description, children, footer }: { title: string; description?: string; children: ReactNode; footer: ReactNode }) {
  return (
    <main className={styles.page}>
      <div className={styles.card}>
        <Link to="/" className={styles.brand} aria-label="OneB, página inicial">
          <BrandMark />
          OneB
        </Link>
        <h1 className={styles.title}>{title}</h1>
        {description && <p className={styles.description}>{description}</p>}
        {children}
        <p className={styles.footer}>{footer}</p>
      </div>
      <p className={styles.disclaimer}>O OneB monitora o mercado e explica os dados coletados. Não executa ordens e não recomenda compra ou venda.</p>
    </main>
  );
}

/** Mensagem centralizada (404, erro inesperado, carregamento). */
export function CenteredMessage({ title, description, children, role }: { title: string; description?: string; children?: ReactNode; role?: string }) {
  return (
    <main className={styles.page} role={role}>
      <div className={styles.message}>
        <h1 className={styles.title}>{title}</h1>
        {description && <p className={styles.description}>{description}</p>}
        {children && <div className={styles.actions}>{children}</div>}
      </div>
    </main>
  );
}
