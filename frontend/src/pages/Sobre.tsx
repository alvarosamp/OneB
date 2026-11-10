import { Link } from 'react-router-dom';
import { MarketingLayout } from '../components/marketing/MarketingLayout';

const values = [
  ['Condição de alto nível', 'Aulas práticas, objetivas e atualizadas com o que realmente funciona.'],
  ['Ferramentas exclusivas', 'Indicadores, estudos e relatórios para levar sua operação a outro nível.'],
  ['Mentores experientes', 'Profissionais que vivem o mercado e compartilham o que realmente importa.'],
  ['Comunidade forte', 'Networking, troca de ideias e apoio para você nunca operar sozinho.'],
];

export function Sobre() {
  return (
    <MarketingLayout>
      <main className="oneb-page oneb-section">
        <section className="oneb-about-hero">
          <div>
            <p className="oneb-eyebrow">Sobre a OneB</p>
            <h1>Muito mais que uma escola. Um ecossistema completo para investidores.</h1>
            <p>
              A OneB nasceu com o propósito de mudar o jogo da educação financeira no Brasil, formando investidores
              consistentes através de conteúdo prático, ferramentas profissionais e comunidade.
            </p>
            <div className="oneb-value-list">
              {values.map(([title, description]) => (
                <article key={title}>
                  <span>◇</span>
                  <div>
                    <h2>{title}</h2>
                    <p>{description}</p>
                  </div>
                </article>
              ))}
            </div>
          </div>
          <div className="oneb-trader-visual" aria-label="Trader observando monitores com gráficos">
            <div className="monitor-grid">
              <span />
              <span />
              <span />
              <span />
            </div>
            <strong>OneB</strong>
          </div>
        </section>
        <section className="oneb-final-cta">
          <div>
            <h2>Pronto para transformar a sua forma de investir?</h2>
            <p>Faça parte da OneB e evolua com quem leva o mercado a sério.</p>
          </div>
          <Link to="/cadastro" className="oneb-primary">
            Quero ser OneB
          </Link>
        </section>
      </main>
    </MarketingLayout>
  );
}
