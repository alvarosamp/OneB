import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '../../context/ToastContext';
import { clearApiCache } from '../../hooks/useApi';

const getMock = vi.fn();
const postMock = vi.fn();
vi.mock('../../api/client', async (orig) => {
  const actual = await orig<typeof import('../../api/client')>();
  return { ...actual, api: { ...actual.api, get: (p: string) => getMock(p), post: (p: string, b: unknown) => postMock(p, b) } };
});

import { CommandPaletteProvider, useCommandPalette } from './CommandPaletteContext';

function Where() {
  const loc = useLocation();
  return <p data-testid="where">{loc.pathname + loc.search}</p>;
}

function Opener() {
  const { open } = useCommandPalette();
  return (
    <button type="button" onClick={open}>
      abrir
    </button>
  );
}

function setup() {
  return render(
    <MemoryRouter initialEntries={['/ferramenta']}>
      <ToastProvider>
        <CommandPaletteProvider>
          <Opener />
          <Routes>
            <Route path="*" element={<Where />} />
          </Routes>
        </CommandPaletteProvider>
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe('CommandPalette', () => {
  beforeEach(() => {
    clearApiCache();
    getMock.mockReset();
    postMock.mockReset();
    getMock.mockResolvedValue([
      { id: 1, symbol: 'NVDA', label: 'NVIDIA', asset_type: 'equity', active: true },
      { id: 2, symbol: 'AAPL', label: 'Apple', asset_type: 'equity', active: true },
    ]);
  });

  it('abre com Ctrl+K e fecha com Esc', async () => {
    const user = userEvent.setup();
    setup();
    await user.keyboard('{Control>}k{/Control}');
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toHaveFocus();
    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('busca um ativo e abre o gráfico só com o teclado', async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByText('abrir'));
    await screen.findByRole('dialog');
    await user.keyboard('nvd');
    await screen.findByRole('option', { name: /NVDA/ });
    await user.keyboard('{Enter}');
    // nível de ações
    expect(await screen.findByRole('option', { name: /Abrir gráfico/ })).toHaveAttribute('aria-selected', 'true');
    await user.keyboard('{Enter}');
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/ativo/NVDA'));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('Esc no nível de ações volta para a busca', async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByText('abrir'));
    await user.keyboard('aapl');
    await screen.findByRole('option', { name: /AAPL/ });
    await user.keyboard('{Enter}');
    await screen.findByRole('option', { name: /Criar alerta/ });
    await user.keyboard('{Escape}');
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toHaveAttribute('aria-label', 'Buscar ativo ou página');
  });

  it('adiciona à watchlist um símbolo digitado fora dela', async () => {
    const user = userEvent.setup();
    postMock.mockResolvedValue({ id: 3, symbol: 'MSFT', label: '', asset_type: 'equity', active: true });
    setup();
    await user.click(screen.getByText('abrir'));
    await user.keyboard('msft');
    await screen.findByRole('option', { name: /MSFT.*fora da watchlist/ });
    await user.keyboard('{Enter}');
    await screen.findByRole('option', { name: /Adicionar à watchlist/ });
    await user.keyboard('{ArrowUp}{Enter}');
    await waitFor(() => expect(postMock).toHaveBeenCalledWith('/api/watchlist', { symbol: 'MSFT', label: '', asset_type: '' }));
    expect(await screen.findByText('MSFT adicionado à watchlist')).toBeInTheDocument();
  });

  it('mantém o foco preso no diálogo com Tab', async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByText('abrir'));
    await user.keyboard('nvda');
    await screen.findByRole('option', { name: /NVDA/ });
    await user.keyboard('{Enter}');
    await screen.findByRole('option', { name: /Abrir gráfico/ });
    const dialog = screen.getByRole('dialog');
    for (let i = 0; i < 4; i++) {
      await user.tab();
      expect(dialog.contains(document.activeElement)).toBe(true);
    }
    await act(async () => undefined);
  });
});
