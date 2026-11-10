import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { VideoEmbed } from '../components/VideoEmbed';
import { useToast } from '../context/ToastContext';
import type { CourseDetail, LessonSummary } from '../types';

type LessonTab = 'resumo' | 'checklist' | 'exercicio' | 'simulador' | 'anotacoes';
type Direction = 'LONG' | 'SHORT';

function CourseSimulator() {
  const [symbol, setSymbol] = useState('NASDAQ');
  const [direction, setDirection] = useState<Direction>('LONG');
  const [capital, setCapital] = useState(10000);
  const [riskPct, setRiskPct] = useState(1);
  const [entry, setEntry] = useState(180);
  const [stop, setStop] = useState(174);
  const [target, setTarget] = useState(194);

  const riskUsd = capital * (riskPct / 100);
  const unitRisk = Math.abs(entry - stop);
  const unitReward = Math.abs(target - entry);
  const quantity = unitRisk > 0 ? Math.floor(riskUsd / unitRisk) : 0;
  const plannedRisk = quantity * unitRisk;
  const plannedReward = quantity * unitReward;
  const rr = unitRisk > 0 ? unitReward / unitRisk : 0;
  const validStructure = direction === 'LONG' ? stop < entry && target > entry : stop > entry && target < entry;
  const score = [validStructure, rr >= 2, riskPct <= 2, quantity > 0].filter(Boolean).length;

  return (
    <div className="simulator-panel simulator-panel-pro">
      <div className="simulator-header">
        <div>
          <p className="eyebrow">Simulador integrado</p>
          <h3>Planeje a operacao antes de registrar o setup</h3>
        </div>
        <div className={`simulator-score ${score >= 3 ? 'good' : 'warn'}`}>{score}/4</div>
      </div>

      <div className="simulator-controls">
        <label>
          Ativo
          <select value={symbol} onChange={(event) => setSymbol(event.target.value)}>
            <option value="NASDAQ">NASDAQ</option>
            <option value="SPY">SPY</option>
            <option value="AAPL">AAPL</option>
            <option value="MSFT">MSFT</option>
          </select>
        </label>
        <label>
          Direcao
          <select value={direction} onChange={(event) => setDirection(event.target.value as Direction)}>
            <option value="LONG">Compra</option>
            <option value="SHORT">Venda</option>
          </select>
        </label>
        <label>
          Capital
          <input type="number" min="100" value={capital} onChange={(event) => setCapital(Number(event.target.value))} />
        </label>
        <label>
          Risco %
          <input type="number" min="0.1" step="0.1" value={riskPct} onChange={(event) => setRiskPct(Number(event.target.value))} />
        </label>
        <label>
          Entrada
          <input type="number" step="0.01" value={entry} onChange={(event) => setEntry(Number(event.target.value))} />
        </label>
        <label>
          Stop
          <input type="number" step="0.01" value={stop} onChange={(event) => setStop(Number(event.target.value))} />
        </label>
        <label>
          Alvo
          <input type="number" step="0.01" value={target} onChange={(event) => setTarget(Number(event.target.value))} />
        </label>
      </div>

      <div className="simulator-output">
        <div>
          <span>Quantidade</span>
          <strong>{quantity}</strong>
        </div>
        <div>
          <span>Risco planejado</span>
          <strong>US$ {plannedRisk.toFixed(2)}</strong>
        </div>
        <div>
          <span>Retorno potencial</span>
          <strong>US$ {plannedReward.toFixed(2)}</strong>
        </div>
        <div>
          <span>Risco/retorno</span>
          <strong>{rr.toFixed(2)}R</strong>
        </div>
      </div>

      <div className="simulator-feedback-grid">
        <article>
          <strong>{validStructure ? 'Estrutura coerente.' : 'Estrutura invalida.'}</strong>
          <p className="muted">A direcao precisa combinar entrada, stop e alvo antes de qualquer revisao.</p>
        </article>
        <article>
          <strong>{rr >= 2 ? 'Risco/retorno adequado.' : 'Risco/retorno fraco.'}</strong>
          <p className="muted">Quando a relacao fica ruim, a melhor resposta pode ser NO_TRADE.</p>
        </article>
        <article>
          <strong>{riskPct <= 2 ? 'Risco dentro do limite.' : 'Risco agressivo.'}</strong>
          <p className="muted">Para aluno piloto, use tamanho pequeno e revise o resultado depois.</p>
        </article>
      </div>
    </div>
  );
}

