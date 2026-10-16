import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { useApiMock, postMock } = vi.hoisted(() => ({ useApiMock: vi.fn(), postMock: vi.fn() }));
vi.mock('../../hooks/useApi', () => ({ useApi: useApiMock }));
vi.mock('../../api/client', () => ({ api: { post: postMock, delete: vi.fn() } }));

import { Sinal } from './Sinal';

const ready = <T,>(data: T) => ({ data, status: 'ready', error: null, errorStatus: null, lastUpdated: new Date(), refreshing: false, retry: vi.fn(), mutate: vi.fn() });

describe('Avaliar sinal', () => {
  beforeEach(() => {
    useApiMock.mockReset();
    postMock.mockReset();
    useApiMock.mockReturnValue(ready({ signals: [], scoreboard: [], note: '' }));
  });

  it('envia o texto colado e mostra a chance de cada alvo contra o necessário para empatar', async () => {
    postMock.mockResolvedValue({
      ok: true, asset: 'XAUUSD', label: 'Ouro', symbol: 'XAUUSD.s',
      signal: { direction: 'long', entry: 4180.5, stop: 4170, targets: [4185], stop_distance: 10.5 },
      stop_atr: 0.81, targets: [{ price: 4185, distance: 4.5, target_r: 0.43, p_target: 0.68, ci95: [0.66, 0.71], p_stop: 0.32, p_open_24h: 0, mean_r: -0.02, breakeven_p: 0.7, n: 1720 }],
      sample: { n: 860, from: null, to: null }, warnings: ['O spread come 20% desse stop: custo alto.'],
      sizing: { risk_money: 10, lots: 0, below_minimum: true, min_lot_risk: 10.5, actual_risk: 0 },
      verdict: 'Com esse stop e esse primeiro alvo...', method: 'Taxa-base medida...', tracked_id: 3,
    });
    render(<Sinal />);
    await userEvent.type(screen.getByLabelText('Sinal'), 'OURO COMPRA 4180 SL 4170 TP1 4185');
    await userEvent.type(screen.getByLabelText('De onde veio (ex.: VTX)'), 'VTX');
    await userEvent.type(screen.getByLabelText('Saldo no MT5 (US$, opcional)'), '1000');
    await userEvent.click(screen.getByRole('button', { name: 'Avaliar' }));
    expect(postMock).toHaveBeenCalledWith('/api/signals/evaluate', {
      text: 'OURO COMPRA 4180 SL 4170 TP1 4185', source: 'VTX', balance: 1000, risk_pct: 1, track: true,
    });
    expect(await screen.findByText('68%')).toBeInTheDocument();
    expect(screen.getByText('70%')).toBeInTheDocument();
    expect(screen.getByText('-0,02R')).toBeInTheDocument();
    expect(screen.getByText(/nem o lote mínimo cabe/)).toBeInTheDocument();
    expect(screen.getByText('O spread come 20% desse stop: custo alto.')).toBeInTheDocument();
  });

  it('mostra o erro de leitura do sinal', async () => {
    postMock.mockResolvedValue({ ok: false, error: 'Não achei o stop. Sinal sem stop não dá para avaliar: o risco é ilimitado.' });
    render(<Sinal />);
    await userEvent.type(screen.getByLabelText('Sinal'), 'ouro compra 4180 alvo 4200');
    await userEvent.click(screen.getByRole('button', { name: 'Avaliar' }));
    expect(await screen.findByText(/Sinal sem stop/)).toBeInTheDocument();
  });
});
