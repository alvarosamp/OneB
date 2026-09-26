import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { RedirectTo } from './RedirectTo';

function Where() {
  const loc = useLocation();
  return <p data-testid="where">{`${loc.pathname}${loc.search}`}</p>;
}

function renderAt(url: string) {
  render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/regime" element={<RedirectTo to="/analise" params={{ tab: 'regime' }} />} />
        <Route path="/mesa-ia" element={<RedirectTo to="/assistente" params={{ modo: 'mercado' }} />} />
        <Route path="/antigo/:symbol" element={<RedirectTo to="/ativo/:symbol" />} />
        <Route path="*" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  );
  return screen.getByTestId('where').textContent;
}

describe('RedirectTo', () => {
  it('leva a rota antiga para a aba nova', () => {
    expect(renderAt('/regime')).toBe('/analise?tab=regime');
  });

  it('preserva a query existente', () => {
    expect(renderAt('/regime?symbol=AAPL')).toBe('/analise?symbol=AAPL&tab=regime');
  });

  it('usa o parâmetro de modo do Assistente', () => {
    expect(renderAt('/mesa-ia')).toBe('/assistente?modo=mercado');
  });

  it('repassa parâmetros de rota', () => {
    expect(renderAt('/antigo/NVDA')).toBe('/ativo/NVDA');
  });
});
