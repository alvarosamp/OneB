import { Link } from 'react-router-dom';
import { CheckCircle2, PlayCircle } from 'lucide-react';
import { useApi } from '../../hooks/useApi';
import { AsyncContent, EmptyState, ICON, Section, SkeletonLines, buttonClass } from '../../components/ui';
import styles from './Brasil.module.css';

const BRASIL_TRACK = 'investir-no-brasil';

interface CourseLesson {
  id: number;
  title: string;
  description: string;
  duration_minutes: number;
  completed?: boolean;
}

interface Course {
  slug: string;
  title: string;
  description: string;
  modules: { id: number; title: string; lessons: CourseLesson[] }[];
}

/** Brasil › Aulas: a trilha "Investir no Brasil" da Academia, com progresso e quizzes. */
export function AulasBrasil() {
  const course = useApi<Course>(`/api/lms/courses/${BRASIL_TRACK}`);
  return (
    <div className={styles.page}>
      <AsyncContent state={course} loading={<SkeletonLines lines={8} />} empty={<EmptyState title="Sem dados agora" />} errorTitle="Aulas indisponíveis">
        {(c) => {
          const lessons = c.modules.flatMap((m) => m.lessons);
          const next = lessons.find((l) => !l.completed) ?? lessons[0];
          const done = lessons.filter((l) => l.completed).length;
          return (
            <>
              <p className={styles.lead}>{c.description}</p>
              <div className={styles.formActions}>
                {next && (
                  <Link to={`/aulas/${c.slug}?aula=${next.id}`} className={buttonClass({ variant: 'primary' })}>
                    {done ? 'Continuar' : 'Começar a primeira aula'}
                  </Link>
                )}
                <span className={styles.meta}>
                  {done} de {lessons.length} aulas concluídas · cada aula tem checklist, exercício e quiz
                </span>
              </div>
              {c.modules.map((m) => (
                <Section key={m.id} title={m.title}>
                  <ul className={styles.lessonList}>
                    {m.lessons.map((l) => (
                      <li key={l.id}>
                        <Link to={`/aulas/${c.slug}?aula=${l.id}`}>
                          <span>
                            {l.completed ? <CheckCircle2 {...ICON} aria-label="concluída" /> : <PlayCircle {...ICON} aria-hidden />} <strong>{l.title}</strong>
                            <br />
                            <span className={styles.meta}>{l.description}</span>
                          </span>
                          <span className={styles.meta}>{l.duration_minutes} min</span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </Section>
              ))}
            </>
          );
        }}
      </AsyncContent>
    </div>
  );
}
