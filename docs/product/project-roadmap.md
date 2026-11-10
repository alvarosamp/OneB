# Planejamento de acompanhamento - OneB Market

Atualizado em: 13/08/2026

## Objetivo do projeto

Transformar o OneB Market em uma plataforma de decisao e aprendizado para traders, com quatro frentes acompanhadas em paralelo:

- Escola: trilhas, aulas, pratica guiada, progresso e revisao.
- Inteligencia: score, explicacao, memoria temporal, qualidade dos sinais e decisao auditavel.
- Indicadores: biblioteca tecnica, setups, backtests, validacao estatistica e leitura de regime.
- HFT/automacao: pesquisa e simulacao de baixa latencia, sem execucao real no curto prazo.

O principio central continua sendo: a plataforma ajuda a decidir melhor, mas nao promete certeza e nao deve executar ordens antes de passar por dados confiaveis, risco, simulacao e auditoria.

## Situacao atual resumida

| Frente | Estado atual | Proximo gargalo |
| --- | --- | --- |
| Escola | Existem telas de Escola, Aulas, Estrategias e backend LMS com cursos, modulos, aulas e progresso. Parte do conteudo ainda esta estatico ou semente inicial. | Transformar trilhas em curriculo real, com progresso ligado ao banco e exercicios conectados ao terminal. |
| Inteligencia | Ja existe radar, score, explicacao, diario, playbooks, qualidade dos dados, Mesa IA, historico, placar de confiabilidade e circuit breaker. | Padronizar contrato de predicao, calibrar fora da amostra e melhorar explicabilidade com evidencia estruturada. |
| Indicadores | Biblioteca tecnica inclui SMA, EMA, RSI, MACD, Bollinger, volume, ATR, ADX, volatilidade, pivots e swing levels. Ha scripts de backtest e auditoria. | Montar catalogo de setups, validar por regime, custo, slippage e turnover. |
| HFT/automacao | O sistema monitora, alerta e simula. A documentacao deixa claro que nao executa ordens. | Antes de qualquer live trading: paper trading robusto, broker adapter, risco portfolio-aware e kill switch. |

## Roadmap por fase

### Fase 1 - Organizacao e MVP acompanhado, 2 a 3 semanas

Meta: deixar o produto acompanhavel por voce e testavel por 5 a 10 usuarios piloto.

Entregas:

- Criar quadro de acompanhamento com epicos: Escola, Inteligencia, Indicadores, HFT, Infra, Produto.
- Separar telas que sao demo/marketing das telas operacionais autenticadas.
- Conectar a Escola real ao LMS: lista de cursos, curso detalhe, marcar aula concluida e progresso por usuario.
- Criar backlog de conteudo: aulas obrigatorias, aulas futuras, exercicios e checklists.
- Definir metricas de acompanhamento: aulas concluidas, sinais gerados, sinais bloqueados por qualidade, recomendacoes registradas, acerto 5d, drawdown simulado.

Estudo recomendado:

- Produto SaaS para nicho financeiro: onboarding, ativacao, retencao.
- Modelagem simples de LMS: cursos, modulos, aulas, progresso e certificados.
- Revisao de compliance basico: diferenciar educacao, apoio a decisao e recomendacao de investimento.

Tempo estimado:

- Desenvolvimento: 30 a 50 horas.
- Conteudo inicial: 10 a 20 horas.
- Validacao com usuarios: 1 semana de uso guiado.

### Fase 2 - Escola OneB de verdade, 3 a 5 semanas

Meta: fazer a Escola deixar de ser vitrine e virar rotina de evolucao.

Entregas:

- Curriculo v1 com 4 trilhas:
  - Fundamentos do mercado americano.
  - Analise tecnica e price action.
  - Gestao de risco e psicologia.
  - Processo, diario e revisao.
- Cada aula deve ter video/link, resumo, checklist e exercicio pratico.
- Progresso real por usuario na UI.
- Recomendacao de proxima aula com base no erro do usuario: exemplo, se o aluno registra trade sem invalidacao, sugerir aula de invalidacao.
- Certificado simples: liberar quando concluir aulas obrigatorias e simulacoes minimas.

Estudo recomendado:

- Design instrucional.
- Rotina de trading e journaling.
- Gestao de risco antes de setup.
- Copy educacional sem promessa de ganho.

Tempo estimado:

- Produto/engenharia: 40 a 70 horas.
- Conteudo: 30 a 60 horas para a primeira versao utilizavel.

