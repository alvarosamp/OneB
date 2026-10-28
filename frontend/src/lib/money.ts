/** Lê valor em reais digitado de qualquer jeito: "1.500,50", "R$ 1500.5", "1500". Inválido → NaN; vazio → 0. */
export function parseMoney(text: string): number {
  const t = text.trim().replace(/[R$\s]/g, '');
  if (!t) return 0;
  const normalized = t.includes(',') ? t.replace(/\./g, '').replace(',', '.') : /^\d{1,3}(\.\d{3})+$/.test(t) ? t.replace(/\./g, '') : t;
  const n = Number(normalized);
  return Number.isFinite(n) ? n : NaN;
}
