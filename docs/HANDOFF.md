# Passagem de bastão — projeto OneB (atualizado em 12/10/2026)

Para continuar em outra conta, abra o Claude Code nesta pasta (`Nasdaq`) e diga:
"Leia docs/HANDOFF.md e continue o projeto a partir das próximas etapas."

## O que é o projeto

O OneB é um terminal de mercado com academia, em FastAPI + React/Vite, publicado na Hostinger via Docker.

**Princípio:** o motor quantitativo decide, o risco controla, a IA explica e o usuário opera manualmente no MT5. O app nunca envia ordens.

**Áreas:**
- **Hoje:** `/ferramenta`.
- **Análise:** abas Visão geral, Ativo, Horários, Tendência, Regime, Técnica e Macro.
- **Academia:** trilhas, quizzes e um laboratório com replays.
- **OneB AI:** assistente com ferramentas somente de leitura.

## Regras de trabalho (obrigatórias)

1. **Pré-registro antes de qualquer cálculo.**
   - Cada teste tem um arquivo em `configs/preregistration/*.json`, com o hash SHA256 gravado em `LOCK.json`.
   - `app.setups.load_preregistered` confere o hash.
   - Emendas só antes de calcular, e sempre divulgadas no próprio arquivo.
   - Proibido otimizar depois de ver o resultado.
2. **Divulgar erros:** se um cálculo saiu errado, corrigir e registrar a correção no relatório e no documento do teste.
3. **Pesado vai para o HD externo D:** dados em `D:/OneB/market-data` e relatórios em `D:/OneB/research`. O app em produção não tem o HD, por isso os resumos pequenos ficam versionados em `app/research_results/*.json`.
4. **No MT5:**
   - não habilitar ordens nem AlgoTrading;
   - não matar o terminal;
   - só leitura (pacote `MetaTrader5`, terminal em `C:\Program Files\Honor Pro MT5 Terminal\terminal64.exe`, conta demo).
5. **Sistema e git:**
   - não alterar configurações do sistema; quem faz isso é o usuário;
   - não fazer commit sem pedido.
6. **Credenciais de teste** só no app local, com o banco temporário de pré-visualização (configuração "backend-preview" em `.claude/launch.json`), e nunca repetidas no chat.
7. **Idioma:** responder ao usuário em português, de forma direta e sem jargão.

## Comandos de verificação

- Backend: `python -m pytest -q tests` (371 testes passando em 10/10/2026).
- Frontend, dentro de `frontend/`:
  - tipos: `npx tsc -b`. **Não use `tsc -p .`, que não checa nada** (o `tsconfig.json` raiz tem `"files": []`);
  - testes: `npx vitest run` (118 testes passando).
- Pré-visualização: `.claude/launch.json` tem `backend-preview` (porta 8811) e `frontend-dev` (porta 5173). O backend de pré-visualização não recarrega sozinho; reinicie depois de mudar Python.
- Deploy (o usuário roda): `docker compose -f compose.hostinger.yaml up -d --build`. Se houver migração nova, rodar antes `alembic upgrade head`.
- Antes do deploy, com o MT5 aberto: `python scripts/check_broker_specs.py` (só leitura). A HonorPro muda lote mínimo e spread sem aviso — em 14/10/2026 o US100.s passou de lote mínimo 1,0 para 0,1. Qualquer DIFERENTE: `python scripts/check_broker_specs.py --write` grava os valores em `configs/broker/honorpro.json` (com histórico), depois rodar os testes.
- A imagem Docker agora leva `configs/preregistration`, `configs/broker` e `configs/manual_advisors_v1.json` (antes ficavam fora e o placar do plano falharia em produção; teste `tests/test_docker_context.py`).
- No Windows, heredocs do bash quebram com aspas e acentos. Escreva o script num arquivo e rode o arquivo.

## Placar dos testes (evidência)

