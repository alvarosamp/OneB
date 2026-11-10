import styles from './Skeleton.module.css';

interface SkeletonProps {
  width?: number | string;
  height?: number | string;
  className?: string;
}

export function Skeleton({ width = '100%', height = 12, className }: SkeletonProps) {
  return <span aria-hidden="true" className={[styles.skeleton, className ?? ''].join(' ')} style={{ width, height }} />;
}

/** Bloco de linhas para listas/tabelas em carregamento. */
export function SkeletonLines({ lines = 4, height = 14, label = 'Carregando' }: { lines?: number; height?: number; label?: string }) {
  return (
    <div className={styles.lines} role="status" aria-label={label}>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} height={height} width={i === lines - 1 ? '60%' : '100%'} />
      ))}
    </div>
  );
}
