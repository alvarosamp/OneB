import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

/** Mostra a página só para quem tem Pro (assinatura ou teste grátis); os demais veem o convite. */
export function ProGate({ feature, children }: { feature: string; children: ReactNode }) {
  const { user } = useAuth();
  if (user?.plan === 'pro') return <>{children}</>;
  return (
    <div className="container">
      <div className="upgrade-card">
        <p className="eyebrow">Plano Pro</p>
        <h1>{feature}</h1>
        <p className="muted">
          Este recurso faz parte do plano Pro: alertas no Telegram, painel de risco, análise matinal,
          assistente de IA e relatórios em PDF.
        </p>
        <Link to="/planos" className="btn-link">
          Ver planos
        </Link>
      </div>
    </div>
  );
}