| Teste | Resultado | Documento |
|---|---|---|
| `calendar_v1`: volatilidade depois de CPI, payroll e FOMC | **APROVADO** para volatilidade (de 2,3x a 5,7x em 30 min); sem direção | `docs/research/calendar_v1_2026-10-07.md` |
| `volfc_v1`: amplitude do próximo pregão (HAR + evento) | **APROVADO**: erro 10,5% menor que o ATR 14; faixa de 80% acertou de 77% a 83% | `docs/research/volfc_v1_2026-10-10.md` |
| `tsmom_v1`: tendência de 1, 3 e 12 meses | NOT_SIGNIFICANT, inclusive com o universo completo | `docs/research/tsmom_v1_2026-10-08.md` |
| `lab_v1`: 64 regras de indicador, incluindo o Duck | Nenhuma sobreviveu | `docs/research/lab_v1_discovery_2026-10-10.md` |
| `f7_honor_v1`: momentum da última hora com o custo HonorPro | REPROVADO; a vantagem sumiu a partir de 2024 | idem |
| `ctx_v1`: plano a favor da tendência de 3 meses (Nasdaq e ouro) | NÃO APROVADO; a chance de 2R fica em ~28% de qualquer jeito | `docs/research/ctx_v1_2026-10-13.md` |
| `hours_v1`: alguma hora tem vantagem de direção? | NÃO (92 células, melhor q = 0,74); o guia de horários usa movimento e custo | `docs/research/hours_v1_2026-10-13.md` |
| `hours_v1`: alguma hora tem vantagem de direção? | NÃO (92 células, melhor q = 0,74); o guia usa movimento e custo | `docs/research/hours_v1_2026-10-13.md` |
| `ctx_v1`: plano a favor da tendência de 3 meses | NÃO APROVADO; a chance de 2R fica em ~28% | `docs/research/ctx_v1_2026-10-13.md` |
| sessfc_v1 (quanto ainda anda das 10:30 ao fechamento de NY) | APROVADO em 16/10/2026: Nasdaq −21,6% de erro e 82,6% de cobertura; ouro −12,0% e 79,5%. No app, na IA, no plano e no indicador do MT5; placar ao vivo desde 19/10 | `docs/research/sessfc_v1_2026-10-16.md` |
| plan_live_v1 (placar ao vivo do plano) | AO VIVO desde 15/10/2026; conferência retroativa 05/08–14/10: 12 de 12 alvos dentro da faixa de 95% | `docs/research/plan_live_v1_2026-10-14.md` |
| replay_v1 (usuário seguindo o OneB em 7 horários/dia) | NÃO APROVADO: direção 'sem indicadores' (acompanhar 24 h, contrariar 1 h) não supera o cara ou coroa; operar muitos horários perde pelo spread | `docs/research/replay_v1_2026-10-14.md` |
| Ilusão da taxa de acerto (descritivo) | Entradas aleatórias com TP1 curto: 63%–89% de "acerto", resultado negativo | `docs/research/win_rate_illusion_2026-10-14.md` |
| `tom_v1`: virada do mês | NÃO APROVADO, em 7 índices | `docs/research/tom_v1_2026-10-10.md` |
| 100 Pips e Caixa de Londres | Só descritivo, negativos | `docs/research/*_ex5_oos_*` |

**Conclusão:** o que tem evidência é **medir risco** (calendário, volatilidade, custo, tamanho de posição), não prever direção. O produto foi direcionado para ser um **copiloto de risco**.

## O que existe no app (feito nesta fase)

- **Análise › Ativo** (`app/routers/asset_brief.py`, `frontend/src/pages/analise/Ativo.tsx`):
  - preço e ATR;
  - amplitude esperada do próximo pregão (volfc), com o gráfico e os stops por ATR;
  - próximas horas e eventos com impacto medido;
  - calculadora de lote (`lib/riskPlan.ts`);
  - o que já foi testado no ativo.
