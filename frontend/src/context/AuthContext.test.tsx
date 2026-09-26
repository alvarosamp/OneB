import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from './AuthContext';
import { clearAccessToken, getAccessToken } from '../api/authStore';

function response(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

/** AuthProvider sempre tenta POST /api/auth/refresh ao montar (o access token vive só em
 * memória e morre no reload), então todo teste precisa responder essa chamada primeiro. */
function mockFetchSequence(...responses: unknown[]) {
  const fetchMock = vi.fn();
  for (const res of responses) fetchMock.mockResolvedValueOnce(res);
  fetchMock.mockResolvedValue(response(401, { detail: 'Sessão expirada' }));
  globalThis.fetch = fetchMock as unknown as typeof fetch;
  return fetchMock;
}

const fakeUser = { id: 1, username: 'pai', is_admin: false, created_at: '2026-01-01T00:00:00Z' };
const noSession = response(401, { detail: 'Sessão expirada — faça login novamente.' });

describe('AuthContext', () => {
  beforeEach(() => {
    clearAccessToken();
    vi.restoreAllMocks();
  });

  it('starts with no user when there is no valid refresh cookie', async () => {
    mockFetchSequence(noSession);

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.user).toBeNull();
    expect(getAccessToken()).toBeNull();
  });

  it('rebuilds the session on load from the refresh cookie alone', async () => {
    mockFetchSequence(
      response(200, { access_token: 'fresh-access', user: fakeUser }),
      response(200, fakeUser),
    );

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.user).toEqual(fakeUser);
    expect(getAccessToken()).toBe('fresh-access');
  });

  it('login() keeps the access token in memory only, never in localStorage', async () => {
    mockFetchSequence(noSession, response(200, { access_token: 'abc123', user: fakeUser }));

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.login('pai', 'senha12345');
    });

    expect(result.current.user).toEqual(fakeUser);
    expect(getAccessToken()).toBe('abc123');
    expect(localStorage.getItem('oneb_market_token')).toBeNull();
    expect(Object.keys(localStorage)).toHaveLength(0);
  });

  it('login() with wrong credentials throws and does not set a user', async () => {
    mockFetchSequence(noSession, response(401, { detail: 'Usuário ou senha inválidos.' }));

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await expect(
      act(async () => {
        await result.current.login('pai', 'errada');
      }),
    ).rejects.toThrow('Usuário ou senha inválidos.');

    expect(result.current.user).toBeNull();
    expect(getAccessToken()).toBeNull();
  });

  it('an expired access token is renewed silently and the original call is retried', async () => {
    const fetchMock = mockFetchSequence(
      noSession, // refresh no mount
      response(200, { access_token: 'abc123', user: fakeUser }), // login
      response(401, { detail: 'Token inválido ou expirado' }), // chamada que expirou
      response(200, { access_token: 'renovado', user: fakeUser }), // refresh silencioso
      response(200, [{ symbol: 'AAPL' }]), // retry da chamada original
    );

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.login('pai', 'senha12345');
    });

    const { api } = await import('../api/client');
    const data = await api.get('/api/watchlist');

    expect(data).toEqual([{ symbol: 'AAPL' }]);
    expect(getAccessToken()).toBe('renovado');
    expect(fetchMock.mock.calls[3][0]).toContain('/api/auth/refresh');
  });

  it('gives up and clears the session when the refresh itself fails', async () => {
    mockFetchSequence(
      noSession,
      response(200, { access_token: 'abc123', user: fakeUser }),
      response(401, { detail: 'Token inválido ou expirado' }),
      response(401, { detail: 'Sessão expirada' }), // refresh recusado
    );

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.login('pai', 'senha12345');
    });

    const { api } = await import('../api/client');
    await expect(api.get('/api/watchlist')).rejects.toThrow('Sessão expirada');

    await waitFor(() => expect(result.current.user).toBeNull());
    expect(getAccessToken()).toBeNull();
  });

  it('logout() clears the user and asks the server to revoke the refresh family', async () => {
    const fetchMock = mockFetchSequence(
      noSession,
      response(200, { access_token: 'abc123', user: fakeUser }),
      response(204, undefined),
    );

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.login('pai', 'senha12345');
    });

    await act(async () => {
      await result.current.logout();
    });

    expect(result.current.user).toBeNull();
    expect(getAccessToken()).toBeNull();
    await waitFor(() => expect(fetchMock.mock.calls[2][0]).toContain('/api/auth/logout'));
    const logoutInit = fetchMock.mock.calls[2][1] as RequestInit;
    expect((logoutInit.headers as Record<string, string>)['X-Refresh-Request']).toBe('1');
  });
});
