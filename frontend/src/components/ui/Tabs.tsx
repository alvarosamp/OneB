import { useId, useRef, type KeyboardEvent, type ReactNode } from 'react';
import styles from './Tabs.module.css';

export interface TabItem<V extends string = string> {
  value: V;
  label: ReactNode;
  icon?: ReactNode;
}

interface TabsProps<V extends string> {
  items: TabItem<V>[];
  value: V;
  onChange: (value: V) => void;
  label: string;
  variant?: 'underline' | 'segmented';
  className?: string;
  /** id base para ligar a aba ao painel (aria-controls). */
  idBase?: string;
}

/** Lista de abas acessível (setas, Home/End; ativação automática). */
export function Tabs<V extends string>({ items, value, onChange, label, variant = 'underline', className, idBase }: TabsProps<V>) {
  const autoId = useId();
  const base = idBase ?? autoId;
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const index = items.findIndex((item) => item.value === value);
    let next = -1;
    if (event.key === 'ArrowRight') next = (index + 1) % items.length;
    else if (event.key === 'ArrowLeft') next = (index - 1 + items.length) % items.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = items.length - 1;
    if (next < 0) return;
    event.preventDefault();
    onChange(items[next].value);
    refs.current[next]?.focus();
  }

  const segmented = variant === 'segmented';
  return (
    <div
      role="tablist"
      aria-label={label}
      className={[segmented ? styles.segmented : styles.list, className ?? ''].join(' ')}
      onKeyDown={onKeyDown}
    >
      {items.map((item, i) => {
        const selected = item.value === value;
        return (
          <button
            key={item.value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="tab"
            id={`${base}-tab-${item.value}`}
            aria-controls={`${base}-panel-${item.value}`}
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            className={segmented ? styles.segment : styles.tab}
            onClick={() => onChange(item.value)}
          >
            {item.icon}
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

export function TabPanel({ idBase, value, children, className }: { idBase: string; value: string; children: ReactNode; className?: string }) {
  return (
    <div
      role="tabpanel"
      id={`${idBase}-panel-${value}`}
      aria-labelledby={`${idBase}-tab-${value}`}
      tabIndex={0}
      className={[styles.panel, className ?? ''].join(' ')}
    >
      {children}
    </div>
  );
}
