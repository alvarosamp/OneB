import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { PlayCircle } from 'lucide-react';
import { useApi } from '../../hooks/useApi';
import { TRACKS, type TrackMeta } from '../../content/academia';
import { allLessons, findLesson, formatMinutes, lastLesson, totalMinutes, TRACK_STATUS_LABEL, trackStatus } from '../../lib/academia';
import { formatDateTime } from '../../lib/format';
import { ptBR } from '../../lib/text';
import { tzLabel, userTimeZone } from '../../lib/marketHours';
import type { CourseDetail, LearningState, LiveSession } from '../../types';
import { AsyncContent, Badge, ChipGroup, EmptyState, ICON_LG, Skeleton, SkeletonLines } from '../../components/ui';
import { buttonClass } from '../../components/ui/buttonClass';
import styles from './Academia.module.css';

type LevelFilter = 'todos' | TrackMeta['level'];

/** Home da Academia: continuar de onde parou, trilhas em ordem e lives. */
export function AcademiaHome() {
  const state = useApi<LearningState>('/api/lms/learning-state', { isEmpty: (d) => d.courses.length === 0 });
  const [level, setLevel] = useState<LevelFilter>('todos');
  const tracks = TRACKS.filter((t) => level === 'todos' || t.level === level);

  return (
    <div className={styles.page}>
      <header>
        <h1 className={styles.title}>Academia</h1>
        <p className={styles.lead}>Trilhas em ordem, do básico ao processo. Cada aula termina com um exercício curto e prática no gráfico com dado real.</p>
      </header>

      <ContinueBlock state={state} />

      <section aria-labelledby="trilhas-title">
        <h2 id="trilhas-title" className={styles.sectionTitle}>
          Trilhas
        </h2>
        <div className={styles.filters}>
          <ChipGroup
            label="Filtrar por nível"
            value={level}
            onChange={setLevel}
            items={[
              { value: 'todos', label: 'Todos os níveis' },
              { value: 'Iniciante', label: 'Iniciante' },
              { value: 'Intermediário', label: 'Intermediário' },
              { value: 'Avançado', label: 'Avançado' },
            ]}
          />
        </div>
        <AsyncContent state={state} loading={<SkeletonLines lines={6} height={24} />} empty={<EmptyState title="Nenhuma trilha publicada" description="As trilhas aparecem aqui assim que forem publicadas." />}>
          {(data) => (
            <ol className={styles.tracks}>
              {tracks.map((t) => (
                <TrackRow key={t.slug} track={t} summary={data.courses.find((c) => c.slug === t.slug) ?? null} />
              ))}
            </ol>
          )}
        </AsyncContent>
        {state.data?.certificate && (
          <p className={styles.certificate}>
            Certificado: {state.data.certificate.completed_required_lessons} de {state.data.certificate.required_lessons} aulas obrigatórias e{' '}
            {state.data.certificate.completed_simulations} de {state.data.certificate.required_simulations} simulações concluídas.
          </p>
        )}
      </section>

      <LivesBlock />
    </div>
  );
}

function ContinueBlock({ state }: { state: ReturnType<typeof useApi<LearningState>> }) {
  const local = lastLesson();
  const slug = local?.slug ?? state.data?.recommendation?.course_slug ?? null;
  const course = useApi<CourseDetail>(slug ? `/api/lms/courses/${slug}` : null);

  const target = useMemo(() => {
    if (!course.data) return null;
    const lessons = allLessons(course.data);
    const fromLocal = local && local.slug === course.data.slug ? findLesson(course.data, String(local.lessonId)) : null;
    const fromApi = state.data?.recommendation ? findLesson(course.data, String(state.data.recommendation.lesson_id)) : null;
    const lesson = (fromLocal && !fromLocal.completed ? fromLocal : null) ?? fromApi ?? lessons.find((l) => !l.completed) ?? null;
    if (!lesson) return null;
    return { lesson, index: lessons.findIndex((l) => l.id === lesson.id) + 1, total: lessons.length };
  }, [course.data, local, state.data]);

  if (state.status === 'loading' || course.status === 'loading') {
    return (
      <div className={styles.continue}>
        <Skeleton height={90} />
        <SkeletonLines lines={3} />
      </div>
    );
  }
  if (!course.data || !target) return null;
  const pct = course.data.lesson_count ? Math.round((course.data.completed_count / course.data.lesson_count) * 100) : 0;
  const started = course.data.completed_count > 0 || !!local;

  return (
    <section className={styles.continue} aria-label={started ? 'Continuar de onde parou' : 'Comece por aqui'}>
      <div className={styles.thumb} aria-hidden="true">
        <PlayCircle {...ICON_LG} size={32} />
      </div>
      <div className={styles.continueBody}>
        <span className={styles.continueLabel}>{started ? 'Continuar' : 'Comece por aqui'}</span>
        <h2 className={styles.continueTitle}>{ptBR(target.lesson.title)}</h2>
        <span className={styles.meta}>
          {ptBR(course.data.title)}, aula {target.index} de {target.total}, {target.lesson.duration_minutes} min
        </span>
        <div className={styles.progress}>
          <span className={styles.bar} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label="Progresso da trilha">
            <span style={{ width: `${pct}%` }} />
          </span>
          <span className={styles.meta}>
            {course.data.completed_count} de {course.data.lesson_count} aulas
          </span>
        </div>
      </div>
      <Link to={`/aulas/${course.data.slug}?aula=${target.lesson.id}`} className={buttonClass({ variant: 'primary', size: 'lg' })}>
        {started ? 'Continuar aula' : 'Começar aula'}
      </Link>
    </section>
  );
}

