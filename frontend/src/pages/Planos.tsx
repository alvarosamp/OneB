import { Link } from 'react-router-dom';
import { MarketingLayout } from '../components/marketing/MarketingLayout';
import { plans } from '../content/onebMarketing';

export function Planos() {
  return (
    <MarketingLayout>
      <main className="oneb-page oneb-section">
        <section className="oneb-section-heading compact">
          <p className="oneb-eyebrow">Planos</p>
          <h1>Escolha como quer entrar na OneB.</h1>
          <p>Comece pela escola ou combine estudo com o Terminal para aplicar o método no dia a dia.</p>
          <div className="oneb-toggle">
            <span>Mensal</span>
            <span>Anual - 20% OFF</span>
          </div>
        </section>
        <section className="oneb-pricing-grid">
          {plans.map((plan) => (
            <article key={plan.name} className={plan.featured ? 'featured' : ''}>
              {plan.featured && <div className="oneb-plan-badge">MVP recomendado</div>}
              <h2>{plan.name}</h2>
              <p>{plan.description}</p>
              <strong>
                {plan.price}
                <small>/mês</small>
              </strong>
              <ul>
                {plan.benefits.map((benefit) => (
                  <li key={benefit}>✓ {benefit}</li>
                ))}
              </ul>
              <Link to="/cadastro" className={plan.featured ? 'oneb-primary' : 'oneb-secondary'}>
                Começar agora
              </Link>
            </article>
          ))}
        </section>
        <section className="oneb-trust-row">
          <span>Pagamento seguro</span>
          <span>Cancele quando quiser</span>
          <span>Acesso imediato</span>
        </section>
      </main>
    </MarketingLayout>
  );
}
