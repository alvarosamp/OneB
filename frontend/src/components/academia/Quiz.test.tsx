import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Quiz, type QuizItem } from './Quiz';

const questions: QuizItem[] = [
  { index: 0, question: 'Q1?', options: ['a', 'b'], answered: false },
  { index: 1, question: 'Q2?', options: ['c', 'd'], answered: false },
];
const key: Record<number, number> = { 0: 1, 1: 0 };

describe('Quiz', () => {
  it('confere no servidor, dá feedback e só libera após acertar tudo', async () => {
    const onPassed = vi.fn();
    const solved = new Set<number>();
    const answer = vi.fn(async (index: number, choice: number) => {
      const correct = key[index] === choice;
      if (correct) solved.add(index);
      return { correct, why: correct ? `porque ${choice}` : null, passed: solved.size === 2 };
    });
    const user = userEvent.setup();
    render(<Quiz questions={questions} answer={answer} onPassed={onPassed} passed={false} />);
    await user.click(screen.getByLabelText('a'));
    expect(await screen.findByText('Ainda não.')).toBeInTheDocument();
    await user.click(screen.getByLabelText('b'));
    expect(await screen.findByText('porque 1', { exact: false })).toBeInTheDocument();
    expect(onPassed).not.toHaveBeenCalled();
    await user.click(screen.getByLabelText('c'));
    expect(await screen.findByText(/Exercício concluído/)).toBeInTheDocument();
    expect(onPassed).toHaveBeenCalledTimes(1);
    expect(answer).toHaveBeenCalledWith(1, 0);
  });

  it('mostra como acertadas as questões já resolvidas antes', () => {
    render(<Quiz questions={[{ ...questions[0], answered: true, correct: 1, why: 'já sabia' }]} answer={vi.fn()} onPassed={vi.fn()} passed={false} />);
    expect(screen.getByText('já sabia', { exact: false })).toBeInTheDocument();
  });
});
