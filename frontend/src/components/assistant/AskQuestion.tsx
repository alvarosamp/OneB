import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { api } from '../../api/client';
import { splitAnswer } from '../../lib/assistant';
import { formatTime } from '../../lib/format';
import type { OneBAskResponse } from '../../types';
import { ThumbsDown, ThumbsUp } from 'lucide-react';
import { Badge, Button, chipClass, EmptyState, ErrorState, ICON, SkeletonLines, Textarea } from '../ui';
import { AnswerCard } from './AnswerCard';
import styles from './Assistant.module.css';

interface Turn {
  id: number;
  question: string;
  at: string;
  status: 'running' | 'done' | 'error';
  answer?: OneBAskResponse;
  error?: string;
}

const SUGGESTIONS = [
  'Como está o mercado hoje? O que preciso saber?',
  'Qual o melhor horário para operar o Nasdaq?',
  'Se eu comprar ouro agora, qual seria o plano?',
  'Tenho US$ 1.000: qual ativo cabe na minha conta?',
  'O plano de hoje bateu o alvo?',
  'Quanto o Nasdaq deve mexer no próximo pregão?',
  'Quando sai o próximo CPI?',
  'Compro ou vendo Nasdaq agora?',
  'Quanto a IA acerta?',
  'Um serviço promete 90% de acerto. Isso é bom?',
  'Quanto custa operar o S&P 500?',
  'O que é ATR?',
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
        { role: 'user', content: t.question },
        { role: 'assistant', content: t.answer ? `${t.answer.answer.headline}. ${t.answer.answer.conclusion}` : '' },
      ]);
    setInput('');
    setTurns((prev) => [...prev, { id, question: q, at: new Date().toISOString(), status: 'running' }]);
    try {
      const res = await api.post<OneBAskResponse>('/api/opportunities/ai/ask', { question: q, history });
      setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, status: 'done', answer: res } : t)));
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
          hint="Enter envia, Shift+Enter quebra linha. A OneB AI consulta o ledger de oportunidades, as estatísticas dos setups, regime, calendário e notícias; cada número é conferido."
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
            {t.status === 'done' && t.answer !== undefined && <OneBAnswerCard response={t.answer} />}
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

/** Resposta estruturada da OneB AI: estado, claims com evidência, contrapontos e o selo do verificador. */
export function OneBAnswerCard({ response }: { response: OneBAskResponse }) {
  const a = response.answer;
  const state = a.state_summary;
  const subtitle = [state.symbol, state.setup?.replace(/_/g, ' '), state.state, state.approval].filter(Boolean).join(' · ');
  const changed = a.what_changed.filter(Boolean);
  const sources = response.tool_calls.filter((n) => n !== 'submit_answer');
  return (
    <AnswerCard
      subject={a.headline}
      subtitle={subtitle || undefined}
      conclusion={a.conclusion}
      evidences={a.claims.map((c) => c.text)}
      counterpoints={a.counter_points.map((c) => c.text)}
      details={
        <div className={styles.paragraphs}>
          {changed.length > 0 && (
            <p>
              <b>O que mudou:</b> {changed.join(' ')}
            </p>
          )}
          {a.unknowns.length > 0 && (
            <p>
              <b>Não sabemos:</b> {a.unknowns.join(' ')}
            </p>
          )}
          <p className="muted">
            Fontes consultadas: {sources.join(', ') || 'leitura automática do ledger'} · modelo {response.model}
          </p>
        </div>
      }
    >
      <div className={styles.answerFooter}>
        {response.fallback_used ? (
          <Badge tone="warning">Resposta automática (sem narrativa de IA)</Badge>
        ) : response.grounding.ok ? (
          <Badge tone="positive">{response.grounding.numbers_checked} número(s) conferido(s) com os dados</Badge>
        ) : (
          <Badge tone="negative">Verificação falhou</Badge>
        )}
        {response.answer_id != null && <AnswerRating answerId={response.answer_id} />}
      </div>
    </AnswerCard>
  );
}

/** Gostei / não gostei de uma resposta; o "não" abre um campo opcional para dizer o que faltou. */
function AnswerRating({ answerId }: { answerId: number }) {
  const [sent, setSent] = useState<1 | -1 | null>(null);
  const [comment, setComment] = useState('');
  const [asking, setAsking] = useState(false);
  async function send(rating: 1 | -1, text?: string) {
    try {
      await api.post('/api/opportunities/ai/feedback', { answer_id: answerId, rating, comment: text || null });
      setSent(rating);
      setAsking(false);
    } catch {
      /* avaliação é opcional: falha silenciosa */
    }
  }
  if (sent) return <span className={styles.hint}>{sent === 1 ? 'Obrigado pela avaliação.' : 'Obrigado: vamos usar isso para melhorar.'}</span>;
  return (
    <span className={styles.rating}>
      <span className={styles.hint}>Esta resposta ajudou?</span>
      <Button variant="ghost" size="sm" icon={<ThumbsUp {...ICON} />} aria-label="Ajudou" onClick={() => void send(1)} />
      <Button variant="ghost" size="sm" icon={<ThumbsDown {...ICON} />} aria-label="Não ajudou" onClick={() => setAsking(true)} />
      {asking && (
        <span className={styles.ratingForm}>
          <input
            className={styles.ratingInput}
            aria-label="O que faltou?"
            placeholder="O que faltou? (opcional)"
            value={comment}
            maxLength={1000}
            onChange={(e) => setComment(e.target.value)}
          />
          <Button size="sm" variant="secondary" onClick={() => void send(-1, comment)}>
            Enviar
          </Button>
        </span>
      )}
    </span>
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
