import { useMemo, useState } from 'react';
import { ArrowRight, BookOpenCheck, CheckCircle2, Route } from 'lucide-react';
import { Link } from 'react-router-dom';
import { MarketingLayout } from '../components/marketing/MarketingLayout';
import { courseTracks } from '../content/onebMarketing';

const filters = ['Todas', 'Iniciante', 'Intermediário', 'Avançado', 'Técnica', 'Risco', 'Método', 'IA'];

function normalize(value: string) {
  return value.toLocaleLowerCase('pt-BR').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

export function Aulas() {
  const [activeFilter, setActiveFilter] = useState('Todas');
  const visibleTracks = useMemo(() => {
    if (activeFilter === 'Todas') return courseTracks;
    const query = normalize(activeFilter);
    return courseTracks.filter((track) => normalize(`${track.level} ${track.theme} ${track.title}`).includes(query));
  }, [activeFilter]);

  return (
    <MarketingLayout>
      <main className="oneb-page oneb-section oneb-learning-page">
        <section className="oneb-page-hero">
          <div>
            <p className="oneb-eyebrow">Aprendizado OneB</p>
            <h1>Aprenda o que você vai usar no mercado.</h1>
            <p>Conteúdo organizado para sair da teoria, praticar com contexto e construir um processo que você consiga repetir.</p>
            <div className="oneb-hero-actions">
              <Link to="/cadastro" className="oneb-primary">Começar a aprender</Link>
              <a href="#trilhas" className="oneb-secondary">Explorar trilhas</a>
            </div>
          </div>
          <aside className="oneb-learning-method">
            <p className="oneb-eyebrow">Como você evolui</p>
            <div><BookOpenCheck size={20} /><span><b>Entenda</b><small>Conceitos sem atalhos.</small></span></div>
            <div><Route size={20} /><span><b>Pratique</b><small>Checklists e cenários guiados.</small></span></div>
            <div><CheckCircle2 size={20} /><span><b>Revise</b><small>Decisões, erros e progresso real.</small></span></div>
          </aside>
        </section>

        <section className="oneb-curriculum-intro" id="trilhas">
          <div><p className="oneb-eyebrow">Trilhas de aprendizado</p><h2>Uma base sólida, construída na ordem certa.</h2></div>
          <p>Escolha um tema para conhecer a proposta. Seu progresso verdadeiro aparece somente depois de entrar.</p>
        </section>

        <div className="oneb-filters" aria-label="Filtrar trilhas">
          {filters.map((filter) => (
            <button key={filter} className={filter === activeFilter ? 'active' : ''} type="button" onClick={() => setActiveFilter(filter)}>
              {filter}
            </button>
          ))}
        </div>

        <div className="oneb-course-track-grid">
          {visibleTracks.map((track) => (
            <article key={track.title} className={`oneb-course-track ${track.status === 'Plano avançado' ? 'locked' : ''}`}>
              <div className="course-track-thumb"><span>{track.theme}</span></div>
              <div className="course-track-body">
                <div className="course-track-top"><span>{track.level}</span><small>{track.status}</small></div>
                <h2>{track.title}</h2>
                <p>Aula, checklist e prática para aplicar o conceito em um cenário controlado.</p>
                <Link to={track.status === 'Plano avançado' ? '/planos' : '/cadastro'}>
                  {track.status === 'Plano avançado' ? 'Conhecer o plano' : <>Conhecer trilha <ArrowRight size={16} /></>}
                </Link>
              </div>
            </article>
          ))}
          {visibleTracks.length === 0 && <p className="oneb-empty-filter">Nenhuma trilha corresponde a este filtro.</p>}
        </div>
      </main>
    </MarketingLayout>
  );
}
