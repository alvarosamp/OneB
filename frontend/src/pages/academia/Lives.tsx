import { ExternalLink } from 'lucide-react';
import { useApi } from '../../hooks/useApi';
import { formatDateTime } from '../../lib/format';
import { tzLabel, userTimeZone } from '../../lib/marketHours';
import type { LiveSession } from '../../types';
import { AsyncContent, Badge, EmptyState, ICON_SM, PageHeader, Section, SkeletonLines } from '../../components/ui';
import styles from './Academia.module.css';

const STATUS: Record<LiveSession['status'], { label: string; tone: 'warning' | 'info' | 'neutral' }> = {
  LIVE: { label: 'ao vivo agora', tone: 'warning' },
  SCHEDULED: { label: 'agendada', tone: 'info' },
  ENDED: { label: 'encerrada', tone: 'neutral' },
};

/** Lives da Academia: ao vivo, próximas e replays. */
export function Lives() {
  const lives = useApi<LiveSession[]>('/api/lives', { pollMs: 60_000 });
  const tz = tzLabel(userTimeZone());
  return (
    <div className={styles.page}>
      <PageHeader title="Lives" description={`Horários no ${tz}.`} />
      <AsyncContent state={lives} loading={<SkeletonLines lines={6} />} empty={<EmptyState title="Nenhuma live cadastrada" description="Quando uma live for agendada, ela aparece aqui." />}>
        {(list) => {
          const live = list.filter((l) => l.status === 'LIVE');
          const next = list.filter((l) => l.status === 'SCHEDULED').sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));
          const ended = list.filter((l) => l.status === 'ENDED').sort((a, b) => b.scheduled_at.localeCompare(a.scheduled_at));
          const render = (items: LiveSession[], empty: string) =>
            items.length ? (
              <ul className={styles.list}>
                {items.map((l) => {
                  const href = l.status === 'ENDED' ? l.replay_url : l.stream_url;
                  return (
                    <li key={l.id}>
                      <span className={styles.listTitle}>
                        {l.title} <Badge tone={STATUS[l.status].tone}>{STATUS[l.status].label}</Badge>
                      </span>
                      <span className={styles.meta}>{formatDateTime(l.scheduled_at)}</span>
                      <span className={styles.trackSummary}>{l.description}</span>
                      {href ? (
                        <a href={href} target="_blank" rel="noreferrer">
                          {l.status === 'ENDED' ? 'Assistir replay' : 'Entrar na live'} <ExternalLink {...ICON_SM} aria-hidden="true" />
                        </a>
                      ) : (
                        <span className={styles.meta}>{l.status === 'ENDED' ? 'Replay em edição.' : 'O link aparece aqui perto do horário.'}</span>
                      )}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className={styles.meta}>{empty}</p>
            );
          return (
            <>
              {live.length > 0 && <Section title="Ao vivo agora">{render(live, '')}</Section>}
              <Section title="Próximas">{render(next, 'Nenhuma live agendada.')}</Section>
              <Section title="Replays">{render(ended, 'Sem replays ainda.')}</Section>
            </>
          );
        }}
      </AsyncContent>
    </div>
  );
}
