import { useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, ChevronDown, ChevronRight, Circle, CircleDot } from 'lucide-react';
import type { CourseDetail } from '../../types';
import { ptBR } from '../../lib/text';
import { ICON } from '../ui';
import styles from './Player.module.css';

/** Lista lateral de aulas: módulos colapsáveis, status por ícone e aula atual. */
export function LessonList({ course, currentId, onNavigate }: { course: CourseDetail; currentId: number; onNavigate?: () => void }) {
  const [open, setOpen] = useState<Record<number, boolean>>(() =>
    Object.fromEntries(course.modules.map((m) => [m.id, m.lessons.some((l) => l.id === currentId)])),
  );
  return (
    <nav aria-label="Conteúdo da trilha" className={styles.lessonNav}>
      {course.modules.map((m, i) => {
        const done = m.lessons.filter((l) => l.completed).length;
        const isOpen = open[m.id] ?? false;
        return (
          <div key={m.id} className={styles.navModule}>
            <button type="button" className={styles.navModuleHead} aria-expanded={isOpen} onClick={() => setOpen((o) => ({ ...o, [m.id]: !isOpen }))}>
              {isOpen ? <ChevronDown {...ICON} aria-hidden="true" /> : <ChevronRight {...ICON} aria-hidden="true" />}
              <span>
                Módulo {i + 1}
                <span className={styles.navModuleTitle}>{ptBR(m.title)}</span>
              </span>
              <span className="num muted">
                {done}/{m.lessons.length}
              </span>
            </button>
            {isOpen && (
              <ol className={styles.navLessons}>
                {m.lessons.map((l) => {
                  const current = l.id === currentId;
                  const Icon = l.completed ? CheckCircle2 : current ? CircleDot : Circle;
                  return (
                    <li key={l.id}>
                      <Link
                        to={`/aulas/${course.slug}?aula=${l.id}`}
                        className={[styles.navLesson, current ? styles.navCurrent : ''].join(' ')}
                        aria-current={current ? 'page' : undefined}
                        onClick={onNavigate}
                      >
                        <Icon {...ICON} className={l.completed ? styles.iconDone : current ? styles.iconCurrent : styles.iconTodo} aria-hidden="true" />
                        <span>{ptBR(l.title)}</span>
                        <span className="num muted">{l.duration_minutes} min</span>
                        <span className="sr-only">{l.completed ? 'concluída' : current ? 'aula atual' : 'não iniciada'}</span>
                      </Link>
                    </li>
                  );
                })}
              </ol>
            )}
          </div>
        );
      })}
    </nav>
  );
}
