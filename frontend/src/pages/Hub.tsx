import { Link } from 'react-router-dom';
import { BarChart3, Bot, GraduationCap, Radio, TrendingUp } from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { usePolling } from '../hooks/usePolling';
import { useEffect, useMemo, useState } from 'react';
import type { DashboardSummary, LiveSession } from '../types';

const ENTRY_CARDS = [
  {
    to: '/aprendizado',
    label: 'Escola',
    title: 'Continuar formacao',
    description: 'Aulas, trilhas, pratica guiada e progresso.',
    icon: GraduationCap,
  },
  {
    to: '/ferramenta',
    label: 'Terminal',
    title: 'Abrir painel',
    description: 'Dashboard, watchlist, eventos e alertas.',
    icon: BarChart3,
  },
  {
    to: '/mesa-ia',
    label: 'Mesa IA',
    title: 'Revisar decisoes',
    description: 'Contexto, explicacao, risco e motivos para esperar.',
    icon: Bot,
  },
  {
    to: '/mercado',
    label: 'Mercado',
    title: 'Ver macro',
    description: 'Noticias, calendario e earnings.',
    icon: TrendingUp,
  },
];

function fmtDateTime(iso: string) {
  return new Date(iso).toLocaleString('pt-BR', {
    weekday: 'short',
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function Hub() {
  const { user } = useAuth();
  const { data } = usePolling<DashboardSummary>('/api/dashboard-summary', 30000);
  const [lives, setLives] = useState<LiveSession[]>([]);

  useEffect(() => {
    api.get<LiveSession[]>('/api/lives').then(setLives).catch(() => setLives([]));
  }, []);

  const nextLive = useMemo(
    () =>
      lives
        .filter((live) => live.status === 'LIVE' || live.status === 'SCHEDULED')
        .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())[0],
    [lives],
  );
  const marketRows = data?.rows.slice(0, 4) ?? [];

  return (
    <div className="container command-center academy-home">
      <section className="academy-home-hero">
        <div>
          <p className="eyebrow">OneB Escola</p>
          <h1>Boa noite, {user?.username}.</h1>
          <p className="muted">Continue estudando e aplique o metodo no Terminal.</p>
        </div>
      </section>

      <section className="academy-primary-grid">
        <article className="academy-continue-panel">
          <div>
            <p className="eyebrow">Continuar estudando</p>
            <h2>Price Action na Pratica</h2>
            <p className="muted">Modulo atual: contexto, gatilho, invalidacao e gestao de risco antes do setup.</p>
          </div>
          <div className="learning-progress-row">
            <span>48 de 72 aulas</span>
            <strong>66%</strong>
          </div>
          <div className="course-progress-bar">
            <div className="course-progress-fill" style={{ width: '66%' }} />
          </div>
          <div className="academy-panel-footer">
            <span className="muted">Proxima aula: Gestao de risco profissional</span>
            <Link to="/aulas/price-action" className="oneb-primary">
              Continuar aula
            </Link>
          </div>
        </article>

        <aside className="academy-live-panel">
          <div className="live-icon">
            <Radio size={22} />
          </div>
          <p className="eyebrow">Proxima live</p>
          {nextLive ? (
            <>
              <h2>{nextLive.title}</h2>
              <p className="muted">{fmtDateTime(nextLive.scheduled_at)}</p>
              <span className={`status-pill ${nextLive.status === 'LIVE' ? 'good' : 'warn'}`}>
                {nextLive.status === 'LIVE' ? 'Ao vivo agora' : 'Agendada'}
              </span>
            </>
          ) : (
            <>
              <h2>Agenda em preparacao</h2>
              <p className="muted">Nenhuma live agendada no momento.</p>
            </>
          )}
          <Link to="/lives" className="oneb-secondary">
            Ver agenda
          </Link>
        </aside>
      </section>

      <section className="hub-entry-grid">
        {ENTRY_CARDS.map((card) => {
          const Icon = card.icon;
          return (
            <Link to={card.to} className="hub-entry-card" key={card.label}>
              <Icon size={22} />
              <span>{card.label}</span>
              <h2>{card.title}</h2>
              <p>{card.description}</p>
            </Link>
          );
        })}
      </section>

      <section className="panel market-now-panel">
        <div className="panel-title">
          <div>
            <p className="eyebrow">Mercado agora</p>
            <h2>Aplicacao pratica do estudo</h2>
          </div>
          <Link to="/ferramenta" className="btn-link">
            Abrir Terminal
          </Link>
        </div>
        <div className="market-snapshot-grid">
          {marketRows.length === 0 ? (
            <p className="muted">Adicione ativos na watchlist para ver um snapshot aqui.</p>
          ) : (
            marketRows.map((row) => (
              <article key={row.id}>
                <span>{row.symbol}</span>
                <strong>{row.price !== null ? row.price.toFixed(2) : '-'}</strong>
                <small className={(row.change_pct ?? 0) >= 0 ? 'up' : 'down'}>
                  {row.change_pct !== null ? `${row.change_pct >= 0 ? '+' : ''}${row.change_pct.toFixed(2)}%` : 'sem dados'}
                </small>
              </article>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
