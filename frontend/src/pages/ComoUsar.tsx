import { Link } from 'react-router-dom';

const flows = [
  {
    title: '1. Comece pelo Dashboard',
    text: 'Use o radar para priorizar ativos, confira a qualidade dos dados e observe dolar, ouro, noticias globais, eventos e alertas.',
    link: '/',
    label: 'Abrir dashboard',
  },
  {
    title: '2. Cadastre ativos e regras',
    text: 'Monte a watchlist e crie regras objetivas com preco, variacao, RSI, medias, MACD, volume e backtest antes de salvar.',
    link: '/watchlist',
    label: 'Watchlist',
  },
  {
    title: '3. Leia o mercado',
    text: 'Acompanhe noticias por ativo, noticias globais/macro, calendario economico e earnings para entender o pano de fundo.',
    link: '/mercado',
    label: 'Mercado',
  },
  {
    title: '4. Use o Copiloto',
    text: 'Informe ativo, capital e risco maximo. O sistema vota com agentes tecnico, noticias, macro, risco e perfil.',
    link: '/copiloto',
    label: 'Copiloto',
  },
  {
    title: '5. Registre operacoes',
    text: 'Lance compras e vendas manuais em Posicoes para medir P&L, exposicao e alimentar o diario inteligente.',
    link: '/posicoes',
    label: 'Posicoes',
  },
  {
    title: '6. Aprenda com o Perfil',
    text: 'Veja taxa de acerto, profit factor, horarios, ativos, estilos, expectativa e licoes por trade fechado.',
    link: '/perfil',
    label: 'Perfil',
  },
  {
    title: '7. Converse com a IA',
    text: 'Pergunte sobre movimentos, alertas, noticias, risco e contexto. A IA explica dados coletados, sem executar ordens.',
    link: '/assistente',
    label: 'Assistente IA',
  },
];

const routine = [
  'Abra o Dashboard e veja se ha dados atrasados, noticias globais fortes ou eventos economicos criticos.',
  'Confira dolar e ouro para entender pressao macro, apetite por risco e impacto em resultado para quem opera do Brasil.',
  'Use o radar para escolher os ativos que merecem investigacao primeiro.',
  'Abra o ativo, valide grafico, RSI, MACD, medias, volume e noticias recentes.',
  'Rode o Copiloto com capital e risco maximo antes de planejar qualquer entrada manual.',
  'Se operar fora da plataforma, registre a compra/venda em Posicoes para alimentar o Perfil.',
  'Revise o Perfil do Trader semanalmente para detectar erros repetidos e setups mais fortes.',
];

const validationChecks = [
  {
    title: 'Dados reais',
    text: 'Confirme se AAPL, MSFT, NVDA e SNAP retornam candles OHLCV suficientes pelo Yahoo Finance.',
  },
  {
    title: 'Falso positivo',
    text: 'Compare cada sinal historico com o retorno dos proximos 5 pregoes e conte os sinais que falharam.',
  },
  {
    title: 'Confianca minima',
    text: 'A simulacao so pode comprar se a precisao historica for pelo menos 58% e o retorno medio for positivo.',
  },
  {
    title: 'Banca de US$200',
    text: 'O robô compra apenas acoes inteiras que caibam no caixa, sem alavancagem e sem ordem real.',
  },
  {
    title: 'Risco',
    text: 'Toda entrada simulada nasce com stop de 1 ATR e alvo de 2 ATR; posicoes abertas continuam sendo gerenciadas.',
  },
  {
    title: 'Resposta confiavel',
    text: 'Quando o filtro nao passa, a resposta correta e NO_TRADE. Esperar tambem e uma decisao.',
  },
];

export function ComoUsar() {
  return (
    <div className="container dashboard-container">
      <div className="page-header">
        <div>
          <p className="eyebrow">Manual operacional</p>
          <h1>Como usar o OneB Terminal</h1>
          <p className="muted">
            O sistema transforma dados de mercado em um processo de decisao: monitoramento, contexto,
            explicabilidade, risco, diario e aprendizado do trader. Ele nao executa ordens.
          </p>
        </div>
      </div>

      <section className="guide-grid">
        {flows.map((step) => (
          <article className="guide-card" key={step.title}>
            <h2>{step.title}</h2>
            <p>{step.text}</p>
            <Link to={step.link}>{step.label}</Link>
          </article>
        ))}
      </section>

      <section className="dashboard-grid">
        <div className="panel panel-wide">
          <h2>Rotina recomendada</h2>
          <ol className="decision-list">
            {routine.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
        </div>

        <aside className="panel">
          <h2>Leitura dos sinais</h2>
          <ul className="source-list">
            <li>
              <strong>Score do radar</strong>
              <span>Triagem para investigar, nao uma ordem de compra.</span>
            </li>
            <li>
              <strong>Copiloto</strong>
              <span>Votos e explicacoes de agentes especializados.</span>
            </li>
            <li>
              <strong>Perfil</strong>
              <span>Aprendizado baseado no seu historico real de operacoes.</span>
            </li>
            <li>
              <strong>Noticias globais</strong>
              <span>Contexto macro que pode afetar todo o mercado.</span>
            </li>
          </ul>
        </aside>
      </section>

      <section className="panel">
        <h2>Fluxo para analisar uma acao</h2>
        <ol className="decision-list">
          <li>Confirme se a cotacao esta recente e se ha evento macro ou noticia relevante.</li>
          <li>Veja se o ativo aparece no radar por movimento, alerta, noticia ou earnings.</li>
          <li>Valide tecnico no grafico: tendencia, momentum, volume e possivel sobrecompra/sobrevenda.</li>
          <li>Use o Copiloto para combinar tecnico, noticias, macro, risco e perfil.</li>
          <li>Leia a tese contraria antes de decidir. Ela existe para evitar confirmacao cega.</li>
          <li>Defina entrada, stop, alvo, perda maxima e tamanho de posicao fora do sistema.</li>
          <li>Depois da operacao, registre o resultado para o diario inteligente aprender.</li>
        </ol>
      </section>

      <section className="panel">
        <h2>Modo simulacao confiavel</h2>
        <p className="muted">
          O projeto inclui um simulador de carteira ficticia que roda em segundo plano no Docker.
          Ele usa US$200 de banca inicial, dados historicos do Yahoo Finance, mede falsos positivos
          e so segue uma recomendacao quando a calibracao historica passa no filtro minimo.
        </p>
        <ul className="source-list">
          {validationChecks.map((item) => (
            <li key={item.title}>
              <strong>{item.title}</strong>
              <span>{item.text}</span>
            </li>
          ))}
        </ul>
        <ol className="decision-list">
          <li>Rode o projeto com Docker para manter API, worker, frontend e simulador ativos.</li>
          <li>Abra o Resumo Diario para ler tendencias, volatilidade, noticias e pontos de atencao.</li>
          <li>Acompanhe a simulacao pelos arquivos de eventos e estado salvos na pasta data.</li>
          <li>Antes de confiar em uma entrada, confira se a decisao atual nao foi bloqueada por falso positivo historico.</li>
          <li>Use o resultado como treino e validacao de processo, nunca como ordem automatica.</li>
        </ol>
      </section>

      <section className="panel">
        <h2>Limites importantes</h2>
        <p className="muted">
          O OneB Terminal usa fontes gratuitas e dados que podem ter atraso. O Copiloto e o Assistente
          ajudam a interpretar informacoes, mas nao garantem resultado, nao substituem gestao de risco e
          nao constituem recomendacao de investimento.
        </p>
      </section>
    </div>
  );
}
