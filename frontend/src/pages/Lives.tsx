import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { VideoEmbed } from '../components/VideoEmbed';
import type { LiveSession } from '../types';

function fmtDateTime(iso: string) {
  return new Date(iso).toLocaleString('pt-BR', {
    weekday: 'short',
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function Lives() {
  const [lives, setLives] = useState<LiveSession[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<LiveSession[]>('/api/lives')
      .then(setLives)
      .catch(() => setError('Não foi possível carregar as lives agora.'));
  }, []);

  const live = lives?.find((l) => l.status === 'LIVE') ?? null;
  const scheduled = lives?.filter((l) => l.status === 'SCHEDULED') ?? [];
  const ended = lives?.filter((l) => l.status === 'ENDED') ?? [];

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <p className="eyebrow">Ao vivo</p>
          <h1>Lives</h1>
          <p className="muted">Salas de mercado em tempo real e replays das últimas transmissões.</p>
        </div>
      </div>

      {error && <p className="form-error">{error}</p>}

      {live && (
        <section className="panel" style={{ marginBottom: '1.5rem' }}>
          <div className="panel-title">
            <h2>🔴 Ao vivo agora: {live.title}</h2>
          </div>
          <p className="muted">{live.description}</p>
          {live.stream_url ? (
            <VideoEmbed url={live.stream_url} title={live.title} />
          ) : (
            <div className="course-video-placeholder">
              <span>▶</span>
              <p className="muted">Transmissão em andamento</p>
            </div>
          )}
        </section>
      )}

      <section className="panel" style={{ marginBottom: '1.5rem' }}>
        <div className="panel-title">
          <h2>Próximas lives</h2>
        </div>
        {scheduled.length === 0 ? (
          <p className="muted">Nenhuma live agendada no momento.</p>
        ) : (
          <ul className="items-list">
            {scheduled.map((session) => (
              <li key={session.id}>
                <strong>{session.title}</strong>
                <span className="muted block-text">{fmtDateTime(session.scheduled_at)}</span>
                {session.description && <p className="muted">{session.description}</p>}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Replays</h2>
        </div>
        {ended.length === 0 ? (
          <p className="muted">Ainda sem replays disponíveis.</p>
        ) : (
          <div className="course-grid">
            {ended.map((session) => (
              <div key={session.id} className="course-card">
                <h2>{session.title}</h2>
                <p className="muted">{fmtDateTime(session.scheduled_at)}</p>
                {session.replay_url ? (
                  <VideoEmbed url={session.replay_url} title={session.title} />
                ) : (
                  <p className="muted">Replay em breve.</p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
