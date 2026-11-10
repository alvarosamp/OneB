import { useId } from 'react';

interface SparklineProps {
  values: (number | null)[];
  width?: number;
  height?: number;
  /** Cor semântica pela variação do período exibido. */
  tone?: 'positive' | 'negative' | 'neutral';
  label?: string;
}

/** Linha mínima em SVG; sem eixo, só a forma do movimento. */
export function Sparkline({ values, width = 72, height = 22, tone = 'neutral', label }: SparklineProps) {
  const id = useId();
  const points = values.filter((v): v is number => v !== null && Number.isFinite(v));
  if (points.length < 2) return null;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const step = width / (points.length - 1);
  const d = points.map((v, i) => `${(i * step).toFixed(1)},${(height - 2 - ((v - min) / span) * (height - 4)).toFixed(1)}`).join(' ');
  const color = tone === 'positive' ? 'var(--positive)' : tone === 'negative' ? 'var(--negative)' : 'var(--text-secondary)';
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role={label ? 'img' : undefined} aria-hidden={label ? undefined : true} aria-labelledby={label ? id : undefined}>
      {label && <title id={id}>{label}</title>}
      <polyline points={d} fill="none" stroke={color} strokeWidth="1.25" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
