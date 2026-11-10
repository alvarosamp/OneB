import { CheckCircle2 } from 'lucide-react';
import { MarketingLayout } from '../components/marketing/MarketingLayout';
import { StrategyCard } from '../components/marketing/StrategyCard';
import { strategies } from '../content/onebMarketing';

const principles = ['Contexto antes do gatilho', 'Invalidação antes da entrada', 'Risco definido antes do retorno'];

export function Estrategias() {
  return (
    <MarketingLayout>
      <main className="oneb-page oneb-section">
        <section className="oneb-page-hero">
          <div>
            <p className="oneb-eyebrow">Estratégias OneB</p>
            <h1>Estratégia é processo, não promessa.</h1>
            <p>
              Aprenda a estruturar uma decisão que possa ser explicada, registrada e revisada — inclusive quando a melhor escolha for esperar.
            </p>
          </div>
          <aside className="oneb-principles-card">
            <p className="oneb-eyebrow">Antes de operar</p>
            {principles.map((principle) => (
              <div key={principle}><CheckCircle2 size={18} /><span>{principle}</span></div>
            ))}
            <small>Sem sinal mágico. Sem decisão sem motivo.</small>
          </aside>
        </section>
        <section className="oneb-curriculum-intro">
          <div><p className="oneb-eyebrow">Fundamentos do método</p><h2>Quatro hábitos para decisões melhores.</h2></div>
          <p>Cada bloco resolve uma parte do processo. Juntos, eles formam uma rotina simples de preparação e revisão.</p>
        </section>
        <div className="oneb-strategy-grid">
          {strategies.map((strategy, index) => (
            <StrategyCard key={strategy.title} strategy={strategy} index={index} />
          ))}
        </div>
      </main>
    </MarketingLayout>
  );
}
