import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LessonBody } from './LessonBody';
import { parseLessonBody } from '../../lib/lessonBody';

describe('LessonBody', () => {
  it('separa subtítulos, listas e parágrafos', () => {
    const blocks = parseLessonBody('Intro\ncontinua.\n\n## Conta\n\n- um\n- dois\n\nFim.');
    expect(blocks).toEqual([
      { kind: 'p', text: 'Intro continua.' },
      { kind: 'h', text: 'Conta' },
      { kind: 'ul', items: ['um', 'dois'] },
      { kind: 'p', text: 'Fim.' },
    ]);
  });

  it('renderiza negrito sem interpretar HTML', () => {
    render(<LessonBody source={'Texto **forte** e <script>x</script>'} />);
    expect(screen.getByText('forte').tagName).toBe('STRONG');
    expect(document.querySelector('script')).toBeNull();
  });

  it('monta tabela com cabeçalho e ignora a linha separadora', () => {
    const blocks = parseLessonBody('Antes\n\n| Ano | R |\n|---|---|\n| 2023 | +0,06 |\n| 2024 | **−0,05** |\n\nDepois');
    expect(blocks[1]).toEqual({ kind: 'table', head: ['Ano', 'R'], rows: [['2023', '+0,06'], ['2024', '**−0,05**']] });
    render(<LessonBody source={'| Ano | R |\n|---|---|\n| 2024 | **−0,05** |'} />);
    expect(screen.getByRole('columnheader', { name: 'Ano' })).toBeTruthy();
    expect(screen.getByText('−0,05').tagName).toBe('STRONG');
  });
});