function TrackRow({ track, summary }: { track: TrackMeta; summary: LearningState['courses'][number] | null }) {
  const detail = useApi<CourseDetail>(summary ? `/api/lms/courses/${track.slug}` : null);
  if (!track.available || !summary) {
    return (
      <li className={[styles.track, styles.unavailable].join(' ')}>
        <span className={styles.trackNumber}>{track.order}</span>
        <span className={styles.trackBody}>
          <span className={styles.trackTitle}>{track.title}</span>
          <span className={styles.trackSummary}>{track.summary}</span>
        </span>
        <span className={styles.trackProgress}>{track.level}</span>
        <span className={styles.trackStatus}>
          <Badge>Em produção</Badge>
        </span>
      </li>
    );
  }
  const status = trackStatus(summary);
  const pct = summary.lesson_count ? Math.round((summary.completed_count / summary.lesson_count) * 100) : 0;
  return (
    <li>
      <Link to={`/academia/trilhas/${track.slug}`} className={styles.track}>
        <span className={[styles.trackNumber, status === 'concluida' ? styles.trackDone : ''].join(' ')}>{track.order}</span>
        <span className={styles.trackBody}>
          <span className={styles.trackTitle}>{track.title}</span>
          <span className={styles.trackSummary}>{track.summary}</span>
        </span>
        <span className={styles.trackProgress}>
          <span>
            {summary.lesson_count} aulas{detail.data ? `, ${formatMinutes(totalMinutes(detail.data))}` : ''}, {track.level.toLowerCase()}
          </span>
          <span className={styles.progress}>
            <span className={styles.bar} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label={`Progresso em ${track.title}`}>
              <span style={{ width: `${pct}%` }} />
            </span>
            <span>
              {summary.completed_count}/{summary.lesson_count}
            </span>
          </span>
        </span>
        <span className={styles.trackStatus}>
          <Badge tone={status === 'concluida' ? 'info' : 'neutral'} outline={status === 'nao-iniciada'}>
            {TRACK_STATUS_LABEL[status]}
          </Badge>
        </span>
      </Link>
    </li>
  );
}

function LivesBlock() {
  const lives = useApi<LiveSession[]>('/api/lives');
  const upcoming = (lives.data ?? []).filter((l) => l.status !== 'ENDED').sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));
  const replays = (lives.data ?? []).filter((l) => l.status === 'ENDED').slice(0, 3);
  return (
    <div className={styles.two}>
      <section aria-labelledby="live-title">
        <h2 id="live-title" className={styles.sectionTitle}>
          Próxima live
        </h2>
        <AsyncContent state={lives} empty={<EmptyState title="Nenhuma live agendada" description="Quando uma live for marcada, ela aparece aqui." />}>
          {() =>
            upcoming[0] ? (
              <ul className={styles.list}>
                <li>
                  <span className={styles.listTitle}>
                    {upcoming[0].title} {upcoming[0].status === 'LIVE' && <Badge tone="warning">ao vivo agora</Badge>}
                  </span>
                  <span className={styles.meta}>{formatDateTime(upcoming[0].scheduled_at)} ({tzLabel(userTimeZone())})</span>
                  <span className={styles.trackSummary}>{upcoming[0].description}</span>
                </li>
              </ul>
            ) : (
              <EmptyState title="Nenhuma live agendada" description="Veja os replays enquanto isso." />
            )
          }
        </AsyncContent>
      </section>
      <section aria-labelledby="replays-title">
        <h2 id="replays-title" className={styles.sectionTitle}>
          Replays recentes
        </h2>
        {replays.length ? (
          <ul className={styles.list}>
            {replays.map((r) => (
              <li key={r.id}>
                <span className={styles.listTitle}>{r.title}</span>
                <span className={styles.meta}>{formatDateTime(r.scheduled_at)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.meta}>Sem replays ainda.</p>
        )}
        <Link to="/academia/lives" className={styles.meta}>
          Ver todas as lives
        </Link>
      </section>
    </div>
  );
}
