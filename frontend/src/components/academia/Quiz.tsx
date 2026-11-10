import { useState } from 'react';
import { CheckCircle2, XCircle } from 'lucide-react';
import type { QuizQuestion } from '../../content/academia';
import { Button, ICON } from '../ui';
import styles from './Player.module.css';

/**
 * Exercício objetivo com feedback imediato e explicação do porquê.
 * A aula só é "concluída" depois de acertar todas as questões (modelo Alura).
 */
export function Quiz({ questions, onPassed, passed }: { questions: QuizQuestion[]; onPassed: () => void; passed: boolean }) {
  const [answers, setAnswers] = useState<(number | null)[]>(() => questions.map(() => null));

  function choose(qi: number, oi: number) {
    const next = answers.map((a, i) => (i === qi ? oi : a));
    setAnswers(next);
    if (next.every((a, i) => a === questions[i].correct)) onPassed();
  }

  const correctCount = answers.filter((a, i) => a === questions[i].correct).length;

  return (
    <div className={styles.quiz}>
      <p className={styles.quizStatus} aria-live="polite">
        {passed || correctCount === questions.length
          ? 'Exercício concluído. Você já pode concluir a aula.'
          : `${correctCount} de ${questions.length} corretas. Responda todas para concluir a aula.`}
      </p>
      {questions.map((q, qi) => {
        const a = answers[qi];
        const answered = a !== null;
        const right = a === q.correct;
        return (
          <fieldset key={q.question} className={styles.question}>
            <legend>
              {qi + 1}. {q.question}
            </legend>
            <div className={styles.options}>
              {q.options.map((opt, oi) => {
                const selected = a === oi;
                return (
                  <label key={opt} className={[styles.option, selected ? (right ? styles.optionRight : styles.optionWrong) : ''].join(' ')}>
                    <input type="radio" name={`q-${qi}`} checked={selected} onChange={() => choose(qi, oi)} disabled={answered && right} />
                    <span>{opt}</span>
                  </label>
                );
              })}
            </div>
            {answered && (
              <div className={[styles.feedback, right ? styles.feedbackRight : styles.feedbackWrong].join(' ')} role="status">
                {right ? <CheckCircle2 {...ICON} aria-hidden="true" /> : <XCircle {...ICON} aria-hidden="true" />}
                <span>
                  <strong>{right ? 'Correto.' : 'Ainda não.'}</strong> {right ? q.why : 'Releia o resumo e tente outra opção.'}
                </span>
              </div>
            )}
            {answered && !right && (
              <Button size="sm" variant="ghost" onClick={() => setAnswers((prev) => prev.map((x, i) => (i === qi ? null : x)))}>
                Tentar de novo
              </Button>
            )}
          </fieldset>
        );
      })}
    </div>
  );
}
