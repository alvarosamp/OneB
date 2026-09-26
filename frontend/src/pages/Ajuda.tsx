import { Link } from 'react-router-dom';
import { PageHeader, Section } from '../components/ui';
import { STATE_LABEL } from '../lib/decisionState';
import styles from './Ajuda.module.css';

const FLOW = [
  { to: '/ferramenta', title: 'Hoje', text: 'Ticker de referência, gráfico da Nasdaq, leitura do dia com evidências, radar da watchlist, notícias, calendário e alertas.' },
  { to: '/watchlist', title: 'Watchlist', text: 'Cadastre poucos ativos e crie regras objetivas (preço, variação, RSI, médias, MACD, volume). Teste a regra nos últimos 3 meses antes de salvar.' },
  { to: '/radar', title: 'Radar', text: 'Tabela da watchlist ordenada por atenção. O nível de atenção é explicável: passe o mouse para ver as contribuições.' },
  { to: '/analise', title: 'Análise', text: 'Resumo diário, análise matinal, regime, estudo técnico com níveis e setups, e contexto macro.' },
  { to: '/assistente', title: 'Assistente', text: 'Visão do mercado, análise de ativo, revisão de setup, perguntas livres e explicação de alertas, sempre com evidências.' },
  { to: '/carteira', title: 'Carteira', text: 'Lance operações feitas fora do OneB para acompanhar P&L, manter o diário de decisão e medir seu desempenho.' },
  { to: '/academia', title: 'Academia', text: 'Trilhas em ordem, com exercício curto e prática no gráfico. Os termos do terminal têm “Entenda” com link para a aula.' },
];

const ROUTINE = [
  'Abra o Hoje e confira se há dado atrasado (aviso em amarelo), evento de alto impacto no calendário ou notícia forte.',
  'Leia a leitura do dia: o estado e as evidências dizem se o contexto pede espera.',
  'Use o radar para escolher os poucos ativos que merecem investigação.',
  'Abra o ativo: gráfico, regime, momentum, volatilidade e risco em ATR.',
  'Se houver plano, revise-o no Assistente (Revisar setup) com seu capital e risco máximo.',
  'Operou fora do OneB? Registre na Carteira para alimentar o diagnóstico de desempenho.',
];

/** Ajuda (antigo Como usar). */
export function Ajuda() {
  return (
    <div className={styles.page}>
      <PageHeader title="Ajuda" description="O OneB monitora NASDAQ, ouro e a sua watchlist e explica os dados coletados. Não executa ordens e não recomenda compra ou venda." />

      <Section title="Onde encontrar cada coisa">
        <dl className={styles.flow}>
          {FLOW.map((f) => (
            <div key={f.to}>
              <dt>
                <Link to={f.to}>{f.title}</Link>
              </dt>
              <dd>{f.text}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section title="Rotina sugerida" divided>
        <ol className={styles.list}>
          {ROUTINE.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ol>
      </Section>

      <Section title="Como ler os estados" divided>
        <dl className={styles.flow}>
          <div>
            <dt>{STATE_LABEL['sem-setup']}</dt>
            <dd>Não há combinação de contexto e gatilho que justifique agir agora. Esperar é uma decisão válida.</dd>
          </div>
          <div>
            <dt>{STATE_LABEL.observar}</dt>
            <dd>Contexto e leitura técnica apontam na mesma direção (viés de alta ou de baixa), mas ainda sem força suficiente.</dd>
          </div>
          <div>
            <dt>{STATE_LABEL.formacao}</dt>
            <dd>Regime forte, técnica e momentum alinhados. Ainda é preciso definir entrada, stop, alvo e tamanho por conta própria.</dd>
          </div>
        </dl>
      </Section>

      <Section title="Atalhos" divided>
        <dl className={styles.flow}>
          <div>
            <dt>
              <kbd>Ctrl</kbd> + <kbd>K</kbd> (ou <kbd>⌘</kbd> + <kbd>K</kbd>)
            </dt>
            <dd>Buscar ativo ou página e abrir ações (gráfico, alerta, watchlist, Assistente).</dd>
          </div>
          <div>
            <dt>
              <kbd>Espaço</kbd>, <kbd>←</kbd> <kbd>→</kbd>
            </dt>
            <dd>No player da Academia, para vídeos em arquivo: reproduzir ou pausar e voltar ou avançar 5 s.</dd>
          </div>
        </dl>
      </Section>

      <Section title="Limites" divided>
        <p className={styles.text}>
          Os dados vêm de fontes gratuitas e podem ter atraso; séries do FRED (juros, VIX, índice do dólar) são diárias. O status de mercado é calculado pelo relógio do seu dispositivo, com a lista de
          feriados configurada no app. Nenhuma leitura garante resultado nem substitui sua gestão de risco.
        </p>
      </Section>
    </div>
  );
}
