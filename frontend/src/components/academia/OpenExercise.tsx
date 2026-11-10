import { useState } from 'react';
import { Button, Textarea } from '../ui';
import { ptBR } from '../../lib/text';
import styles from './Player.module.css';

const MIN = 40;

/** Exercício aberto (aulas sem questões objetivas): conclui ao registrar uma resposta. */
export function OpenExercise({ prompt, onPassed, passed }: { prompt: string; onPassed: () => void; passed: boolean }) {
  const [text, setText] = useState('');
  return (
    <div className={styles.quiz}>
      <p className={styles.reading}>{ptBR(prompt)}</p>
      <Textarea label="Sua resposta" rows={5} value={text} onChange={(e) => setText(e.target.value)} hint={`Mínimo de ${MIN} caracteres. Fica salva nas suas anotações.`} />
      <div>
        <Button variant="primary" size="sm" disabled={text.trim().length < MIN || passed} onClick={onPassed}>
          {passed ? 'Exercício registrado' : 'Registrar resposta'}
        </Button>
      </div>
    </div>
  );
}
