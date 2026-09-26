/**
 * Vocabulário único de estado em todo o app. O produto não recomenda:
 * nunca "Operar", "Comprar" ou "Vender".
 */
export type DecisionState = 'sem-setup' | 'observar' | 'formacao';
export type Bias = 'alta' | 'baixa' | null;

export const STATE_LABEL: Record<DecisionState, string> = {
  'sem-setup': 'Sem setup',
  observar: 'Observar',
  formacao: 'Setup em formação',
};

export const BIAS_LABEL: Record<Exclude<Bias, null>, string> = {
  alta: 'viés de alta',
  baixa: 'viés de baixa',
};

export interface DecisionRead {
  state: DecisionState;
  bias: Bias;
}

/** Mapeia as ações do backend (decision_engine) para o vocabulário da UI. */
export function fromBackendAction(action: string | null | undefined): DecisionRead {
  switch ((action ?? '').toUpperCase()) {
    case 'BUY_CONTROLLED':
      return { state: 'formacao', bias: 'alta' };
    case 'SELL_SHORT':
      return { state: 'formacao', bias: 'baixa' };
    case 'WATCH_BUY':
      return { state: 'observar', bias: 'alta' };
    case 'WATCH_SHORT':
      return { state: 'observar', bias: 'baixa' };
    default:
      // NO_TRADE, WAIT, AVOID e desconhecidos
      return { state: 'sem-setup', bias: null };
  }
}

/** Viés a partir de rótulos do backend (ALTISTA/BAIXISTA, BULL/BEAR, LONG/SHORT, COMPRA/VENDA). */
export function biasFromLabel(label: string | null | undefined): Bias {
  const l = (label ?? '').toUpperCase();
  if (/ALTIST|BULL|LONG|ALTA|COMPRA|POSITIV/.test(l)) return 'alta';
  if (/BAIXIST|BEAR|SHORT|BAIXA|VENDA|NEGATIV/.test(l)) return 'baixa';
  return null;
}
