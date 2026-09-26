import { MarketingLayout } from '../components/marketing/MarketingLayout';
import { ApplicationCard } from '../components/marketing/ApplicationCard';
import { applications } from '../content/onebMarketing';

export function Aplicacoes() {
  return (
    <MarketingLayout>
      <main className="oneb-page oneb-section">
        <section className="oneb-section-heading compact">
          <p className="oneb-eyebrow">Ferramentas OneB</p>
          <h1>O essencial para transformar informação em decisão.</h1>
          <p>
            Aprenda, acompanhe o que importa e registre suas decisões em um fluxo simples — sem excesso de telas ou promessa de sinal certo.
          </p>
        </section>

        <section className="oneb-app-grid">
          {applications.map((app, index) => (
            <ApplicationCard key={app.key} app={app} index={index} />
          ))}
        </section>
      </main>
    </MarketingLayout>
  );
}
