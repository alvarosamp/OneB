import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { postMock } = vi.hoisted(() => ({ postMock: vi.fn() }));
vi.mock('../../api/client', () => ({ api: { post: postMock }, ApiError: class extends Error {} }));

import { Simulador } from './Simulador';
import type { Simulation } from './types';

const sim: Simulation = {
  profile: { key: 'moderado', label: 'Moderado', text: 'Aceita oscilação numa parte do dinheiro.', factors: ['Prazo de 10 anos: longo.'] },
  horizon: 'longo',
  steps: [{ title: '1. Monte a reserva de emergência', text: 'Guarde R$ 15.000.' }],
  reserve: { target: 15000, months_to_fill: 47 },
  allocation: [
    { key: 'tesouro_ipca', label: 'Tesouro IPCA+', pct: 35, group: 'renda_fixa', risk: 2, initial_amount: 0, monthly_amount: 105, monthly_from: 48, liquidity: 'D+1', guarantee: 'Tesouro', tax: 'IR', reason: 'Protege da inflação.' },
    { key: 'acoes_br', label: 'Ações brasileiras via ETF (índice)', pct: 20, group: 'renda_variavel', risk: 4, initial_amount: 0, monthly_amount: 60, monthly_from: 48, liquidity: 'D+2', guarantee: 'Nenhuma', tax: '15%', reason: 'Prazo longo.' },
  ],
  projection: {
    months: 120, years: 10, invested: 37000, p10: 60000, median: 70000, p90: 85000, median_today_money: 45000, poupanca: 52000, vs_poupanca: 18000,
    loss_probability: 0.01, has_variable: true,
    timeline: [
      { month: 0, invested: 1000, p10: 1000, p50: 1000, p90: 1000, poupanca: 1000 },
      { month: 120, invested: 37000, p10: 60000, p50: 70000, p90: 85000, poupanca: 52000 },
    ],
  },
  assumptions: { selic: 13.75, cdi: 13.65, ipca_12m: 4.58, poupanca: 6.17, ipca_real_rate: 6.5, prefixado_rate: 12.65,
    variable: { acoes_br: { premium_over_cdi: 2, volatility_pct: 24 } }, rates_as_of: '2026-10-27', rates_stale: false, scenarios: 2000 },
  warnings: ['Em prazos longos, supor CDI constante é uma simplificação.'],
  disclaimer: 'Simulação educacional (Resoluções CVM 19 e 20).',
};

describe('Simulador', () => {
  beforeEach(() => postMock.mockReset());

  it('envia o caso e mostra perfil, divisão com o porquê e a faixa', async () => {
    postMock.mockResolvedValue(sim);
    render(<Simulador />);
    await userEvent.click(screen.getByRole('button', { name: 'Simular' }));
    const [path, body] = postMock.mock.calls[0];
    expect(path).toBe('/api/brasil/simulate');
    expect(body).toMatchObject({ initial: 1000, monthly: 300, months: 120, goal: 'aposentadoria', has_reserve: false, monthly_expenses: 2500 });
    expect(await screen.findByText('Seu perfil: Moderado')).toBeInTheDocument();
    expect(screen.getByText('Protege da inflação.')).toBeInTheDocument();
    expect(screen.getByText(/R\$ 105\/mês a partir do mês 48/)).toBeInTheDocument();
    expect(screen.getByText(/R\$ 60\.000 a R\$ 85\.000/)).toBeInTheDocument();
    expect(screen.getByText(/CVM 19 e 20/)).toBeInTheDocument();
  });

  it('não envia sem dinheiro', async () => {
    render(<Simulador />);
    await userEvent.clear(screen.getByLabelText('Quanto você tem para começar (R$)'));
    await userEvent.clear(screen.getByLabelText('Quanto consegue guardar por mês (R$)'));
    await userEvent.click(screen.getByRole('button', { name: 'Simular' }));
    expect(screen.getByRole('alert')).toHaveTextContent(/valor inicial ou um aporte mensal/);
    expect(postMock).not.toHaveBeenCalled();
  });
});