- **Análise › Horários** (`pages/analise/Horarios.tsx`, dados em `app/research_results/hour_heatmap.json`, gerados por `scripts/build_hour_heatmap.py`): mapa de movimento e custo do spread por hora de Brasília.
- **Hoje:** bloco "Próximo pregão" (`/api/analysis/next-session`).
- **OneB AI:**
  - ferramenta `get_asset_risk` em `app/oneb_ai/tools.py`;
  - regras 8 e 9 do prompt em `app/oneb_ai/agent.py`.
- **Academia:** módulo "O laboratório do OneB" na trilha "Como avaliar um sinal", com 2 aulas e quizzes. O texto das aulas agora aceita tabelas.

**Custos medidos na HonorPro** (spread mediano em dias úteis): US100.s 0,7 ponto; US500.s 5,3 pontos (cerca de 25 vezes mais caro em proporção); XAUUSD.s 0,26.

## Correções importantes já feitas (ainda não publicadas)

1. **Cache de preços sem validade:** o diário estava congelado desde 13/08. Agora há prazo de validade por intervalo, em `app/market_data/service.py`.
2. **Calendário econômico:**
   - o FRED gerava um "FOMC" falso todo dia e não trazia eventos futuros;
   - agora o FOMC vem de `app/market_data/fomc_schedule.py` (agenda oficial do Fed; revisar a cada ano), os horários são reais (8h30 de NY) e a janela é de 21 dias;
   - `purge_legacy_economic_events` em `app/scheduler.py` limpa as linhas antigas erradas.
3. **Gráfico:** o preço era arredondado para 2 casas, o que deformava o câmbio. Agora a precisão é adaptativa.

## Fontes de dados

- **Dukascopy:** desde 08/10/2026 bloqueada. O jetta exige desafio antirrobô, e o datafeed recusa o IP do usuário.
  - **Não insistir nem contornar.** No máximo um teste com curl por semana.
  - Leitor próprio já pronto, para quando liberar: `scripts/dukascopy_feed.py` (8 s entre pedidos; pausa de 15 a 60 min em caso de 429).
- **Dados já completos no D:** M5 de 2019 a 2026 para NAS100, SPX500, EURUSD e XAUUSD (o XAU foi remontado do M1) e o diário de 17 CFDs.
- **WTI M5:** incompleto no lado ask.
- **MT5 HonorPro:** só tem cerca de 6 meses de histórico.
- **Yahoo (yfinance):** dados ao vivo do app.
- **FRED:** calendário (chave já configurada).
- **O usuário não tem orçamento para fontes pagas.**

## Atualização de 12–13/10/2026: foco na IA

- **Resposta automática com intenção** (`app/oneb_ai/intent.py` e `risk_template` em `agent.py`). Sem LLM ou com a API fora do ar, a IA entende perguntas de risco e responde com as ferramentas certas:
  - lote, stop, amplitude, horário, eventos, custo, tendência e pedidos de direção;
  - pergunta sobre setup continua indo para o ledger;
  - saldo em R$ não é calculado; a IA pede o valor em US$.
- **Verificador:** passou a ignorar nomes de índice ("Nasdaq 100", "S&P 500") ao checar números.
- **Placar ao vivo da previsão:** endpoint `/api/analysis/volfc-scoreboard`, mostrado na aba Ativo e entregue à IA como `forecast_live_score`. Coeficientes congelados desde 10/10, com início em 12/10.
- **Feriados federais dos EUA:** marcados na previsão (`us_holiday`) e citados pela IA como dia atípico.
- **Perguntas sugeridas no Assistente** voltadas a risco.
- **Avaliações (golden):** `tests/evals/golden.json` tem 19 casos, 7 deles de risco com a fixture de mercado `semana_cpi`. O gancho `ToolContext.market_override` só é usado pelo harness. O teste `test_ai_evals` exige 100% de aprovação no modo automático.
  - Para trocar modelo ou prompt, rode `python scripts/run_ai_evals.py --live`.
  - Regras duras: zero número não aterrado e zero linguagem de ordem.
