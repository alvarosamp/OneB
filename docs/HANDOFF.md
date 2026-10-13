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
- No Windows, heredocs do bash quebram com aspas e acentos. Escreva o script num arquivo e rode o arquivo.

## Placar dos testes (evidência)

| Teste | Resultado | Documento |
|---|---|---|
| `calendar_v1`: volatilidade depois de CPI, payroll e FOMC | **APROVADO** para volatilidade (de 2,3x a 5,7x em 30 min); sem direção | `docs/research/calendar_v1_2026-10-07.md` |
| `volfc_v1`: amplitude do próximo pregão (HAR + evento) | **APROVADO**: erro 10,5% menor que o ATR 14; faixa de 80% acertou de 77% a 83% | `docs/research/volfc_v1_2026-10-10.md` |
| `tsmom_v1`: tendência de 1, 3 e 12 meses | NOT_SIGNIFICANT, inclusive com o universo completo | `docs/research/tsmom_v1_2026-10-08.md` |
| `lab_v1`: 64 regras de indicador, incluindo o Duck | Nenhuma sobreviveu | `docs/research/lab_v1_discovery_2026-10-10.md` |
| `f7_honor_v1`: momentum da última hora com o custo HonorPro | REPROVADO; a vantagem sumiu a partir de 2024 | idem |
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
