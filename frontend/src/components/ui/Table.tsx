import { useMemo, useState, type KeyboardEvent, type ReactNode } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react';
import { ICON_SM } from './icon';
import styles from './Table.module.css';

export interface Column<T> {
  key: string;
  header: ReactNode;
  /** Rótulo textual para leitores de tela quando o header não é texto. */
  label?: string;
  align?: 'left' | 'right' | 'center';
  render: (row: T) => ReactNode;
  /** Valor usado na ordenação; sem ele a coluna não ordena. `null` vai para o fim. */
  sortValue?: (row: T) => number | string | null | undefined;
  wrap?: boolean;
  width?: string;
}

interface TableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  caption?: string;
  onRowClick?: (row: T) => void;
  rowLabel?: (row: T) => string;
  initialSort?: { key: string; dir: 'asc' | 'desc' };
  dense?: boolean;
  stickyFirstColumn?: boolean;
  empty?: ReactNode;
  className?: string;
}

/** Tabela densa, ordenável, com linha inteira clicável/navegável por teclado. */
export function Table<T>({
  columns,
  rows,
  rowKey,
  caption,
  onRowClick,
  rowLabel,
  initialSort,
  dense,
  stickyFirstColumn,
  empty,
  className,
}: TableProps<T>) {
  const [sort, setSort] = useState(initialSort ?? null);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const column = columns.find((c) => c.key === sort.key);
    if (!column?.sortValue) return rows;
    const get = column.sortValue;
    return [...rows].sort((a, b) => {
      const va = get(a);
      const vb = get(b);
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      const cmp = typeof va === 'number' && typeof vb === 'number' ? va - vb : String(va).localeCompare(String(vb), 'pt-BR');
      return sort.dir === 'asc' ? cmp : -cmp;
    });
  }, [rows, columns, sort]);

  function toggleSort(key: string) {
    setSort((prev) => (prev?.key === key ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' }));
  }

  function onRowKey(event: KeyboardEvent<HTMLTableRowElement>, row: T) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onRowClick?.(row);
    }
  }

  const alignCls = (a?: string) => (a === 'right' ? styles.right : a === 'center' ? styles.center : '');

  return (
    <div className={[styles.scroller, className ?? ''].join(' ')}>
      <table className={[styles.table, dense ? styles.dense : '', stickyFirstColumn ? styles.stickyFirst : ''].join(' ')}>
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((col) => {
              const active = sort?.key === col.key;
              const ariaSort = active ? (sort!.dir === 'asc' ? 'ascending' : 'descending') : col.sortValue ? 'none' : undefined;
              return (
                <th key={col.key} scope="col" className={alignCls(col.align)} aria-sort={ariaSort} style={col.width ? { width: col.width } : undefined}>
                  {col.sortValue ? (
                    <button type="button" className={styles.sortButton} onClick={() => toggleSort(col.key)}>
                      {col.header}
                      {active ? (
                        sort!.dir === 'asc' ? <ArrowUp {...ICON_SM} aria-hidden="true" /> : <ArrowDown {...ICON_SM} aria-hidden="true" />
                      ) : (
                        <ArrowUpDown {...ICON_SM} aria-hidden="true" opacity={0.4} />
                      )}
                    </button>
                  ) : (
                    col.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 && empty ? (
            <tr className={styles.empty}>
              <td colSpan={columns.length}>{empty}</td>
            </tr>
          ) : (
            sorted.map((row) => (
              <tr
                key={rowKey(row)}
                className={onRowClick ? styles.clickable : undefined}
                tabIndex={onRowClick ? 0 : undefined}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                onKeyDown={onRowClick ? (e) => onRowKey(e, row) : undefined}
                aria-label={onRowClick && rowLabel ? rowLabel(row) : undefined}
              >
                {columns.map((col) => (
                  <td key={col.key} className={[alignCls(col.align), col.wrap ? styles.wrap : ''].join(' ')}>
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
