import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider } from '../context/AuthContext';
import { ProGate } from './ProGate';

const baseUser = {
  id: 1,
  username: 'ana',
  email: 'ana@teste.com',
  is_admin: false,
  created_at: '2026-01-01T00:00:00Z',
  paid: false,
  on_trial: false,
  trial_ends_at: null,
  telegram_linked: false,
};

function renderGate(plan: 'free' | 'pro') {
  localStorage.setItem('nasdaq_token', 't');
  globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ ...baseUser, plan }) });
  return render(
    <MemoryRouter>
      <AuthProvider>
        <ProGate feature="Painel de risco">
          <p>conteudo pro</p>
        </ProGate>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('ProGate', () => {
  beforeEach(() => localStorage.clear());

  it('shows the upgrade card to free users', async () => {
    renderGate('free');
    await waitFor(() => expect(screen.getByText('Ver planos')).toBeTruthy());
    expect(screen.queryByText('conteudo pro')).toBeNull();
  });

  it('renders the page for pro users (paid or on trial)', async () => {
    renderGate('pro');
    await waitFor(() => expect(screen.getByText('conteudo pro')).toBeTruthy());
  });
});
