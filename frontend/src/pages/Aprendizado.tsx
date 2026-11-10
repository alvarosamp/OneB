import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { useToast } from '../context/ToastContext';
import type { CertificateStatus, CourseSummary, LearningRecommendation, LearningState } from '../types';

const FILTERS = ['Todos', 'Iniciante', 'Intermediario', 'Avancado', 'Analise tecnica', 'Risco', 'Estrategia', 'IA'];

function courseTheme(title: string) {
  const normalized = title.toLowerCase();
  if (normalized.includes('risco') || normalized.includes('psicologia')) return 'Risco';
  if (normalized.includes('tecnica') || normalized.includes('price')) return 'Tecnica';
  if (normalized.includes('fundamento')) return 'Base';
  return 'Metodo';
}

function courseLevel(title: string, order: number) {
  const normalized = title.toLowerCase();
  if (normalized.includes('avanc')) return 'Avancado';
  if (normalized.includes('risco')) return 'Essencial';
  if (order <= 1) return 'Iniciante';
  return 'Intermediario';
}

export function Aprendizado() {
  const toast = useToast();
  const [courses, setCourses] = useState<CourseSummary[]>([]);
  const [recommendation, setRecommendation] = useState<LearningRecommendation | null>(null);
  const [certificate, setCertificate] = useState<CertificateStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api
      .get<LearningState>('/api/lms/learning-state')
      .then((data) => {
        if (!cancelled) {
          setCourses(data.courses);
          setRecommendation(data.recommendation);
          setCertificate(data.certificate);
        }
      })
      .catch(() => toast('Erro ao carregar trilhas da Escola', 'error'))
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [toast]);

  const totals = useMemo(
    () =>
      courses.reduce(
        (acc, course) => ({
          lessons: acc.lessons + course.lesson_count,
          completed: acc.completed + course.completed_count,
        }),
        { lessons: 0, completed: 0 },
      ),
    [courses],
  );
  const progressPct = totals.lessons > 0 ? Math.round((totals.completed / totals.lessons) * 100) : 0;
  const nextCourse =
    (recommendation ? courses.find((course) => course.slug === recommendation.course_slug) : null) ??
    courses.find((course) => course.completed_count < course.lesson_count) ??
    courses[0] ??
    null;

  return (
    <div className="container command-center">
      <section className="command-hero">
        <div>
          <p className="eyebrow">Escola</p>
          <h1>Curso, estrategia e pratica conectados ao seu terminal.</h1>
          <p className="muted">
            Continue aulas, acompanhe progresso e leve cada conceito para simulacao, watchlist e revisao de risco.
          </p>
        </div>
        <div className="command-score">
          <span>Progresso geral</span>
          <strong>{progressPct}%</strong>
          <small className="muted">
            {totals.completed} de {totals.lessons} aulas concluidas
          </small>
        </div>
      </section>

      <section className="oneb-learning-summary command-learning-summary">
        <article>
          <span>Continue</span>
          <strong>{recommendation?.lesson_title ?? nextCourse?.title ?? 'Primeira trilha'}</strong>
          <p>{recommendation?.reason ?? nextCourse?.description ?? 'Comece pela base antes de abrir a mesa.'}</p>
        </article>
        <article>
          <span>Certificado</span>
          <strong>{certificate?.eligible ? 'Liberado' : `${certificate?.progress_pct ?? 0}%`}</strong>
          <p>{certificate?.next_requirement ?? 'Conclua aulas obrigatorias e simulacoes.'}</p>
        </article>
        <article>
          <span>Proximo passo</span>
          <strong>{recommendation ? 'Corrigir lacuna' : nextCourse ? 'Abrir aula' : 'Cadastrar curso'}</strong>
          <p>
            {certificate
              ? `${certificate.completed_simulations}/${certificate.required_simulations} simulacoes praticas`
              : 'Estude, marque progresso e pratique no simulador.'}
          </p>
        </article>
      </section>

      {recommendation && (
        <section className="oneb-continue">
          <div>
            <p className="oneb-eyebrow">Recomendacao da Escola</p>
            <h2>{recommendation.lesson_title}</h2>
            <p>{recommendation.reason}</p>
          </div>
          <Link to={`/aulas/${recommendation.course_slug}`} className="oneb-primary">
            Abrir aula recomendada
          </Link>
        </section>
      )}

      <div className="oneb-filters command-filters">
        {FILTERS.map((filter) => (
          <button key={filter} className={filter === 'Todos' ? 'active' : ''} type="button">
            {filter}
          </button>
        ))}
      </div>

      <section className="oneb-course-track-grid command-course-grid">
        {loading && <p className="muted">Carregando trilhas...</p>}
        {!loading && courses.length === 0 && (
          <p className="muted">Nenhuma trilha publicada ainda. Rode a carga inicial do LMS para liberar a Escola.</p>
        )}
        {courses.map((course) => {
          const progress = course.lesson_count > 0 ? Math.round((course.completed_count / course.lesson_count) * 100) : 0;
          const status = progress === 100 ? 'Concluido' : progress > 0 ? 'Em andamento' : 'Liberado';
          return (
          <article key={course.id} className="oneb-course-track">
            <div className="course-track-thumb">
              <span>{courseTheme(course.title)}</span>
            </div>
            <div className="course-track-body">
              <div className="course-track-top">
                <span>{courseLevel(course.title, course.order)}</span>
                <small>{status}</small>
              </div>
              <h2>{course.title}</h2>
              <p>{course.description}</p>
              <div className="course-track-progress">
                <i style={{ width: `${progress}%` }} />
              </div>
              <Link to={`/aulas/${course.slug}`}>
                Abrir trilha
              </Link>
            </div>
          </article>
          );
        })}
      </section>
    </div>
  );
}
