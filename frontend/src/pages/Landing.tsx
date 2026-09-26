import type { CSSProperties } from 'react';
import { ArrowUpRight, BookOpen, Radar, ShieldCheck, type LucideIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { MarketingLayout } from '../components/marketing/MarketingLayout';

const journey = [
  { step: '01', title: 'Aprenda', subtitle: 'Base antes da decisão', description: 'Aulas curtas, checklists e exercícios para transformar conteúdo em processo.', detail: 'Trilhas práticas', to: '/aulas', icon: BookOpen },
  { step: '02', title: 'Acompanhe', subtitle: 'Mercado sem ruído', description: 'Watchlist, alertas e contexto reunidos para mostrar o que merece atenção.', detail: 'Dados e alertas', to: '/aplicacoes', icon: Radar },
  { step: '03', title: 'Decida', subtitle: 'Risco antes da entrada', description: 'Evidências, invalidação e NO_TRADE quando não houver informação suficiente.', detail: 'Decisão protegida', to: '/estrategias', icon: ShieldCheck },
];

function TerminalHeroVisual() {
  return (
    <div className="oneb-terminal-visual" aria-label="Prévia visual das ferramentas OneB">
      <div className="terminal-glass-window terminal-window-main">
        <header><span>OneB</span><strong>NASDAQ</strong></header>
        <div className="terminal-candle-board">
          {[48, 58, 46, 72, 64, 86, 74, 94, 82].map((height, index) => (
            <i key={`${height}-${index}`} style={{ height: `${height}%` }} />
          ))}
        </div>
        <footer><span>Regime BULL</span><span>RSI 58.4</span><span>Risco 1.2%</span></footer>
      </div>
      <div className="terminal-glass-window terminal-window-side">
        <span>Decisão</span>
        <strong>NO_TRADE</strong>
        <small>Dados fracos ou risco alto são motivos para esperar.</small>
      </div>
      <div className="metal-candles" aria-hidden="true">
        {[0, 1, 2, 3, 4].map((item) => (
          <span key={item} style={{ '--i': item } as CSSProperties}><i /></span>
        ))}
      </div>
    </div>
  );
}

function JourneyCard({ item }: { item: { step: string; title: string; subtitle: string; description: string; detail: string; to: string; icon: LucideIcon } }) {
  const Icon = item.icon;
  return (
    <article className="oneb-journey-card">
      <div className="oneb-journey-top"><span>{item.step}</span><Icon size={22} aria-hidden="true" /></div>
      <p className="oneb-eyebrow">{item.subtitle}</p>
      <h3>{item.title}</h3>
      <p>{item.description}</p>
      <div className="oneb-journey-footer">
        <small>{item.detail}</small>
        <Link to={item.to} aria-label={`Conhecer ${item.title}`}><ArrowUpRight size={18} /></Link>
      </div>
    </article>
  );
}

export function Landing() {
  return (
    <MarketingLayout>
      <main>
        <section className="oneb-hero oneb-section oneb-hero-redesign">
          <div className="oneb-hero-copy oneb-reveal">
            <p className="oneb-eyebrow">Aprendizado e ferramentas</p>
            <h1>Aprenda mercado.<br />Pratique com dados.<br />Decida com método.</h1>
            <p>A OneB conecta aprendizado, dados e gestão de risco para você construir decisões mais conscientes.</p>
            <div className="oneb-hero-actions">
              <a href="#ecossistema" className="oneb-primary">Conhecer a OneB</a>
              <Link to="/login" className="oneb-secondary">Entrar na plataforma</Link>
            </div>
          </div>
          <TerminalHeroVisual />
        </section>

        <section className="oneb-section ecosystem-section" id="ecossistema">
          <div className="oneb-section-heading split">
            <div><p className="oneb-eyebrow">Uma rotina completa</p><h2>Da dúvida a uma decisão mais consciente.</h2></div>
            <p>Menos telas soltas. Um caminho claro para aprender, observar o mercado e avaliar o risco antes de agir.</p>
          </div>
          <div className="oneb-journey-grid">
            {journey.map((item) => <JourneyCard key={item.step} item={item} />)}
          </div>
          <div className="oneb-journey-summary">
            <div><span>Um único fluxo</span><strong>Estudo → contexto → decisão</strong><p>A plataforma acompanha a rotina. Você continua no controle.</p></div>
            <Link to="/cadastro" className="oneb-secondary">Começar agora</Link>
          </div>
        </section>

        <section className="oneb-final-cta oneb-section final-cta-redesign">
          <div>
            <p className="oneb-eyebrow">Seu próximo passo</p>
            <h2>Construa método antes de buscar sinais.</h2>
            <p>Comece aprendendo. Use os dados para praticar. Decida sempre com risco definido.</p>
          </div>
          <div className="oneb-final-actions">
            <Link to="/cadastro" className="oneb-primary">Criar conta</Link>
            <Link to="/login" className="oneb-secondary">Já tenho conta</Link>
          </div>
        </section>
      </main>
    </MarketingLayout>
  );
}
