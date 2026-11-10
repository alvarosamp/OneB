import { describe, expect, it } from 'vitest';
import { ptBR } from './text';

describe('ptBR', () => {
  it('acentua palavras comuns do backend preservando caixa', () => {
    expect(ptBR('Preco acima das medias')).toBe('Preço acima das médias');
    expect(ptBR('Pressao e sinais mistos pedem paciencia')).toBe('Pressão e sinais mistos pedem paciência');
    expect(ptBR('ANALISE')).toBe('ANÁLISE');
  });

  it('troca ponto decimal por vírgula', () => {
    expect(ptBR('RSI em 52.84 e volume 1.28x')).toBe('RSI em 52,84 e volume 1,28x');
    expect(ptBR('versão 1.2.3 e hora 10:30')).toBe('versão 1.2.3 e hora 10:30');
  });

  it('não altera palavras já corretas ou parciais', () => {
    expect(ptBR('mediana e análise')).toBe('mediana e análise');
    expect(ptBR(null)).toBe('');
  });
});
