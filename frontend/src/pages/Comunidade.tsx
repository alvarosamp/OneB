import { Link } from 'react-router-dom';
import { MarketingLayout } from '../components/marketing/MarketingLayout';
import { CommunityMockup } from '../components/marketing/Visuals';
import { resultStats } from '../content/onebMarketing';

export function Comunidade() {
  return (
    <MarketingLayout>
      <main className="oneb-page oneb-section">
        <section className="oneb-community-section">
          <div>
            <p className="oneb-eyebrow">Comunidade OneB</p>
            <h1>Uma comunidade que cresce junto e se apoia todos os dias.</h1>
            <p>
              Troque experiências, compartilhe resultados e evolua ao lado de traders comprometidos com consistência.
            </p>
            <div className="oneb-community-stats">
              <strong>1.500+<span>Membros ativos</span></strong>
              <strong>24/7<span>Suporte e networking</span></strong>
              <strong>Grupos<span>Por nível e objetivos</span></strong>
            </div>
            <Link to="/cadastro" className="oneb-secondary">
              Entrar na comunidade
            </Link>
          </div>
          <CommunityMockup />
        </section>
        <section className="oneb-results">
          {resultStats.map((stat) => (
            <article key={stat.label}>
              <strong>{stat.value}</strong>
              <span>{stat.label}</span>
            </article>
          ))}
        </section>
      </main>
    </MarketingLayout>
  );
}