- **Estatística de setup no modo automático:** "Como o Gold Fakeout performou?" e "É melhor que aleatório?" consultam `get_setup_stats` (`stats_template`).
- **Roteamento:** pedidos de entrada, alvo ou recomendação vão para o ledger, que recusa dar níveis.
- **Plano de trade com confiança medida** (o "mesmo produto da VTX", na versão honesta):
  - as taxas-base são calculadas por `scripts/build_trade_plan_rates.py` e gravadas em `app/research_results/trade_plan_rates.json`;
  - para toda hora cheia de 2023 a 2026, compra e venda, stop de 1, 1,5 e 2 ATR(1h), alvos de 1R, 2R e 3R, compra no ask e venda no bid;
  - a API é `/api/analysis/trade-plan/{key}?direction=&stop_atr=`;
  - na tela, é o card "Plano de trade" da aba Ativo, com os níveis no gráfico;
  - na IA, é a ferramenta `get_trade_plan`, usada só quando o usuário escolhe a direção ("se eu comprar/vender").
  - **Números de referência:** com stop de 1,5 ATR, bater 2R antes do stop acontece em cerca de 28% das entradas, e bater 1R em cerca de 48%.
- **Histórico de conversa no modo automático:** `intent.resolve`, por exemplo "e no ouro?".
- **Avaliações:** 22 casos, todos aprovados.
- **Guia de horários** (`scripts/build_hours_guide.py` → `hours_guide.json`; `/api/analysis/hours-guide`): a janela principal, o pico e as horas a evitar, em frases prontas no horário de Brasília. Aparece na aba Horários (guia rápido), no relatório e na IA.
- **Botão "Gerar análise"** na aba Ativo (`/api/analysis/report/{key}`, `components/assistant/AnalysisReport.tsx`): relatório completo com o texto pronto para copiar.
- **LLM local:** não está configurado (`LLM_PROVIDER`/`ANTHROPIC_API_KEY`). Com a chave, o agente usa as mesmas ferramentas e o mesmo verificador.


## Atualização de 14/10/2026: IA

- **Novas respostas no modo automático:**
  - panorama do dia ("como está o mercado hoje?");
  - glossário (`app/oneb_ai/glossary.py`, ferramenta `get_glossary`);
  - comparação entre ativos;
  - chance de bater cada alvo sem direção escolhida;
  - "a IA acerta quanto?" (o que foi aprovado, o placar ao vivo e a direção não comprovada);
  - resumo de todos os setups.
