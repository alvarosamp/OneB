import { useEffect, useId, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ArrowLeft, ListOrdered } from 'lucide-react';
import { api } from '../../api/client';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../context/ToastContext';
import { lessonExtra } from '../../content/academia';
import { allLessons, exercisePassed, findLesson, firstIncomplete, isFileVideo, markExercisePassed, rememberLesson } from '../../lib/academia';
import { ptBR } from '../../lib/text';
import type { CourseDetail, LessonSummary } from '../../types';
import { AsyncContent, Button, EmptyState, ICON, Modal, SkeletonLines, TabPanel, Tabs } from '../../components/ui';
import { buttonClass } from '../../components/ui/buttonClass';
import { VideoArea } from '../../components/academia/VideoArea';
import { Quiz } from '../../components/academia/Quiz';
import { OpenExercise } from '../../components/academia/OpenExercise';
import { Practice } from '../../components/academia/Practice';
import { Notes } from '../../components/academia/Notes';
import { LessonList } from '../../components/academia/LessonList';
import styles from '../../components/academia/Player.module.css';

type Tab = 'resumo' | 'checklist' | 'exercicio' | 'pratica' | 'anotacoes';

/** Player da aula (/aulas/:slug?aula=<id ou título>). */
export function Aula() {
  const { slug = '' } = useParams();
  const course = useApi<CourseDetail>(`/api/lms/courses/${slug}`);
  return (
    <AsyncContent
      state={course}
      loading={<SkeletonLines lines={10} />}
      empty={
        <EmptyState
          title="Trilha não encontrada"
          description="Volte para a Academia e escolha uma trilha."
          action={
            <Link to="/academia" className={buttonClass({ size: 'sm' })}>
              Ir para a Academia
            </Link>
          }
        />
      }
      errorTitle="Não foi possível abrir a aula"
    >
      {(c) => <Player course={c} onCourseChange={course.mutate} />}
    </AsyncContent>
  );
}

