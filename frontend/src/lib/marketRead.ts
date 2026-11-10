import type { RegimeReport, TechnicalAnalysis } from '../types';
import { biasFromLabel, type Bias, type DecisionState } from './decisionState';
import { formatNumber, formatSigned } from './format';

/**
 * Leitura de um ativo a partir de dados que a API já entrega:
 * regime diário (regime_engine) + análise técnica (technical/analysis).
 *
 * Regras (documentadas em DESIGN.md › Vocabulário de estado):
 * - Regime e técnica discordam, ou um deles está neutro → Sem setup
 * - Regime e técnica apontam a mesma direção → Observar
 * - Além disso, regime "forte" (STRONG) e MACD alinhado → Setup em formação
 *
 * TODO(backend): esta regra deveria vir da API (decision_engine), para que
 * Hoje, Radar e Assistente usem exatamente o mesmo cálculo.
 */

export interface Evidence {
  text: string;
  /** Sinal da contribuição para o viés (+ alta, − baixa, 0 neutro). */
  tone: 'positive' | 'negative' | 'neutral' | 'warning';
  concept?: string;
}
export interface MarketRead {
  state: DecisionState;
  bias: Bias;
  regimeLabel: string | null;
  regimeScore: number | null;
  macroContext: string | null;
  volatility: string | null;
  atrPct: number | null;
  evidences: Evidence[];
}

export const REGIME_LABEL: Record<string, string> = {
  'STRONG BULL': 'Alta forte',
  BULL: 'Alta',
  NEUTRAL: 'Neutro',
  BEAR: 'Baixa',
  'STRONG BEAR': 'Baixa forte',
};

export const MACRO_LABEL: Record<string, string> = {
  POSITIVO: 'Favorável',
  NEUTRO: 'Neutro',
  NEGATIVO: 'Desfavorável',
};

function macdBias(tech: TechnicalAnalysis | null): Bias {
  const s = tech?.signals.find((x) => x.name === 'macd');
  if (!s) return null;
  return s.state === 'good' ? 'alta' : s.state === 'danger' ? 'baixa' : null;
}

export function readMarket(regime: RegimeReport | null, tech: TechnicalAnalysis | null, techFrame = 'intradiário'): MarketRead | null {
  const local = regime?.local_regime ?? null;
  if (!local && !tech) return null;

  const regimeBias = local ? biasFromLabel(local.label) : null;
  const techBias = tech ? biasFromLabel(tech.bias) : null;
  const macd = macdBias(tech);
  const strong = !!local && local.label.startsWith('STRONG');

  let state: DecisionState = 'sem-setup';
  let bias: Bias = null;
  if (regimeBias && techBias && regimeBias === techBias) {
    bias = regimeBias;
    state = strong && macd === regimeBias ? 'formacao' : 'observar';
  }

  const evidences: Evidence[] = [];
  const toneOf = (b: Bias): Evidence['tone'] => (b === 'alta' ? 'positive' : b === 'baixa' ? 'negative' : 'neutral');

  if (local) {
    const trend = local.factors.find((f) => f.name === 'trend');
    evidences.push({
      text: `Regime diário ${REGIME_LABEL[local.label]?.toLowerCase() ?? local.label} (score ${formatSigned(local.score, 0)}): ${trend ? trendText(trend.evidence) : 'sem fator de tendência'}`,
      tone: toneOf(regimeBias),
      concept: 'regime',
    });
  }
  if (tech) {
    if (techBias === null) {
      evidences.push({ text: `Preço e médias curtas sem direção definida no ${techFrame}`, tone: 'neutral', concept: 'ema' });
    } else {
      evidences.push({
        text: `Preço ${techBias === 'alta' ? 'acima' : 'abaixo'} das médias curtas (EMA 9 e 21) no ${techFrame}`,
        tone: toneOf(techBias),
        concept: 'ema',
      });
    }
    if (macd) {
      evidences.push({ text: `MACD ${macd === 'alta' ? 'acima' : 'abaixo'} da linha de sinal`, tone: toneOf(macd), concept: 'macd' });
    }
    if (tech.rsi !== null) {
      const rsi = tech.rsi;
      const extreme = rsi >= 70 || rsi <= 30;
      evidences.push({
        text: `RSI ${formatNumber(rsi, 1)}${rsi >= 70 ? ', esticado' : rsi <= 30 ? ', sobrevendido' : ''}`,
        tone: extreme ? 'warning' : 'neutral',
        concept: 'rsi',
      });
    }
  }
  if (regimeBias && techBias && regimeBias !== techBias) {
    evidences.unshift({ text: `Regime diário e leitura ${techFrame === 'intradiário' ? 'intradiária' : 'técnica'} apontam em direções opostas`, tone: 'warning' });
  }

  return {
    state,
    bias,
    regimeLabel: local ? (REGIME_LABEL[local.label] ?? local.label) : null,
    regimeScore: local?.score ?? null,
    macroContext: regime ? (MACRO_LABEL[regime.macro_context] ?? regime.macro_context) : null,
    volatility: tech?.volatility_label ?? null,
    atrPct: tech?.atr_pct ?? null,
    evidences: evidences.slice(0, 4),
  };
}

/** "EMA20 abaixo da EMA50 (25006.30 vs 25536.15)." → "EMA 20 abaixo da EMA 50" */
function trendText(evidence: string): string {
  const m = evidence.match(/EMA\s?(\d+)\s+(acima|abaixo)\s+da\s+EMA\s?(\d+)/i);
  if (m) return `EMA ${m[1]} ${m[2]} da EMA ${m[3]}`;
  return evidence.replace(/\.$/, '');
}
