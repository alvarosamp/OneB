import { useState } from 'react';
import { CheckCircle2, XCircle } from 'lucide-react';
import { api } from '../../api/client';
import { useApi } from '../../hooks/useApi';
import { Button, ICON, SkeletonLines } from '../ui';
import styles from './Player.module.css';

export interface QuizItem {
  index: number;
  question: string;
  options: string[];
  answered: boolean;
  correct?: number;
  why?: string;
}

export interface QuizResult {
  correct: boolean;
  why: string | null;
  passed: boolean;
}

type Answer = { choice: number; correct: boolean; why: string | null };

/**
 * Exercício objetivo com feedback imediato. O gabarito fica no servidor: cada
 * resposta é conferida lá, e a aula só pode ser concluída depois de acertar tudo.
 */
export function Quiz({ questions, answer, onPassed, passed }: { questions: QuizItem[]; answer: (index: number, choice: number) => Promise<QuizResult>; onPassed: () => void; passed: boolean }) {
  const [answers, setAnswers] = useState<Record<number, Answer>>(() =>
    Object.fromEntries(questions.filter((q) => q.answered && q.correct !== undefined).map((q) => [q.index, { choice: q.correct!, correct: true, why: q.why ?? null }])),
  );
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function choose(index: number, choice: number) {
    setBusy(index);
    setError(null);
    try {
      const res = await answer(index, choice);
      setAnswers((prev) => ({ ...prev, [index]: { choice, correct: res.correct, why: res.why } }));
      if (res.passed) onPassed();
    } catch {
      setError('Não foi possível conferir a resposta agora. Tente de novo.');
    } finally {
      setBusy(null);
    }
  }

  const correctCount = Object.values(answers).filter((a) => a.correct).length;
  const done = passed || correctCount === questions.length;

  return (
    <div className={styles.quiz}>
      <p className={styles.quizStatus} aria-live="polite">
        {done ? 'Exercício concluído. Você já pode concluir a aula.' : `${correctCount} de ${questions.length} corretas. Responda todas para concluir a aula.`}
      </p>
      {error && (
        <p className={styles.gateNote} role="alert">
          {error}
        </p>
      )}
      {questions.map((q) => {
        const a = answers[q.index];
        const right = a?.correct === true;
        return (
          <fieldset key={q.index} className={styles.question} disabled={busy === q.index}>
            <legend>
              {q.index + 1}. {q.question}
            </legend>
            <div className={styles.options}>
              {q.options.map((opt, oi) => {
                const selected = a?.choice === oi;
                return (
                  <label key={opt} className={[styles.option, selected ? (right ? styles.optionRight : styles.optionWrong) : ''].join(' ')}>
                    <input type="radio" name={`q-${q.index}`} checked={selected} onChange={() => choose(q.index, oi)} disabled={right} />
                    <span>{opt}</span>
                  </label>
                );
              })}
            </div>
            {a && (
              <div className={[styles.feedback, right ? styles.feedbackRight : styles.feedbackWrong].join(' ')} role="status">
                {right ? <CheckCircle2 {...ICON} aria-hidden="true" /> : <XCircle {...ICON} aria-hidden="true" />}
                <span>
                  <strong>{right ? 'Correto.' : 'Ainda não.'}</strong> {right ? a.why : 'Releia o resumo e tente outra opção.'}
                </span>
              </div>
            )}
            {a && !right && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() =>
                  setAnswers((prev) => {
                    const next = { ...prev };
                    delete next[q.index];
                    return next;
                  })
                }
              >
                Tentar de novo
              </Button>
            )}
          </fieldset>
        );
      })}
    </div>
  );
}

/** Quiz da aula vindo do servidor; sem questões, mostra `fallback` (exercício aberto). */
export function ServerQuiz({ lessonId, onPassed, passed, fallback }: { lessonId: number; onPassed: () => void; passed: boolean; fallback: React.ReactNode }) {
  const quiz = useApi<{ questions: QuizItem[]; passed: boolean }>(`/api/lms/lessons/${lessonId}/quiz`);
  if (quiz.status === 'loading') return <SkeletonLines lines={6} />;
  if (!quiz.data || quiz.data.questions.length === 0) return <>{fallback}</>;
  return (
    <Quiz
      key={lessonId}
      questions={quiz.data.questions}
      passed={passed || quiz.data.passed}
      onPassed={onPassed}
      answer={(index, choice) => api.post<QuizResult>(`/api/lms/lessons/${lessonId}/quiz/${index}`, { choice })}
    />
  );
}
