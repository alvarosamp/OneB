import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { CheckCircle2, ChevronDown, ChevronRight, Circle, CircleDot } from 'lucide-react';
import { useApi } from '../../hooks/useApi';
import { trackMeta } from '../../content/academia';
import { allLessons, firstIncomplete, formatMinutes, totalMinutes, TRACK_STATUS_LABEL, trackStatus } from '../../lib/academia';
import { ptBR } from '../../lib/text';
import type { CourseDetail } from '../../types';
import { AsyncContent, Badge, EmptyState, ICON, SkeletonLines } from '../../components/ui';
import { buttonClass } from '../../components/ui/buttonClass';
import styles from './Trilha.module.css';

/** Página da trilha: objetivos, pré-requisito, módulos e CTA único. */
export function Trilha() {
  const { slug = '' } = useParams();
  const course = useApi<CourseDetail>(`/api/lms/courses/${slug}`);
  const meta = trackMeta(slug);

  return (
    <div className={styles.page}>
      <Link to="/academia" className={styles.back}>
        Academia
      </Link>
      <AsyncContent
        state={course}
        loading={<SkeletonLines lines={8} />}
        empty={<EmptyState title="Trilha não encontrada" description="Ela pode ter sido renomeada. Volte para a Academia e escolha outra trilha." />}
        errorTitle="Não foi possível abrir a trilha"
      >
        {(c) => {
          const status = trackStatus(c);
          const next = firstIncomplete(c);
          return (
            <>
              <header className={styles.header}>
                <div>
                  <h1 className={styles.title}>{meta?.title ?? ptBR(c.title)}</h1>
                  <p className={styles.lead}>{meta?.summary ?? ptBR(c.description)}</p>
                  <p className={styles.meta}>
                    {c.lesson_count} aulas, {formatMinutes(totalMinutes(c))}
                    {meta ? `, ${meta.level.toLowerCase()}` : ''}. {c.completed_count} de {c.lesson_count} concluídas.
                  </p>
                </div>
                {next && (
                  <Link to={`/aulas/${c.slug}?aula=${next.id}`} className={buttonClass({ variant: 'primary', size: 'lg' })}>
                    {status === 'nao-iniciada' ? 'Começar trilha' : status === 'concluida' ? 'Rever trilha' : 'Continuar'}
                  </Link>
                )}
              </header>

              <div className={styles.columns}>
                {meta && (
                  <section aria-labelledby="goals">
                    <h2 id="goals" className={styles.sectionTitle}>
                      O que você vai aprender
                    </h2>
                    <ul className={styles.goals}>
                      {meta.goals.map((g) => (
                        <li key={g}>{g}</li>
                      ))}
                    </ul>
                    <h2 className={styles.sectionTitle}>Pré-requisito</h2>
                    <p className={styles.text}>{meta.prerequisite ?? 'Nenhum. Esta é a primeira trilha.'}</p>
                  </section>
                )}
                <section aria-labelledby="modules">
                  <h2 id="modules" className={styles.sectionTitle}>
                    Conteúdo <Badge tone={status === 'concluida' ? 'info' : 'neutral'}>{TRACK_STATUS_LABEL[status]}</Badge>
                  </h2>
                  <Modules course={c} />
                </section>
              </div>
            </>
          );
        }}
      </AsyncContent>
    </div>
  );
}

function Modules({ course }: { course: CourseDetail }) {
  const next = firstIncomplete(course);
  const [open, setOpen] = useState<Record<number, boolean>>(() => Object.fromEntries(course.modules.map((m) => [m.id, m.lessons.some((l) => l.id === next?.id) || course.modules.length <= 2])));
  const lessons = allLessons(course);
  return (
    <div className={styles.modules}>
      {course.modules.map((m, i) => {
        const done = m.lessons.filter((l) => l.completed).length;
        const isOpen = open[m.id];
        const minutes = m.lessons.reduce((s, l) => s + l.duration_minutes, 0);
        return (
          <div key={m.id} className={styles.module}>
            <button type="button" className={styles.moduleHead} aria-expanded={isOpen} onClick={() => setOpen((o) => ({ ...o, [m.id]: !o[m.id] }))}>
              {isOpen ? <ChevronDown {...ICON} aria-hidden="true" /> : <ChevronRight {...ICON} aria-hidden="true" />}
              <span className={styles.moduleTitle}>
                Módulo {i + 1}: {ptBR(m.title)}
              </span>
              <span className={styles.meta}>
                {done}/{m.lessons.length}, {formatMinutes(minutes)}
              </span>
            </button>
            {isOpen && (
              <ol className={styles.lessons}>
                {m.lessons.map((l) => {
                  const Icon = l.completed ? CheckCircle2 : l.id === next?.id ? CircleDot : Circle;
                  const n = lessons.findIndex((x) => x.id === l.id) + 1;
                  return (
                    <li key={l.id}>
                      <Link to={`/aulas/${course.slug}?aula=${l.id}`} className={styles.lesson}>
                        <Icon {...ICON} className={l.completed ? styles.done : l.id === next?.id ? styles.current : styles.todo} aria-hidden="true" />
                        <span>
                          <span className={styles.lessonTitle}>
                            {n}. {ptBR(l.title)}
                          </span>
                          <span className={styles.meta}>{ptBR(l.description)}</span>
                        </span>
                        <span className={styles.meta}>
                          {l.duration_minutes} min
                          <span className="sr-only">{l.completed ? ', concluída' : l.id === next?.id ? ', próxima aula' : ', não iniciada'}</span>
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ol>
            )}
          </div>
        );
      })}
    </div>
  );
}
