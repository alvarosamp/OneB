import { useEffect, useState } from 'react';
import { readNote, writeNote } from '../../lib/academia';
import { Textarea } from '../ui';
import styles from './Player.module.css';

/**
 * Anotações por aula. A API não tem endpoint de anotações: ficam no
 * localStorage deste navegador (com aviso), salvas automaticamente.
 */
export function Notes({ lessonId }: { lessonId: number }) {
  const [text, setText] = useState(() => readNote(lessonId));
  const [status, setStatus] = useState<'idle' | 'saved' | 'failed'>('idle');

  useEffect(() => {
    setText(readNote(lessonId));
    setStatus('idle');
  }, [lessonId]);

  useEffect(() => {
    const id = setTimeout(() => {
      if (text === readNote(lessonId)) return;
      setStatus(writeNote(lessonId, text) ? 'saved' : 'failed');
    }, 600);
    return () => clearTimeout(id);
  }, [text, lessonId]);

  return (
    <div className={styles.quiz}>
      <Textarea
        label="Anotações desta aula"
        rows={8}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Regras, dúvidas e pontos de atenção."
        hint={
          status === 'failed'
            ? 'Não foi possível salvar: o navegador bloqueou o armazenamento local.'
            : `Ficam salvas só neste navegador${status === 'saved' ? ' (salvo)' : ''}.`
        }
      />
    </div>
  );
}
