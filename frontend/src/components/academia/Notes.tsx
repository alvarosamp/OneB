import { useEffect, useRef, useState } from 'react';
import { fetchLessonState, readNote, saveNoteRemote, writeNote } from '../../lib/academia';
import { Textarea } from '../ui';
import styles from './Player.module.css';

type Status = 'loading' | 'idle' | 'saving' | 'saved' | 'local';

/**
 * Anotações por aula, salvas na conta (servidor) com salvamento automático.
 * O localStorage é só cache: se a API falhar, a anotação fica neste navegador
 * e é enviada na próxima edição.
 */
export function Notes({ lessonId }: { lessonId: number }) {
  const [text, setText] = useState(() => readNote(lessonId));
  const [status, setStatus] = useState<Status>('loading');
  const saved = useRef(text);

  useEffect(() => {
    let alive = true;
    const local = readNote(lessonId);
    setText(local);
    saved.current = local;
    setStatus('loading');
    fetchLessonState(lessonId)
      .then((s) => {
        if (!alive) return;
        // Anotação antiga só local (antes da conta guardar) vence uma vazia no servidor.
        const value = s.note || local;
        setText(value);
        saved.current = s.note;
        setStatus('idle');
      })
      .catch(() => alive && setStatus('local'));
    return () => {
      alive = false;
    };
  }, [lessonId]);

  useEffect(() => {
    // Durante um envio, espera: quando ele termina o status muda e o efeito roda de novo.
    if (status === 'loading' || status === 'saving' || text === saved.current) return;
    const id = setTimeout(() => {
      writeNote(lessonId, text);
      setStatus('saving');
      saveNoteRemote(lessonId, text)
        .then(() => {
          saved.current = text;
          setStatus('saved');
        })
        .catch(() => setStatus('local'));
    }, 600);
    return () => clearTimeout(id);
  }, [text, lessonId, status]);

  const hint =
    status === 'local'
      ? 'Sem conexão com a conta: a anotação ficou só neste navegador e será enviada na próxima edição.'
      : status === 'saving'
        ? 'Salvando…'
        : `Salvas na sua conta, em qualquer aparelho${status === 'saved' ? ' (salvo)' : ''}.`;

  return (
    <div className={styles.quiz}>
      <Textarea
        label="Anotações desta aula"
        rows={8}
        value={text}
        disabled={status === 'loading'}
        onChange={(e) => setText(e.target.value)}
        placeholder="Regras, dúvidas e pontos de atenção."
        hint={hint}
      />
    </div>
  );
}
