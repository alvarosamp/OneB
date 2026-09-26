import type { ReactNode } from 'react';
import styles from './Chips.module.css';

interface ChipItem<V extends string> {
  value: V;
  label: ReactNode;
  count?: number;
}

/** Filtro discreto em chips (seleção única, aria-pressed). */
export function ChipGroup<V extends string>({ items, value, onChange, label }: { items: ChipItem<V>[]; value: V; onChange: (v: V) => void; label: string }) {
  return (
    <div className={styles.group} role="group" aria-label={label}>
      {items.map((item) => (
        <button key={item.value} type="button" className={styles.chip} aria-pressed={value === item.value} onClick={() => onChange(item.value)}>
          {item.label}
          {item.count !== undefined && <span className={styles.count}>{item.count}</span>}
        </button>
      ))}
    </div>
  );
}
