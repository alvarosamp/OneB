export type Direction = 'LONG' | 'SHORT';

export interface SimInput {
  direction: Direction;
  capital: number;
  riskPct: number;
  entry: number;
  stop: number;
  target: number;
}

export interface SimResult {
  quantity: number;
  plannedRisk: number;
  plannedReward: number;
  rr: number;
  validStructure: boolean;
  checks: { id: 'estrutura' | 'rr' | 'risco' | 'tamanho'; ok: boolean; text: string }[];
}

/** Plano de operação do simulador da Academia (função pura, testável). */
export function simulate(i: SimInput): SimResult {
  const riskUsd = Math.max(0, i.capital) * (Math.max(0, i.riskPct) / 100);
  const unitRisk = Math.abs(i.entry - i.stop);
  const unitReward = Math.abs(i.target - i.entry);
  const byRisk = unitRisk > 0 ? Math.floor(riskUsd / unitRisk) : 0;
  const byCapital = i.entry > 0 ? Math.floor(i.capital / i.entry) : 0;
  const quantity = Math.max(0, Math.min(byRisk, byCapital));
  const rr = unitRisk > 0 ? unitReward / unitRisk : 0;
  const validStructure = i.direction === 'LONG' ? i.stop < i.entry && i.target > i.entry : i.stop > i.entry && i.target < i.entry;
  return {
    quantity,
    plannedRisk: quantity * unitRisk,
    plannedReward: quantity * unitReward,
    rr,
    validStructure,
    checks: [
      { id: 'estrutura', ok: validStructure, text: validStructure ? 'Entrada, stop e alvo coerentes com a direção.' : 'Stop e alvo não combinam com a direção escolhida.' },
      { id: 'rr', ok: rr >= 2, text: rr >= 2 ? 'Risco/retorno de pelo menos 2R.' : 'Risco/retorno abaixo de 2R: considere Sem setup.' },
      { id: 'risco', ok: i.riskPct <= 2, text: i.riskPct <= 2 ? 'Risco por operação dentro de 2%.' : 'Risco acima de 2% do capital.' },
      { id: 'tamanho', ok: quantity > 0, text: quantity > 0 ? 'O tamanho cabe no capital e no risco.' : 'Com esse stop, nenhuma unidade cabe no risco.' },
    ],
  };
}