function Player({ course, onCourseChange }: { course: CourseDetail; onCourseChange: (c: CourseDetail) => void }) {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const idBase = useId();
  const lessons = useMemo(() => allLessons(course), [course]);
  const lesson = findLesson(course, params.get('aula')) ?? firstIncomplete(course);
  const index = lesson ? lessons.findIndex((l) => l.id === lesson.id) : -1;
  const prev = index > 0 ? lessons[index - 1] : null;
  const next = index >= 0 && index < lessons.length - 1 ? lessons[index + 1] : null;
  const extra = lesson ? lessonExtra(lesson.title) : undefined;

  const [tab, setTab] = useState<Tab>('resumo');
  const [passed, setPassed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [drawer, setDrawer] = useState(false);

  useEffect(() => {
    if (!lesson) return;
    rememberLesson(course.slug, lesson.id);
    setPassed(exercisePassed(lesson.id));
    setTab('resumo');
    window.scrollTo({ top: 0 });
  }, [course.slug, lesson?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!lesson) return <EmptyState title="Esta trilha ainda não tem aulas" description="Volte mais tarde." />;

  const canComplete = lesson.completed || passed;

  function goTo(l: LessonSummary | null) {
    if (!l) return;
    setParams({ aula: String(l.id) });
  }

  function onPassed() {
    markExercisePassed(lesson!.id);
    setPassed(true);
  }

  async function setCompleted(done: boolean) {
    setSaving(true);
    try {
      if (done) await api.post(`/api/lms/lessons/${lesson!.id}/complete`);
      else await api.delete(`/api/lms/lessons/${lesson!.id}/complete`);
      onCourseChange({
        ...course,
        completed_count: course.completed_count + (done ? 1 : -1),
        modules: course.modules.map((m) => ({ ...m, lessons: m.lessons.map((l) => (l.id === lesson!.id ? { ...l, completed: done } : l)) })),
      });
      toast(done ? 'Aula concluída' : 'Aula marcada como não concluída', 'success');
      if (done) {
        if (next) goTo(next);
        else navigate(`/academia/trilhas/${course.slug}`);
      }
    } catch (err) {
      toast(err instanceof Error ? `Não foi possível salvar o progresso: ${err.message}` : 'Não foi possível salvar o progresso', 'error');
    } finally {
      setSaving(false);
    }
  }

  const tabs: { value: Tab; label: string }[] = [
    { value: 'resumo', label: 'Resumo' },
    { value: 'checklist', label: 'Checklist' },
    { value: 'exercicio', label: passed || lesson.completed ? 'Exercício (feito)' : 'Exercício' },
    { value: 'pratica', label: 'Praticar no gráfico' },
    { value: 'anotacoes', label: 'Anotações' },
  ];
  const doneCount = course.modules.flatMap((m) => m.lessons).filter((l) => l.completed).length;

  return (
    <div className={styles.layout}>
      <div className={styles.main}>
        <div className={styles.footerRight}>
          <Link to={`/academia/trilhas/${course.slug}`} className={styles.meta}>
            {ptBR(course.title)}
          </Link>
          <Button size="sm" variant="ghost" className={styles.drawerButton} icon={<ListOrdered {...ICON} />} onClick={() => setDrawer(true)}>
            Conteúdo {doneCount}/{lessons.length}
          </Button>
        </div>

        <VideoArea url={lesson.video_url} title={ptBR(lesson.title)} lessonId={lesson.id} />

        <header className={styles.lessonHeader}>
          <h1 className={styles.lessonTitle}>{ptBR(lesson.title)}</h1>
          <span className={styles.meta}>
            {ptBR(lessons[index]?.moduleTitle ?? '')}, aula {index + 1} de {lessons.length}, {lesson.duration_minutes} min
            {lesson.completed ? ', concluída' : ''}
          </span>
        </header>

        <Tabs items={tabs} value={tab} onChange={setTab} label="Material da aula" idBase={idBase} />
        <TabPanel idBase={idBase} value={tab} className={styles.panel}>
          {tab === 'resumo' && (
            <div className={styles.quiz}>
              <p className={styles.reading}>{ptBR(lesson.summary || lesson.description)}</p>
              {lesson.description && lesson.summary && <p className={styles.meta}>{ptBR(lesson.description)}</p>}
            </div>
          )}
          {tab === 'checklist' && (
            <ul className={styles.checklist}>
              {lesson.checklist.map((item) => (
                <li key={item}>
                  <label>
                    <input type="checkbox" />
                    <span>{ptBR(item)}</span>
                  </label>
                </li>
              ))}
            </ul>
          )}
          {tab === 'exercicio' &&
            (extra?.quiz.length ? (
              <Quiz key={lesson.id} questions={extra.quiz} onPassed={onPassed} passed={passed || lesson.completed} />
            ) : (
              <OpenExercise key={lesson.id} prompt={lesson.exercise} onPassed={onPassed} passed={passed || lesson.completed} />
            ))}
          {tab === 'pratica' && <Practice symbol={extra?.practiceSymbol ?? 'QQQ'} hint={extra?.practiceHint ?? ptBR(lesson.exercise)} />}
          {tab === 'anotacoes' && <Notes lessonId={lesson.id} />}
        </TabPanel>

        <div className={styles.footerNav}>
          <Button variant="ghost" icon={<ArrowLeft {...ICON} />} disabled={!prev} onClick={() => goTo(prev)}>
            Aula anterior
          </Button>
          <div className={styles.footerRight}>
            {!canComplete && (
              <>
                <span className={styles.gateNote}>Faça o exercício para concluir.</span>
                {tab !== 'exercicio' && (
                  <Button size="sm" variant="ghost" onClick={() => setTab('exercicio')}>
                    Abrir exercício
                  </Button>
                )}
              </>
            )}
            {lesson.completed ? (
              <>
                <Button size="sm" variant="ghost" loading={saving} onClick={() => setCompleted(false)}>
                  Marcar como não concluída
                </Button>
                {next && (
                  <Button variant="primary" onClick={() => goTo(next)}>
                    Ir para a próxima aula
                  </Button>
                )}
              </>
            ) : (
              <Button variant="primary" disabled={!canComplete} loading={saving} onClick={() => setCompleted(true)}>
                {next ? 'Concluir e ir para a próxima' : 'Concluir trilha'}
              </Button>
            )}
          </div>
        </div>
        {isFileVideo(lesson.video_url) && <p className={styles.shortcuts}>
          Atalhos do vídeo: <kbd>Espaço</kbd> reproduz ou pausa, <kbd>←</kbd> <kbd>→</kbd> voltam ou avançam 5 s.
        </p>}
      </div>

      <aside className={styles.aside}>
        <h2 className={styles.asideTitle}>
          Conteúdo
          <span className="num muted">
            {doneCount}/{lessons.length}
          </span>
        </h2>
        <LessonList course={course} currentId={lesson.id} />
      </aside>

      <Modal open={drawer} onClose={() => setDrawer(false)} title={`Conteúdo (${doneCount}/${lessons.length})`} variant="drawer">
        <LessonList course={course} currentId={lesson.id} onNavigate={() => setDrawer(false)} />
      </Modal>
    </div>
  );
}
