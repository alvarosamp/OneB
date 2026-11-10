import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { api } from '../../api/client';
import { splitAnswer } from '../../lib/assistant';
import { formatTime } from '../../lib/format';
import { Button, chipClass, EmptyState, ErrorState, SkeletonLines, Textarea } from '../ui';
import { AnswerCard } from './AnswerCard';
import styles from './Assistant.module.css';

interface Turn {
  id: number;
  question: string;
  at: string;
  status: 'running' | 'done' | 'error';
  answer?: string;
  error?: string;
}

const SUGGESTIONS = [
  'Quais ativos da minha watchlist merecem mais atenção agora?',
  'Resuma os alertas recentes e os riscos envolvidos.',
  'Há resultados próximos que podem mexer com a carteira?',
  'Compare as notícias recentes com a variação dos ativos.',
  'Monte um checklist para validar um setup antes de agir.',
];

/** Modo "Perguntar": pergunta livre sobre os dados do OneB (antigo Assistente IA). */
export function AskQuestion({ initialQuestion }: { initialQuestion?: string }) {
  const [input, setInput] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);
  const seq = useRef(0);
  const lastRef = useRef<HTMLDivElement>(null);
  const running = turns.some((t) => t.status === 'running');

  useEffect(() => {
    lastRef.current?.scrollIntoView({ block: 'nearest' });
  }, [turns.length]);

  // Pergunta vinda de outro modo (ex.: "Perguntar sobre este alerta") é enviada uma vez.
  const autoAsked = useRef(false);
  useEffect(() => {
    if (initialQuestion && !autoAsked.current) {
      autoAsked.current = true;
      void ask(initialQuestion);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuestion]);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || running) return;
    const id = ++seq.current;
    const history = turns
      .filter((t) => t.status === 'done')
      .slice(-4)
      .flatMap((t) => [
        { role: 'user', text: t.question },
        { role: 'assistant', text: t.answer ?? '' },
      ]);
    setInput('');
    setTurns((prev) => [...prev, { id, question: q, at: new Date().toISOString(), status: 'running' }]);
    try {
      const res = await api.post<{ answer: string }>('/api/assistant/ask', { question: q, history });
      setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, status: 'done', answer: res.answer } : t)));
    } catch (err) {
      setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, status: 'error', error: err instanceof Error ? err.message : 'Erro de conexão' } : t)));
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    void ask(input);
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void ask(input);
    }
  }

  return (
    <div className={styles.mode}>
      <form className={styles.form} onSubmit={submit}>
        <Textarea
          label="Pergunta"
          className={styles.grow}
          rows={2}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKey}
          placeholder="Ex.: compare NVDA e AAPL com base nos alertas e notícias recentes"
          hint="Enter envia, Shift+Enter quebra linha. Responde com base na watchlist, preços, notícias e alertas já coletados."
        />
        <Button type="submit" variant="primary" loading={running} disabled={!input.trim()}>
          Perguntar
        </Button>
      </form>

      {turns.length === 0 && (
        <div className={styles.subsection}>
          <span className={styles.hint}>Perguntas frequentes</span>
          <div className={styles.chips}>
            {SUGGESTIONS.map((s) => (
              <button key={s} type="button" className={chipClass} onClick={() => void ask(s)}>
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className={styles.conversation}>
        {turns.map((t, i) => (
          <div key={t.id} ref={i === turns.length - 1 ? lastRef : undefined} className={styles.subsection}>
            <p className={styles.question}>
              <strong>{t.question}</strong>
              <time dateTime={t.at}>{formatTime(t.at)}</time>
            </p>
            {t.status === 'running' && <SkeletonLines lines={4} label="Buscando nos dados" />}
            {t.status === 'error' && <ErrorState title="O Assistente não respondeu" error={t.error} onRetry={() => void ask(t.question)} />}
            {t.status === 'done' && t.answer !== undefined && <FreeAnswer text={t.answer} />}
          </div>
        ))}
      </div>
      {turns.length > 0 && !running && (
        <div>
          <Button variant="ghost" size="sm" onClick={() => setTurns([])}>
            Limpar conversa
          </Button>
        </div>
      )}
    </div>
  );
}

/** Resposta livre do modelo organizada em conclusão, itens e parágrafos (sem efeito de digitação). */
export function FreeAnswer({ text, subject = 'Resposta' }: { text: string; subject?: string }) {
  if (!text.trim()) return <EmptyState title="Resposta vazia" description="Tente reformular a pergunta." />;
  const { conclusion, points, rest } = splitAnswer(text);
  return (
    <AnswerCard subject={subject} conclusion={conclusion} evidences={points}>
      {rest.length > 0 && (
        <div className={styles.paragraphs}>
          {rest.map((p, i) => (
            <p key={i}>{p}</p>
          ))}
        </div>
      )}
    </AnswerCard>
  );
}
