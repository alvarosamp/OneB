import type { CopilotAnalysis } from '../types';
import type { DataConfidence } from '../components/assistant/AnswerCard';
import { biasFromLabel, type DecisionRead } from './decisionState';

/**
 * Tradução do Copiloto (app/copilot.py) para o vocabulário da UI.
 * OBSERVAR_COMPRA (≥3 agentes construtivos e confiança ≥ 60) → Setup em formação, viés de alta
 * AGUARDAR_CONFIRMACAO → Observar (viés do agente técnico, se houver)
 * EVITAR_POR_ENQUANTO → Sem setup
 */
export function readCopilot(a: CopilotAnalysis): DecisionRead {
  if (a.bias === 'OBSERVAR_COMPRA') return { state: 'formacao', bias: 'alta' };
  if (a.bias === 'EVITAR_POR_ENQUANTO') return { state: 'sem-setup', bias: null };
  const tech = a.votes.find((v) => v.name.toLowerCase().startsWith('tecn'));
  return { state: 'observar', bias: tech ? voteBias(tech.vote) : null };
}

/** Votos dos agentes sem verbo de ordem. */
export function voteLabel(vote: string): string {
  const v = vote.toLowerCase();
  if (v.startsWith('compr')) return 'Construtivo';
  if (v.startsWith('evit') || v.startsWith('vend')) return 'Desfavorável';
  return 'Neutro';
}

function voteBias(vote: string) {
  const v = vote.toLowerCase();
  if (v.startsWith('compr')) return 'alta' as const;
  if (v.startsWith('evit') || v.startsWith('vend')) return 'baixa' as const;
  return biasFromLabel(vote);
}

export function dataConfidence(level: string | null | undefined): DataConfidence {
  switch ((level ?? '').toUpperCase()) {
    case 'HIGH':
      return 'alta';
    case 'MEDIUM':
      return 'media';
    case 'LOW':
      return 'baixa';
    default:
      return null;
  }
}

/** Status do plano do Copiloto sem verbos de ordem. */
export function planStatusLabel(status: string | undefined): string {
  const s = (status ?? '').toUpperCase();
  if (s.startsWith('OBSERVAR')) return 'Aguardando confirmação do gatilho';
  if (s.includes('NÃO') || s.includes('NAO')) return 'Sem setup: níveis só como referência';
  return 'Aguardar confirmação';
}

/** Primeira frase de um texto livre (para "conclusão em uma frase"). */
export function firstSentence(text: string): string {
  const clean = text.trim();
  const m = clean.match(/^(.+?[.!?])(\s|$)/s);
  return m ? m[1] : clean;
}

/** Quebra uma resposta livre em parágrafos e itens de lista. */
export function splitAnswer(text: string): { conclusion: string; points: string[]; rest: string[] } {
  const lines = text
    .split(/\n+/)
    .map((l) => l.trim())
    .filter(Boolean);
  const points: string[] = [];
  const rest: string[] = [];
  for (const line of lines) {
    const m = line.match(/^(?:[-*•]|\d+[.)])\s+(.*)$/);
    if (m) points.push(m[1]);
    else rest.push(line);
  }
  const first = rest.length ? firstSentence(rest[0]) : points.shift() ?? '';
  if (rest.length) {
    const remainder = rest[0].slice(first.length).trim();
    rest[0] = remainder;
  }
  return { conclusion: first, points, rest: rest.filter(Boolean) };
}
