/**
 * Plano de risco: quanto operar para arriscar um valor fixo, dado o stop em pontos.
 * Vale para símbolos com lucro em dólar (US100.s, US500.s, XAUUSD.s, EURUSD.s):
 * 1 lote ganha/perde `contractSize` dólares por 1,0 de preço.
 */
export interface RiskPlanInput {
  balance: number;
  riskPct: number; // 1 = 1% do saldo
  stopPoints: number; // distância do stop em preço
  contractSize: number;
  volumeMin: number;
  volumeStep: number;
  spreadPoints: number | null;
}

export interface RiskPlan {
  riskMoney: number;
  lots: number; // arredondado PARA BAIXO ao passo da corretora; 0 se nem o lote mínimo cabe
  actualRisk: number; // risco com o lote arredondado
  spreadCost: number | null; // custo de ida e volta do spread, em dólar
  spreadShareOfRisk: number | null;
  belowMinimum: boolean;
}

export function riskPlan(i: RiskPlanInput): RiskPlan | null {
  if (!(i.balance > 0) || !(i.riskPct > 0) || !(i.stopPoints > 0) || !(i.contractSize > 0) || !(i.volumeStep > 0)) return null;
  const riskMoney = (i.balance * i.riskPct) / 100;
  const perLot = i.stopPoints * i.contractSize;
  const raw = riskMoney / perLot;
  const steps = Math.floor(raw / i.volumeStep + 1e-9);
  const rounded = Number((steps * i.volumeStep).toFixed(6));
  const belowMinimum = rounded < i.volumeMin;
  const lots = belowMinimum ? 0 : rounded;
  const spreadCost = i.spreadPoints != null ? i.spreadPoints * i.contractSize * lots : null;
  const actualRisk = lots * perLot;
  return {
    riskMoney,
    lots,
    actualRisk,
    spreadCost,
    spreadShareOfRisk: spreadCost != null && actualRisk > 0 ? spreadCost / actualRisk : null,
    belowMinimum,
  };
}
