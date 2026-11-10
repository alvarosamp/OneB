import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import type { BillingStatus, PlansInfo } from '../types';

function fmtDate(iso: string | null) {
  return iso ? new Date(iso).toLocaleDateString('pt-BR') : '';
}

export function Planos() {
  const { user, refreshUser } = useAuth();
  const toast = useToast();
  const [params] = useSearchParams();
  const [plans, setPlans] = useState<PlansInfo | null>(null);
  const [status, setStatus] = useState<BillingStatus | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get<PlansInfo>('/api/billing/plans', { skipAuth: true }).then(setPlans).catch(() => undefined);
    api.get<BillingStatus>('/api/billing/status').then(setStatus).catch(() => undefined);
  }, []);

  useEffect(() => {
    // volta do Stripe: o webhook pode demorar alguns segundos; tenta de novo antes de desistir
    if (params.get('checkout') !== 'ok') return;
    toast('Pagamento recebido. Liberando o Pro...', 'success');
    let tries = 0;
    const timer = setInterval(async () => {
      tries += 1;
      try {
        const s = await api.get<BillingStatus>('/api/billing/status');
        setStatus(s);
        if (s.paid || tries >= 8) {
          clearInterval(timer);
          await refreshUser();
        }
      } catch {
        clearInterval(timer);
      }
    }, 2000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  async function go(path: '/api/billing/checkout' | '/api/billing/portal') {
    setBusy(true);
    try {
      const { url } = await api.post<{ url: string }>(path);
      window.location.assign(url);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Não foi possível abrir o pagamento', 'error');
      setBusy(false);
    }
  }

  const paid = status?.paid ?? false;

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <p className="eyebrow">Conta</p>
          <h1>Planos</h1>
        </div>
      </div>

      {params.get('checkout') === 'cancelado' && <p className="muted">Pagamento cancelado. Nada foi cobrado.</p>}

      {status && (
        <div className="panel" style={{ marginBottom: '1rem' }}>
          <strong>
            Seu plano: {paid ? 'Pro' : status.on_trial ? 'Pro (teste grátis)' : 'Free'}
          </strong>
          {status.on_trial && <p className="muted">O teste termina em {fmtDate(status.trial_ends_at)}.</p>}
          {paid && status.current_period_end && (
            <p className="muted">
              Situação: {status.subscription_status || 'ativo'} · período atual até {fmtDate(status.current_period_end)}
            </p>
          )}
          {paid && !status.has_customer && <p className="muted">Plano liberado manualmente pelo administrador.</p>}
        </div>
      )}

      <div className="guide-grid landing-grid">
        <article className="guide-card">
          <h3>Free</h3>
          <p className="plan-price">R$ 0</p>
          <ul className="plan-list">
            <li>{plans ? `${plans.free.max_symbols} ativos na watchlist` : 'Watchlist básica'}</li>
            <li>{plans ? `${plans.free.max_rules} regras de alerta` : 'Regras de alerta'}</li>
            <li>Painel, notícias e calendário</li>
            <li>Registro de posições</li>
          </ul>
        </article>
        <article className="guide-card plan-highlight">
          <h3>Pro</h3>
          <p className="plan-price">{plans?.pro.price_label ?? ''}</p>
          <ul className="plan-list">
            <li>{plans ? `Até ${plans.pro.max_symbols} ativos e ${plans.pro.max_rules} regras` : 'Mais ativos e regras'}</li>
            <li>Alertas e resumos no Telegram</li>
            <li>Painel de risco por ativo</li>
            <li>Análise matinal e relatórios em PDF</li>
            <li>Assistente e copiloto com IA</li>
          </ul>
          {paid ? (
            status?.has_customer && (
              <button type="button" className="btn-secondary" disabled={busy} onClick={() => go('/api/billing/portal')}>
                Gerenciar assinatura
              </button>
            )
          ) : status && !status.checkout_enabled ? (
            <p className="muted">Pagamento online em breve. Fale com o administrador para liberar o Pro.</p>
          ) : (
            <button type="button" className="auth-submit" disabled={busy || !status} onClick={() => go('/api/billing/checkout')}>
              {busy ? 'Abrindo...' : 'Assinar o Pro'}
            </button>
          )}
        </article>
      </div>
      {user && !paid && (
        <p className="muted">
          Cobrança mensal recorrente pelo Stripe. Cancele quando quiser em &quot;Gerenciar assinatura&quot;.
        </p>
      )}
    </div>
  );
}
