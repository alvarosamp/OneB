import { formatSigned, isNum } from './format';
import { ptBR } from './text';

/** Variação em % ou pontos-base (juros), com sinal e cor de mercado. */
export function formatTrendChange(value: number | null | undefined, unit: '%' | 'bps'): string {
  if (!isNum(value)) return '—';
  return unit === 'bps' ? `${formatSigned(value, 1)} bps` : `${formatSigned(value, 2)}%`;
}

export function themeLabel(value: string): string {
  return ptBR(value.replaceAll('_', ' ').toLocaleLowerCase('pt-BR'));
}
