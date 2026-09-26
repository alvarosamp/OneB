import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Quiz } from './Quiz';

const questions = [
  { question: 'Q1?', options: ['a', 'b'], correct: 1, why: 'porque b' },
  { question: 'Q2?', options: ['c', 'd'], correct: 0, why: 'porque c' },
];

describe('Quiz', () => {
  it('dá feedback imediato e só libera após acertar tudo', async () => {
    const onPassed = vi.fn();
    const user = userEvent.setup();
    render(<Quiz questions={questions} onPassed={onPassed} passed={false} />);
    await user.click(screen.getByLabelText('a'));
    expect(screen.getByText('Ainda não.')).toBeInTheDocument();
    await user.click(screen.getByLabelText('b'));
    expect(screen.getByText('porque b', { exact: false })).toBeInTheDocument();
    expect(onPassed).not.toHaveBeenCalled();
    await user.click(screen.getByLabelText('c'));
    expect(onPassed).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/Exercício concluído/)).toBeInTheDocument();
  });
});
