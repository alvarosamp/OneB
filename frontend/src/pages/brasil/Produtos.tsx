import { useState } from 'react';
import { useApi } from '../../hooks/useApi';
import { AsyncContent, EmptyState, Badge, ChipGroup, Section, SkeletonLines, type BadgeTone } from '../../components/ui';
import type { Product } from './types';
import styles from './Brasil.module.css';

type Filter = 'todos' | Product['group'];

const RISK_TONE: Record<number, BadgeTone> = { 1: 'positive', 2: 'info', 3: 'warning', 4: 'negative', 5: 'negative' };

/** Brasil › Onde investir: cada classe explicada sem jargão, com risco, resgate, garantia e imposto. */
export function Produtos() {
  const [filter, setFilter] = useState<Filter>('todos');
  const data = useApi<{ products: Product[]; disclaimer: string }>('/api/brasil/products');
  return (
    <div className={styles.page}>
      <p className={styles.lead}>
        Antes de escolher um produto, pergunte: <strong>para que é esse dinheiro e quando vou precisar dele?</strong> A resposta diz se ele pode
        oscilar, se precisa de resgate rápido e quanto imposto faz sentido pagar.
      </p>
      <Section title="As opções mais acessíveis">
        <ChipGroup<Filter>
          label="Filtrar por tipo"
          value={filter}
          onChange={setFilter}
          items={[
            { value: 'todos', label: 'Todos' },
            { value: 'renda_fixa', label: 'Renda fixa' },
            { value: 'renda_variavel', label: 'Renda variável' },
          ]}
        />
        <AsyncContent state={data} loading={<SkeletonLines lines={6} />} empty={<EmptyState title="Sem dados agora" />} errorTitle="Catálogo indisponível">
          {(d) => (
            <>
              <div className={styles.cards} style={{ marginTop: 'var(--sp-4)' }}>
                {d.products
                  .filter((p) => filter === 'todos' || p.group === filter)
                  .map((p) => (
                    <article key={p.key} className={styles.card}>
                      <h3>
                        {p.label}
                        <Badge tone={RISK_TONE[p.risk]}>risco {p.risk_label}</Badge>
                      </h3>
                      <p>{p.what}</p>
                      <dl className={styles.dl}>
                        <dt>Resgate</dt>
                        <dd>{p.liquidity}</dd>
                        <dt>Garantia</dt>
                        <dd>{p.guarantee}</dd>
                        <dt>Imposto</dt>
                        <dd>{p.tax}</dd>
                        <dt>Mínimo</dt>
                        <dd>{p.minimum}</dd>
                      </dl>
                      <p>
                        <strong>Bom para:</strong> {p.good_for}
                      </p>
                      <p className={styles.meta}>
                        <strong>Cuidado:</strong> {p.watch_out}
                      </p>
                    </article>
                  ))}
              </div>
              <p className={styles.meta} style={{ marginTop: 'var(--sp-4)' }}>
                {d.disclaimer}
              </p>
            </>
          )}
        </AsyncContent>
      </Section>
    </div>
  );
}