- **`get_setup_stats`** passou a ler também os relatórios fora da amostra de 13X, Caixa de Londres e 100 Pips (`results.H1_primary`).
- **Cobertura:** 39 de 40 perguntas realistas vão para a resposta certa (o script de cobertura fica no scratchpad da sessão; refazer se necessário).
- **Avaliações:** 31 casos, todos aprovados, mais um teste que confere o esquema estrito das ferramentas para a API da Anthropic.
- **Avaliação pelo usuário (gostei/não gostei):**
  - colunas `rating`, `feedback_comment` e `feedback_at` em `ai_answer_logs`, com a migração `d20261013a01`, que exige `alembic upgrade head`;
  - rotas `async` que buscavam cotações na rede travavam o servidor inteiro (mesa de decisão, assistente antigo, análise matinal): o trabalho síncrono agora roda em `asyncio.to_thread`;
  - calendário: janela de 45 dias (sempre cobre o próximo CPI, payroll e FOMC) e dedupe em UTC — antes, no SQLite, o mesmo evento parecia novo, o INSERT quebrava a constraint e o job inteiro era desfeito (teste `tests/test_calendar_refresh.py`);
  - Confiabilidade da IA: `tests/evals/routing.json` (70 perguntas, 16 assuntos, gíria/erro/abreviação) + golden (46) — 116/116; `python scripts/run_ai_evals.py` grava `app/research_results/ai_reliability.json`, mostrado em 'Por que confiar' junto com a taxa de respostas conferidas e as avaliações de produção. Pergunta não entendida recebe 'Não entendi essa pergunta' (não mais o ledger); resposta automática com número sem fonte tem a frase removida antes de chegar ao cliente. Rodar o script a cada mudança na IA;
  - Indicador MT5 `mt5/OneB_Risco.mq5` (gerado por `scripts/build_mt5_indicator.py` a partir de volfc_v1, trade_plan_rates e hours_guide; compila com 0 erros no MetaEditor; instalação em `mt5/LEIAME.md`). Só desenha e calcula; não envia ordens (teste `tests/test_mt5_indicator.py` proíbe OrderSend/CTrade);
  - 'Avaliar um sinal' (Análise › Avaliar sinal, `app/signal_eval.py`, `app/routers/signals.py`, migração `g20261016a01`): lê o sinal em texto livre, mede a chance de cada alvo antes do stop nos últimos 60 dias (taxa-base NEUTRA = média de compra e venda, com spread, até 24 h), quanto precisa para empatar, lote e avisos; grava em `signal_records` e mostra o placar por fonte (conferido como entrada a mercado no momento em que foi colado, pelas distâncias do sinal). A IA também avalia sinal colado no chat (ferramenta `evaluate_signal`). O job do worker grava o resultado dos sinais abertos;
  - SÓ o job `record_plan_live` do worker (minuto 20 de cada hora, dados baixados sem cache) grava planos e previsões; as telas e a IA só leem (revisão de 15/10/2026: leitura gravando causava corrida no INSERT e podia gravar previsão com a última hora incompleta). Sem o worker ligado, nada é gravado;
  - tabela `forecast_live_records` (migração `f20261015a01`): a previsão do próximo pregão (volfc_v1) é gravada na primeira vez que é calculada e nunca muda; o placar mostra se foi gravada antes do pregão (job das :20 grava às 17:20 de NY);
  - barras diárias das previsões agora são montadas das barras de 1 hora (pregão de 17:00 a 17:00 de NY): a diária do Yahoo para futuros é sobrescrita pela sessão da noite às 18:00 de NY e o pregão do dia sumia (visto em 15/10/2026; teste `test_sessions_from_hourly_splits_at_17h_new_york`);
  - tabela `plan_live_records` (placar ao vivo do plano), com a migração `e20261014a01`, que também exige `alembic upgrade head`; o job `record_plan_live` grava de hora em hora;
  - endpoints `POST /api/opportunities/ai/feedback` e `GET /api/opportunities/ai/feedback/summary`;
  - botões na resposta do Assistente.
- **Desempenho:**
  - o agente roda as ferramentas fora do laço de eventos (`asyncio.to_thread`); antes, cada resposta congelava o servidor;
  - testes com SQLite em memória precisam de `StaticPool`;
  - o cache diário de períodos longos (1 ano ou mais) vale 6 h, porque a Mesa de Decisão rebaixava cerca de 100 ações a cada 30 min.


## Confiabilidade dos dados (14/10/2026)

- **Diferença de preço entre o gráfico e a corretora:** o app usa o FUTURO (Yahoo, ~15 min de atraso), e o usuário opera o CFD da HonorPro. Medido ao vivo em 14/10:
  - US100.s ~+1,06% (+323 pontos) contra NQ=F;
  - US500.s −0,84%;
  - XAUUSD.s −0,74%;
  - EURUSD.s −0,03%.
  - **Consequência:** o "Plano de trade", o relatório e a IA agora usam DISTÂNCIAS a partir da entrada. O usuário pode informar o preço no MT5 (`?entry=`) para ver os níveis exatos.
- **Saúde dos dados:** `/api/analysis/data-health` e `freshness(key)` mostram a idade do diário, o atraso do preço intradiário, a fonte fora do ar (`cache_fallback`), barras planas e o calendário (eventos nos próximos 7 dias e FOMC falso).
  - A aba Ativo mostra o selo "Dados em dia / com atraso / com problema".
  - A IA avisa nos contrapontos quando o dado está ruim.