Preco sugerido para produto:

- Plano Escola: R$ 49 a R$ 69/mes.
- Escola + Terminal: R$ 97 a R$ 147/mes.
- Mesa Guiada: R$ 197 a R$ 297/mes, se houver acompanhamento humano real.

## Inteligencia

### Proximas etapas

1. Padronizar todas as decisoes no contrato de predicao:
   - simbolo, horizonte, direcao, acao, probabilidade, confianca, incerteza, regime, modelo, versao do dataset, evidencias, data dos dados e score de qualidade.

2. Migrar labels antigos para estados finais:
   - STRONG_BUY, BUY, WATCH, NO_TRADE, AVOID, SHORT, STRONG_SHORT.

3. Separar claramente:
   - modelo estatistico calcula score/probabilidade;
   - motor de risco pode bloquear;
   - LLM apenas explica.

4. Melhorar a memoria temporal:
   - resultado 1d, 5d, 20d;
   - por ativo;
   - por regime;
   - por tipo de setup;
   - com custo, slippage e taxa.

5. Criar "model health":
   - acerto recente;
   - calibracao;
   - drift;
   - quantidade minima de amostras;
   - motivo para desligar compra/venda.

Estudo recomendado:

- Validacao walk-forward.
- Calibracao de probabilidade.
- Information coefficient.
- Backtest sem vazamento de dados.
- Interpretabilidade simples: evidencia, peso, confianca e contradicoes.

Tempo estimado:

- Contrato e ajustes de backend: 20 a 35 horas.
- Calibracao e auditoria: 40 a 80 horas.
- UI de acompanhamento: 20 a 35 horas.

Custos provaveis:

- LLM barato para explicacao: pode comecar em poucos dolares por mes.
- LLM mais forte para analises longas: provisionar US$ 20 a US$ 100/mes no piloto.
- Escalar com IA sem controle de cache/log pode virar custo relevante; colocar limite por usuario desde o inicio.

## Indicadores

### Proximas etapas

1. Criar catalogo de indicadores e setups:
   - tendencia: EMA, ADX, MACD.
   - momentum: RSI, variacao percentual, rompimento.
   - volatilidade: ATR, Bollinger, volatilidade anualizada.
   - volume: volume relativo, spike de volume.
   - niveis: pivots, swing high/low, suporte/resistencia operacional.

2. Padronizar cada setup:
   - nome;
   - objetivo;
   - timeframe;
   - condicoes de entrada;
   - invalidacao;
   - stop;
   - alvo;
   - filtro de regime;
   - quando nao operar.

3. Validar cada setup com:
   - periodo in-sample e out-of-sample;
   - custos;
   - slippage;
   - turnover;
   - drawdown;
   - resultado por regime.

4. Criar tela de "Laboratorio de Indicadores":
   - escolher ativo;
   - escolher setup;
   - ver sinais historicos;
   - rodar backtest;
   - salvar como playbook.

Estudo recomendado:

- Pandas para series temporais.
- Estatistica aplicada a trading.
- Slippage e liquidez.
- Regime de mercado.
- Backtesting realista.

Tempo estimado:

- Catalogo v1: 15 a 25 horas.
- Backtests por setup: 30 a 60 horas.
- Laboratorio na UI: 40 a 70 horas.

## HFT e automacao

### Direcao recomendada

Nao tratar HFT como execucao real agora. Para este projeto, o caminho correto e:

1. Monitoramento e alertas.
2. Paper trading com o mesmo motor de estrategia e risco.
3. Simulacao intraday com dados de maior resolucao.
4. Execucao manual assistida.
5. Broker adapter em sandbox.
6. Live trading pequeno, com kill switch.
7. So depois pensar em baixa latencia.

HFT real exige outra categoria de infraestrutura, dados, contrato de corretora, colocation, controle de latencia, observabilidade, reconciliacao de ordens e risco em tempo real. Para o MVP OneB, "HFT" deve significar pesquisa e simulacao de estrategias intraday, nao promessa de competir em microsegundos.

Proximas etapas seguras:

- Criar paper broker adapter.
- Separar strategy engine de execution adapter.
- Fazer risk engine ser usado igualmente em backtest, paper e eventual live.
- Criar kill switch operacional:
  - perda diaria maxima;
  - drawdown maximo;
  - exposicao maxima;
  - numero maximo de ordens;
  - dados atrasados;
  - broker desconectado;
  - modelo degradado.