export function CursoDetalhe() {
  const { slug } = useParams<{ slug: string }>();
  const toast = useToast();
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedLessonId, setSelectedLessonId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<LessonTab>('resumo');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!slug) return;
    api
      .get<CourseDetail>(`/api/lms/courses/${slug}`)
      .then((data) => {
        setCourse(data);
        const firstIncomplete = data.modules.flatMap((module) => module.lessons).find((lesson) => !lesson.completed);
        const firstLesson = data.modules[0]?.lessons[0];
        setSelectedLessonId((firstIncomplete ?? firstLesson)?.id ?? null);
      })
      .catch(() => setError('Nao foi possivel carregar essa trilha.'));
  }, [slug]);

  const allLessons = useMemo(() => course?.modules.flatMap((module) => module.lessons) ?? [], [course]);
  const selectedLesson = allLessons.find((lesson) => lesson.id === selectedLessonId) ?? null;
  const progressPct = course && course.lesson_count > 0 ? Math.round((course.completed_count / course.lesson_count) * 100) : 0;

  async function toggleComplete(lesson: LessonSummary) {
    if (!course) return;
    setSaving(true);
    try {
      if (lesson.completed) {
        await api.delete(`/api/lms/lessons/${lesson.id}/complete`);
      } else {
        await api.post(`/api/lms/lessons/${lesson.id}/complete`);
      }
      setCourse({
        ...course,
        completed_count: course.completed_count + (lesson.completed ? -1 : 1),
        modules: course.modules.map((module) => ({
          ...module,
          lessons: module.lessons.map((item) => (item.id === lesson.id ? { ...item, completed: !item.completed } : item)),
        })),
      });
    } catch {
      toast('Erro ao atualizar progresso da aula', 'error');
    } finally {
      setSaving(false);
    }
  }

  if (error) {
    return (
      <div className="container">
        <p className="form-error">{error}</p>
        <Link className="btn-link" to="/aprendizado">
          Voltar para Escola
        </Link>
      </div>
    );
  }

  if (!course) {
    return (
      <div className="container">
        <p className="muted">Carregando...</p>
      </div>
    );
  }

  return (
    <div className="container course-detail-container course-premium-container">
      <div className="course-detail-hero">
        <div>
          <p className="eyebrow">Escola OneB</p>
          <h1>{course.title}</h1>
          <p className="muted">{course.description}</p>
        </div>
        <div className="course-detail-progress">
          <span>{progressPct}% concluido</span>
          <div className="course-progress-bar">
            <div className="course-progress-fill" style={{ width: `${progressPct}%` }} />
          </div>
          <small className="muted">Proximo passo: concluir a aula e praticar no simulador.</small>
          <Link className="btn-link" to="/aprendizado">
            Todas as trilhas
          </Link>
        </div>
      </div>

      <div className="course-gamification-row">
        <article>
          <span>Aulas</span>
          <strong>
            {course.completed_count}/{course.lesson_count}
          </strong>
        </article>
        <article>
          <span>Certificado</span>
          <strong>{progressPct >= 100 ? 'Aulas ok' : 'Em progresso'}</strong>
        </article>
        <article>
          <span>Pratica</span>
          <strong>Simulador</strong>
        </article>
      </div>

      <div className="course-shell">
        <div className="panel course-player">
          {selectedLesson ? (
            <>
              {selectedLesson.video_url ? (
                <VideoEmbed url={selectedLesson.video_url} title={selectedLesson.title} />
              ) : (
                <div className="course-video-placeholder">
                  <span>▶</span>
                  <p className="muted">Video/link em breve · {selectedLesson.duration_minutes} min</p>
                </div>
              )}

              <div className="lesson-heading">
                <div>
                  <p className="eyebrow">Aula selecionada</p>
                  <h2>{selectedLesson.title}</h2>
                  <p className="muted">{selectedLesson.description}</p>
                </div>
                <div className="lesson-heading-actions">
                  <button type="button" className="btn-secondary" onClick={() => setActiveTab('simulador')}>
                    Praticar no simulador
                  </button>
                  <button
                    type="button"
                    className={selectedLesson.completed ? 'btn-secondary' : 'auth-submit'}
                    disabled={saving}
                    onClick={() => toggleComplete(selectedLesson)}
                  >
                    {selectedLesson.completed ? 'Marcar como nao concluida' : 'Marcar como concluida'}
                  </button>
                </div>
              </div>

              <div className="lesson-tabs" role="tablist" aria-label="Material da aula">
                {[
                  ['resumo', 'Resumo'],
                  ['checklist', 'Checklist'],
                  ['exercicio', 'Exercicio pratico'],
                  ['simulador', 'Simulador'],
                  ['anotacoes', 'Anotacoes'],
                ].map(([key, label]) => (
                  <button key={key} className={activeTab === key ? 'active' : ''} onClick={() => setActiveTab(key as LessonTab)}>
                    {label}
                  </button>
                ))}
              </div>

              {activeTab === 'resumo' && (
                <div className="lesson-tab-panel">
                  <h3>Plano desta aula</h3>
                  <p className="muted">{selectedLesson.summary}</p>
                  <div className="lesson-action-grid">
                    <span>Entender</span>
                    <span>Aplicar</span>
                    <span>Revisar</span>
                  </div>
                </div>
              )}

              {activeTab === 'checklist' && (
                <div className="lesson-tab-panel">
                  <h3>Checklist de execucao</h3>
                  <ul className="lesson-checklist">
                    {selectedLesson.checklist.map((item) => (
                      <li key={item}>
                        <span>✓</span>
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {activeTab === 'exercicio' && (
                <div className="lesson-tab-panel">
                  <h3>Exercicio pratico</h3>
                  <p className="muted">{selectedLesson.exercise}</p>
                  <div className="exercise-grid">
                    <label>
                      Tese da operacao
                      <textarea placeholder="Ex: rompimento com pullback e volume crescente..." />
                    </label>
                    <label>
                      Invalidacao
                      <textarea placeholder="Ex: perda da media ou fechamento abaixo do suporte..." />
                    </label>
                  </div>
                </div>
              )}

              {activeTab === 'simulador' && <CourseSimulator />}

              {activeTab === 'anotacoes' && (
                <div className="lesson-tab-panel">
                  <h3>Anotacoes da aula</h3>
                  <textarea
                    className="lesson-notes"
                    value={notes}
                    onChange={(event) => setNotes(event.target.value)}
                    placeholder="Escreva suas regras, duvidas e pontos de atencao..."
                  />
                </div>
              )}
            </>
          ) : (
            <p className="muted">Nenhuma aula disponivel ainda.</p>
          )}
        </div>

        <aside className="panel course-modules">
          <div className="panel-title">
            <h2>Conteudo</h2>
            <span className="muted">
              {course.completed_count}/{course.lesson_count}
            </span>
          </div>
          {course.modules.map((module) => {
            const moduleCompleted = module.lessons.filter((lesson) => lesson.completed).length;
            const modulePct = module.lessons.length > 0 ? Math.round((moduleCompleted / module.lessons.length) * 100) : 0;
            return (
              <div key={module.id} className="course-module-group">
                <p className="sidebar-group-label">
                  {module.title} · {modulePct}%
                </p>
                <div className="course-progress-bar module-progress">
                  <div className="course-progress-fill" style={{ width: `${modulePct}%` }} />
                </div>
                {module.lessons.map((lesson) => (
                  <button
                    key={lesson.id}
                    type="button"
                    className={`course-lesson-item ${lesson.id === selectedLessonId ? 'active' : ''}`}
                    onClick={() => {
                      setSelectedLessonId(lesson.id);
                      setActiveTab('resumo');
                    }}
                  >
                    <span className={`course-lesson-check ${lesson.completed ? 'done' : ''}`}>{lesson.completed ? '✓' : ''}</span>
                    <span>
                      {lesson.title}
                      <small className="muted block-text">
                        {lesson.duration_minutes} min{lesson.required ? ' · obrigatoria' : ''}
                      </small>
                    </span>
                  </button>
                ))}
              </div>
            );
          })}
        </aside>
      </div>
    </div>
  );
}
