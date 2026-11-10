import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { PlansInfo } from '../types';

const FEATURES = [
  {
    title: 'Alertas que você define',
    text: 'Regras combinadas (preço, RSI, médias, MACD, volume) com teste no histórico antes de salvar. O aviso chega no painel e no Telegram.',
  },
  {
    title: 'Painel de risco por ativo',
    text: 'Tendência, volatilidade, tamanho de posição pelo risco que você aceita, stop sugerido por ATR e o quanto o ativo costuma se mexer em dia de resultado.',
  },
  {
    title: 'Análise matinal',
    text: 'Antes da abertura: índices, níveis de pivô, notícias de maior impacto e o calendário econômico do dia, no painel, no Telegram e em PDF.',
  },
  {
    title: 'Disciplina nas posições',
    text: 'Registre suas operações e veja P&L, perfil de risco e padrões de comportamento. Nada é executado: é só o seu caderno de bordo.',
  },
  {
    title: 'IA que explica, não decide',
    text: 'O assistente resume notícias e dados da sua watchlist. Ele nunca recomenda comprar ou vender.',
  },
  {
    title: 'Registro público de sinais',
    text: 'Gravamos todo dia o estado de tendência e mostramos o placar contra comprar e segurar, com os acertos e os erros.',
  },
];

export function Landing() {
  const [plans, setPlans] = useState<PlansInfo | null>(null);

  useEffect(() => {
    api
      .get<PlansInfo>('/api/billing/plans', { skipAuth: true })
      .then(setPlans)
      .catch(() => setPlans(null));
  }, []);

  return (
    <div className="landing">
      <header className="landing-nav">
        <span className="brand">📈 Monitor NASDAQ</span>
        <nav>
          <Link to="/publico">Registro de sinais</Link>
          <Link to="/login">Entrar</Link>
          <Link to="/cadastro" className="btn-link">
            Testar grátis
          </Link>
        </nav>
      </header>

      <section className="landing-hero">
        <p className="eyebrow">Monitor de risco e disciplina</p>
        <h1>Acompanhe suas ações da NASDAQ com método, não com palpite.</h1>
        <p className="landing-lead">
          Alertas, painel de risco e um briefing antes da abertura. Sem promessa de previsão: nossos testes com
          30 ações, 15 ETFs e 12 anos de dados não encontraram sinal de entrada que supere comprar e segurar de
          forma confiável. O que se repetiu foi a <strong>redução de risco</strong>, e é isso que entregamos.
        </p>
        <div className="landing-cta">
          <Link to="/cadastro" className="auth-submit landing-btn">
            {plans ? `Começar com ${plans.pro.trial_days} dias de Pro grátis` : 'Criar conta grátis'}
          </Link>
          <Link to="/publico" className="landing-secondary">
            Ver o registro público
          </Link>
        </div>
        <p className="muted landing-note">Sem cartão para testar. Você continua no plano Free ao fim do teste.</p>
      </section>

      <section className="landing-section">
        <h2>O que você recebe</h2>
        <div className="guide-grid landing-grid">
          {FEATURES.map((f) => (
            <article key={f.title} className="guide-card">
              <h3>{f.title}</h3>
              <p className="muted">{f.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-section" id="planos">
        <h2>Planos</h2>
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
            <Link to="/cadastro" className="landing-secondary">
              Criar conta
            </Link>
          </article>
          <article className="guide-card plan-highlight">
            <h3>Pro</h3>
            <p className="plan-price">{plans?.pro.price_label ?? 'Consulte'}</p>
            <ul className="plan-list">
              <li>{plans ? `Até ${plans.pro.max_symbols} ativos e ${plans.pro.max_rules} regras` : 'Mais ativos e regras'}</li>
              <li>Alertas e resumos no Telegram</li>
              <li>Painel de risco por ativo</li>
              <li>Análise matinal e relatórios em PDF</li>
              <li>Assistente e copiloto com IA</li>
            </ul>
            <Link to="/cadastro" className="auth-submit landing-btn">
              {plans ? `Testar ${plans.pro.trial_days} dias grátis` : 'Testar grátis'}
            </Link>
          </article>
        </div>
      </section>

      <section className="landing-section">
        <h2>Perguntas frequentes</h2>
        <details>
          <summary>Vocês dizem quando comprar ou vender?</summary>
          <p className="muted">
            Não. O produto mostra dados e risco; a decisão é sua. Não executamos ordens e não somos uma
            recomendação de investimento.
          </p>
        </details>
        <details>
          <summary>De onde vêm os dados?</summary>
          <p className="muted">
            De provedores públicos e gratuitos (cotações e histórico podem ter atraso). Valide qualquer sinal
            antes de operar.
          </p>
        </details>
        <details>
          <summary>Posso cancelar quando quiser?</summary>
          <p className="muted">
            Sim, pelo portal de assinatura dentro do app. Você mantém o Pro até o fim do período pago.
          </p>
        </details>
      </section>

      <footer className="landing-footer">
        <p>
          Ferramenta apenas de monitoramento e informação. Não constitui recomendação de investimento, análise
          de valores mobiliários nem consultoria. Rentabilidade passada não garante resultado futuro.
        </p>
        <p>
          <Link to="/termos">Termos de uso</Link> · <Link to="/privacidade">Privacidade</Link> ·{' '}
          <Link to="/publico">Registro de sinais</Link>
        </p>
      </footer>
    </div>
  );
}