- **Plugins:** o usuário tem 6 ativos; nenhum é de dados. Recomendados para ativar: "Data" (Anthropic: validar dados, estatística) e "oryxflow" (reprodutibilidade, evita dado velho; pede acesso amplo). O Bright Data não deve ser usado para contornar bloqueio de fonte.

## Próximas etapas (prioridade)

1. **Usuário:** publicar o site e pedir um commit deste trabalho.
2. **Forward do volfc:** gravar todo dia a amplitude prevista e a realizada, e mostrar o placar ao vivo no app. Primeiro teste real: o CPI de 14/10/2026.
3. **Usar o modelo aprovado na prática:**
   - a calculadora de lote passa a usar a amplitude prevista;
   - aviso de véspera de evento no app, no OneB AI e no Telegram.
4. **Academia:** aula "Efeitos famosos que sumiram" (virada de mês, momentum, tendência) e aula sobre como usar a amplitude prevista.
5. **Novos estudos, cada um com pré-registro:**
   - previsão da volatilidade hora a hora;
   - correlação entre ativos em dias de evento.
6. **Pendências externas:**
   - WTI M5 (Dukascopy);
   - Gap Drive (precisa de tick);
   - estender `configs/events/macro_events_2019_2026.json` além de set/2026 se algum estudo precisar.

## Seção Brasil · Investir (28/10/2026)

O app agora tem duas áreas: **Brasil** (investir, foco em quem nunca investiu) e **EUA** (o terminal de trading que já existia). Menu em `frontend/src/content/navigation.ts`.

- **Rota** `/brasil` (`frontend/src/pages/Brasil.tsx` e `pages/brasil/*`), abas: Começar, Simulador, Onde investir, Bolsa (B3), Eventos, Aulas.
- **Backend** `app/brasil/` + `app/routers/brasil.py` (`/api/brasil/rates|products|simulate|market|history|events`):
  - taxas: Banco Central SGS (432 Selic, 4389 CDI, 13522 IPCA 12m; 4391/433/195 no histórico), grátis e sem chave; valor de reserva com `stale=True` se o BCB cair;
  - simulador: perfil → reserva de emergência primeiro → divisão por CLASSE (nunca ticker) com o motivo → projeção líquida de IR por aporte (tabela regressiva), custódia B3, isenções; renda variável com 2.000 cenários (semente fixa) e faixa de 80%; comparação com a poupança;
  - **regra:** recomendação de ativo específico exige registro na CVM (Res. 19 e 20). O teste `test_simulator_never_names_a_ticker` garante que o simulador não cita ticker;
  - eventos: Copom 2026 (calendário BCB), FOMC, eleições (TSE; 2026: 04/10 e 25/10; posse 05/01/2027), IPCA (≈ dia 10), vencimento do Ibovespa futuro. Impacto **descritivo** (não pré-registrado) no Ibovespa em 10 anos: dia comum ~1,0%; pós-Copom 1,2% (79 reuniões); pós-turno de eleição 5,9% (6 turnos; 2º turno de 2026: −13,9%). Copom 2027 ainda não cadastrado: incluir quando o BCB publicar;
  - bolsa: ativos `.SA` vão direto ao Yahoo (o Tiingo dava 404). Salto diário > 50% é tratado como desdobramento sem ajuste (XPML11 em 01/2026) e a métrica começa depois dele.
- **Academia:** trilha "Investir no Brasil" (`app/lms_track_investir.py`, 8 aulas, quizzes em `academy_quizzes.json`). Os números das aulas são de 28/10/2026; revisar se mudarem muito.
- Testes: `tests/test_brasil.py` (16), `frontend/src/pages/brasil/Simulador.test.tsx`, `src/lib/money.test.ts`. Suíte: 454 backend, 129 frontend.
- **Deploy grátis (opcional):** `render.yaml` (API no Render Free), `frontend/vercel.json` (site no Vercel, repassa `/api` ao Render) e banco no Neon. Passo a passo em `docs/DEPLOY_GRATIS.md`. Sem worker no plano grátis. `app/config.normalize_database_url` aceita `postgresql://` do Neon/Render.