- Criar logs auditaveis de decisao: o que o sistema viu, decidiu, bloqueou e por que.

Estudo recomendado:

- Market microstructure.
- Order book, spread e slippage.
- Event-driven architecture.
- Paper trading e reconciliacao de ordens.
- Risco pre-trade.
- Regulacao e responsabilidade em sistema que pode influenciar ordem.

Tempo estimado:

- Paper trading serio: 50 a 90 horas.
- Broker sandbox: 40 a 80 horas.
- Live trading minimo com risco: 80 a 150 horas.
- HFT real: projeto separado, meses de trabalho e custo muito maior.

## Infra, dados e custos

### MVP barato

Uso indicado: piloto com poucos usuarios, sem redistribuicao agressiva de dados.

Custos mensais aproximados:

| Item | Custo |
| --- | --- |
| Frontend estatico | US$ 0 a US$ 20 |
| Backend pequeno + worker | US$ 14 a US$ 50 |
| Banco gerenciado | US$ 0 a US$ 20 no inicio |
| Finnhub | US$ 0 no plano gratuito, limitado |
| FMP | US$ 0 no basico; Starter por volta de US$ 22/mes |
| Tiingo | US$ 0 no basico; individual por volta de US$ 30/mes |
| LLM | US$ 5 a US$ 100, dependendo do uso |
| Total piloto | US$ 20 a US$ 200/mes |

Em reais, usando cambio aproximado de R$ 5,13 por US$ 1, isso fica perto de R$ 100 a R$ 1.030 por mes.

### Quando subir de plano

- Subir dados de mercado quando o free tier limitar chamadas, historico ou confiabilidade.
- Subir infra quando scheduler, API ou banco ficarem lentos.
- Subir LLM so depois de medir uso por usuario e colocar cache.
- Dados para redistribuicao comercial podem exigir licenca propria; nao assumir que API individual cobre produto SaaS publico.

Fontes de referencia consultadas em 13/08/2026:

- Finnhub pricing: https://finnhub.io/pricing
- FMP pricing: https://site.financialmodelingprep.com/pricing-plans
- Tiingo pricing: https://www.tiingo.com/about/pricing
- Render pricing/docs: https://render.com/pricing e https://render.com/docs/cronjobs
- OpenAI API pricing: https://openai.com/api/pricing/
- Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing
- Groq pricing: https://groq.com/pricing
- Banco Central conversao USD/BRL: https://www.bcb.gov.br/en/currencyconversion

## Checklist de acompanhamento semanal

Toda semana responder:

- O que foi entregue em Escola?
- O que foi entregue em Inteligencia?
- O que foi entregue em Indicadores?
- O que foi entregue em Simulacao/HFT?
- Quantos usuarios testaram?
- Quantos sinais foram gerados?
- Quantos sinais foram bloqueados por qualidade ou risco?
- Quantas recomendacoes foram registradas?
- Qual foi o acerto 5d?
- Houve erro de dados, API ou scheduler?
- O produto esta mais confiavel ou apenas com mais funcionalidades?

## Prioridade recomendada

1. Escola conectada ao banco e curriculo real.
2. Qualidade dos dados + decisao `NO_TRADE` bem explicada.
3. Catalogo de indicadores e setups validaveis.
4. Memoria temporal e confiabilidade por regime.
5. Paper trading com risk engine compartilhado.
6. So depois automacao/broker.

## Backlog inicial

| Prioridade | Frente | Tarefa | Resultado esperado |
| --- | --- | --- | --- |
| Alta | Escola | Conectar `/aulas` e `/aprendizado` ao `/api/lms/courses` | Progresso real por usuario |
| Alta | Escola | Escrever curriculo v1 com 20 a 30 aulas | Escola vendavel no piloto |
| Alta | Inteligencia | Migrar labels para decision states | Mesa IA alinhada ao contrato |
| Alta | Inteligencia | Exibir motivo de `NO_TRADE` com qualidade/risco | Confiança e transparencia |
| Alta | Indicadores | Criar catalogo de setups v1 | Regras deixam de ser soltas |
| Media | Indicadores | Backtest por regime e custos | Evidencia antes de marketing |
| Media | Produto | Dashboard de acompanhamento semanal | Gestao do projeto |
| Media | HFT | Paper broker adapter | Simulacao realista |
| Baixa | HFT | Broker sandbox | Preparacao para execucao futura |
| Baixa | HFT | Live trading | Somente apos kill switch e auditoria |

