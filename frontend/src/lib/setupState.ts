import type { ApprovalLevel, SetupStateName } from '../types';

/** Rótulos da máquina de estados de setup (app/opportunity.py). */
export const SETUP_STATE_LABEL: Record<SetupStateName, string> = {
  IDLE: 'Vigiando',
  BREAK_DETECTED: 'Rompimento detectado',
  WAITING_CONFIRMATION_1: 'Aguardando confirmação 1',
  WAITING_CONFIRMATION_2: 'Aguardando confirmação 2',
  READY_TO_ENTER: 'Setup formado',
  POSITION_OPEN: 'Posição shadow aberta',
  TARGET: 'Alvo atingido',
  STOP: 'Stop atingido',
  TIME_EXIT: 'Saída por tempo',
  INVALIDATED: 'Invalidado',
  EXPIRED: 'Expirado',
};

/** Etapas mostradas no stepper, na ordem. */
export const SETUP_STEPS: SetupStateName[] = [
  'BREAK_DETECTED',
  'WAITING_CONFIRMATION_1',
  'WAITING_CONFIRMATION_2',
  'READY_TO_ENTER',
];

const STEP_INDEX: Partial<Record<SetupStateName, number>> = {
  IDLE: -1,
  BREAK_DETECTED: 0,
  WAITING_CONFIRMATION_1: 1,
  WAITING_CONFIRMATION_2: 2,
  READY_TO_ENTER: 3,
  POSITION_OPEN: 4,
  TARGET: 4,
  STOP: 4,
  TIME_EXIT: 4,
};

/** Quantas etapas do stepper já foram cumpridas (estados terminais de falha devolvem null). */
export function completedSteps(state: SetupStateName): number | null {
  const idx = STEP_INDEX[state];
  return idx === undefined ? null : idx;
}

export const APPROVAL_LABEL: Record<ApprovalLevel, string> = {
  RESEARCH: 'Pesquisa',
  SHADOW: 'Shadow (sem ordens)',
  PAPER: 'Paper trading',
  LIVE_MANUAL: 'Liberado (manual)',
};

export const APPROVAL_HINT: Record<ApprovalLevel, string> = {
  RESEARCH: 'Hipótese em pesquisa: nada aqui é recomendação.',
  SHADOW: 'O sistema acompanha e simula, sem enviar ordens. Níveis são plano de pesquisa.',
  PAPER: 'Aprovado para simulação manual com registro do que você fez.',
  LIVE_MANUAL: 'Evidência suficiente para operação manual; a decisão continua sua.',
};

export function isTerminalFailure(state: SetupStateName): boolean {
  return state === 'INVALIDATED' || state === 'EXPIRED' || state === 'STOP';
}
