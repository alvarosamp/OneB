import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';

const getMock = vi.fn();
vi.mock('../api/client', async (orig) => {
  const actual = await orig<typeof import('../api/client')>();
  return { ...actual, api: { ...actual.api, get: (path: string) => getMock(path) } };
});

import { clearApiCache, useApi } from './useApi';

describe('useApi', () => {
  beforeEach(() => {
    getMock.mockReset();
    clearApiCache();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('começa em loading e termina em ready com o dado', async () => {
    getMock.mockResolvedValue([{ id: 1 }]);
    const { result } = renderHook(() => useApi<{ id: number }[]>('/api/x'));
    expect(result.current.status).toBe('loading');
    await waitFor(() => expect(result.current.status).toBe('ready'));
    expect(result.current.data).toEqual([{ id: 1 }]);
    expect(result.current.lastUpdated).toBeInstanceOf(Date);
  });

  it('distingue vazio de zero', async () => {
    getMock.mockResolvedValueOnce([]);
    const { result } = renderHook(() => useApi<number[]>('/api/vazio'));
    await waitFor(() => expect(result.current.status).toBe('empty'));

    getMock.mockResolvedValueOnce(0);
    const { result: zero } = renderHook(() => useApi<number>('/api/zero'));
    await waitFor(() => expect(zero.current.status).toBe('ready'));
    expect(zero.current.data).toBe(0);
  });

  it('expõe o erro e permite tentar de novo', async () => {
    getMock.mockRejectedValueOnce(new ApiError(500, 'falhou'));
    const { result } = renderHook(() => useApi<{ ok: boolean }>('/api/erro'));
    await waitFor(() => expect(result.current.status).toBe('error'));
    expect(result.current.error).toContain('500');

    getMock.mockResolvedValueOnce({ ok: true });
    act(() => result.current.retry());
    await waitFor(() => expect(result.current.status).toBe('ready'));
    expect(result.current.error).toBeNull();
  });

  it('trata 404 como vazio, mantendo a causa', async () => {
    getMock.mockRejectedValueOnce(new ApiError(404, 'Sem histórico'));
    const { result } = renderHook(() => useApi('/api/regime/XYZ'));
    await waitFor(() => expect(result.current.status).toBe('empty'));
    expect(result.current.error).toContain('Sem histórico');
  });

  it('mantém o último dado quando uma atualização falha', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    getMock.mockResolvedValueOnce({ v: 1 }).mockRejectedValueOnce(new ApiError(0, 'sem conexão'));
    const { result } = renderHook(() => useApi<{ v: number }>('/api/poll', { pollMs: 1000 }));
    await waitFor(() => expect(result.current.status).toBe('ready'));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1100);
    });
    await waitFor(() => expect(result.current.error).toBe('sem conexão'));
    expect(result.current.status).toBe('ready');
    expect(result.current.data).toEqual({ v: 1 });
  });

  it('não busca quando desabilitado', () => {
    const { result } = renderHook(() => useApi('/api/x', { enabled: false }));
    expect(getMock).not.toHaveBeenCalled();
    expect(result.current.status).toBe('empty');
  });
});
