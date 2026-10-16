import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { useApiMock } = vi.hoisted(() => ({ useApiMock: vi.fn() }));
vi.mock('../../hooks/useApi', () => ({ useApi: useApiMock }));

import { Conta } from './Conta';

const ready = <T,>(data: T) => ({ data, status: 'ready', error: null, errorStatus: null, lastUpdated: new Date(), refreshing: false, retry: vi.fn(), mutate: vi.fn() });

const sizing = {
  balance: 1000,
  risk_pct: 1,
  stop_atr: 1.5,
  note: 'Stop por ATR de 1 hora.',
  rows: [
    { key: 'EURUSD', label: 'Euro/dólar', symbol: 'EURUSD.s', available: true, stop_distance: 0.00216, volume_min: 0.01, lots: 0.04, below_minimum: false,
      actual_risk: 8.65, actual_risk_pct: 0.865, min_lot_risk: 2.16, min_lot_risk_pct: 0.216, min_balance: 216, spread_share: 0.056 },
    { key: 'SPX500', label: 'S&P 500', symbol: 'US500.s', available: true, stop_distance: 33.75, volume_min: 0.1, lots: 0.2, below_minimum: false,
      actual_risk: 6.75, actual_risk_pct: 0.675, min_lot_risk: 3.38, min_lot_risk_pct: 0.338, min_balance: 338, spread_share: 0.157 },
    { key: 'XAUUSD', label: 'Ouro', symbol: 'XAUUSD.s', available: true, stop_distance: 30.49, volume_min: 0.01, lots: 0, below_minimum: true,
      actual_risk: 0, actual_risk_pct: 0, min_lot_risk: 30.49, min_lot_risk_pct: 3.049, min_balance: 3049, spread_share: 0.009 },
    { key: 'NAS100', label: 'Nasdaq 100', symbol: 'US100.s', available: false },
  ],
};

describe('Quanto operar', () => {
  beforeEach(() => {
    useApiMock.mockReset();
    useApiMock.mockReturnValue(ready(sizing));
  });

  it('diz o que cabe, marca o que não cabe e avisa do custo alto', () => {
    render(<Conta />);
    expect(screen.getByText(/cabem: Euro\/dólar, S&P 500\./)).toBeInTheDocument();
    expect(screen.getByText(/US\$ 30,49 \(3,0% da conta\) no lote mínimo/)).toBeInTheDocument();
    expect(screen.getByText(/15,7% · custo alto/)).toBeInTheDocument();
    expect(screen.getByText(/S&P 500 cabe na conta, mas o spread consome 16% do stop/)).toBeInTheDocument();
    expect(screen.getByText(/sem dados de mercado agora/)).toBeInTheDocument();
  });

  it('pede o saldo de novo quando o valor muda e não consulta com saldo inválido', async () => {
    render(<Conta />);
    expect(useApiMock).toHaveBeenLastCalledWith('/api/analysis/sizing?balance=1000&risk_pct=1&stop_atr=1.5', expect.anything());
    const input = screen.getByLabelText('Saldo da conta no MT5 (US$)');
    await userEvent.clear(input);
    await userEvent.type(input, '5.000');
    // espera a pessoa parar de digitar: não consulta com '5', '5.', '5.0'...
    await waitFor(() => expect(useApiMock).toHaveBeenLastCalledWith('/api/analysis/sizing?balance=5000&risk_pct=1&stop_atr=1.5', expect.anything()));
    expect(useApiMock.mock.calls.some((c) => c[0] === '/api/analysis/sizing?balance=5&risk_pct=1&stop_atr=1.5')).toBe(false);
    await userEvent.clear(input);
    await waitFor(() => expect(useApiMock).toHaveBeenLastCalledWith(null, expect.anything()));
    expect(screen.getByText('Informe o saldo da conta em dólar.')).toBeInTheDocument();
  });
});
