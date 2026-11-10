import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { PAYMENT_REQUIRED_EVENT } from '../api/client';
import { useAuth } from '../context/AuthContext';

function daysLeft(iso: string | null): number {
  if (!iso) return 0;
  return Math.max(0, Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000));
}

/** Faixa no topo: avisa do teste grátis, do plano Free, ou de um limite acabado de atingir. */
export function PlanBanner() {
  const { user } = useAuth();
  const [blocked, setBlocked] = useState<string | null>(null);

  useEffect(() => {
    const onBlocked = (e: Event) => setBlocked((e as CustomEvent<string>).detail ?? 'Recurso do plano Pro.');
    window.addEventListener(PAYMENT_REQUIRED_EVENT, onBlocked);
    return () => window.removeEventListener(PAYMENT_REQUIRED_EVENT, onBlocked);
  }, []);

  if (!user) return null;

  if (blocked) {
    return (
      <div className="plan-banner plan-banner-warn" role="status">
        <span>{blocked}</span>
        <Link to="/planos">Ver planos</Link>
        <button type="button" className="link-btn" onClick={() => setBlocked(null)} aria-label="Fechar aviso">
          ✕
        </button>
      </div>
    );
  }
  if (user.on_trial) {
    const days = daysLeft(user.trial_ends_at);
    return (
      <div className="plan-banner" role="status">
        <span>
          Teste grátis do Pro: {days} {days === 1 ? 'dia restante' : 'dias restantes'}.
        </span>
        <Link to="/planos">Assinar</Link>
      </div>
    );
  }
  if (user.plan === 'free') {
    return (
      <div className="plan-banner" role="status">
        <span>Você está no plano Free. Libere Telegram, painel de risco, IA e relatórios no Pro.</span>
        <Link to="/planos">Ver planos</Link>
      </div>
    );
  }
  return null;
}
