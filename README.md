# Monitor NASDAQ

Sistema de **monitoramento e alerta** (não executa ordens) para uma watchlist de ações da
NASDAQ. Acompanha preço/volume, calcula indicadores técnicos (SMA, EMA, RSI, MACD, Bollinger,
volume médio) e dispara alertas configuráveis via **Telegram** e num **dashboard web**.

> ⚠️ Ferramenta de apoio à decisão. Não é recomendação de investimento, não executa ordens de
> compra/venda e usa dados de fontes gratuitas que podem ter atraso. Sempre valide antes de
> operar de verdade (ex: na Exness ou outra corretora).

Inclui também um **painel de mercado** com notícias por ativo, calendário econômico e
calendário de earnings, **regras de alerta compostas** (E/OU) com backtest antes de salvar,
**posições/P&L** manuais, e um **assistente com IA** que explica os dados coletados (nunca
recomenda comprar/vender).

## Arquitetura

Backend e front-end são **dois serviços separados**:

- **Backend** (`app/`): FastAPI, API REST pura (JSON), autenticação por **JWT** (Bearer token,
  sem cookie de sessão), SQLite + APScheduler + bot do Telegram.
- **Front-end** (`frontend/`): **React + TypeScript + Vite**, um SPA que consome o backend via
  `fetch`. Guarda o token JWT no `localStorage` e manda em `Authorization: Bearer <token>` em
  cada request.

Por quê separado: permite hospedar cada parte de forma independente (ex: backend num Web
Service e front num Static Site no Render), o que é o modelo "cloud-native" padrão. O preço
disso é precisar de **CORS** (o backend só aceita requests da origem configurada em
`FRONTEND_ORIGIN`) e **token em vez de cookie** (cookies cross-domain entre dois serviços do
Render dariam mais dor de cabeça que um Bearer token simples).

## Stack

- **Backend**: FastAPI + SQLAlchemy (SQLite) + APScheduler + PyJWT
- **Front-end**: React 19 + TypeScript + Vite + React Router + Chart.js (candlestick)
- **Dados**: [Finnhub](https://finnhub.io) (cotação, notícias e earnings, free tier) +
  `yfinance` (histórico para indicadores, sem necessidade de API key) +
  [Financial Modeling Prep](https://financialmodelingprep.com) (calendário econômico, free tier)
- **Alertas**: bot do Telegram (`python-telegram-bot`)
- **Assistente IA**: Anthropic Claude, Google Gemini ou Groq (à sua escolha, ver seção própria)

### Por que não Investing.com?

O Investing.com não oferece API pública. O único jeito de puxar dados de lá programaticamente
é via scraping não-oficial (bibliotecas como `investiny`), o que viola os termos de uso do site
e quebra sem aviso quando eles mudam o HTML — não é uma base confiável para algo que o pai do
seu amigo vai usar de verdade. Por isso, cotações/notícias/calendário econômico vêm de APIs
oficiais (Finnhub + FMP), que cobrem a mesma necessidade com estabilidade e dentro do free tier.

## Setup local

### Backend

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env
```

Edite o `.env`:

1. **Finnhub**: crie uma conta grátis em https://finnhub.io/register e copie a API key para
   `FINNHUB_API_KEY` (usada para cotação, notícias e calendário de earnings).
2. **Financial Modeling Prep**: crie uma conta grátis em
   https://financialmodelingprep.com/developer/docs/ e copie a API key para `FMP_API_KEY`
   (usada só para o calendário econômico — juros, payroll, inflação etc.). Se não configurar,
   o sistema roda normalmente, só sem o calendário econômico.
3. **Telegram**:
   - Fale com [@BotFather](https://t.me/BotFather) no Telegram, crie um bot (`/newbot`) e
     copie o token para `TELEGRAM_BOT_TOKEN`.
   - Envie qualquer mensagem (ex: `/start`) para o seu bot recém-criado.
   - Rode `python get_chat_id.py` para descobrir o `TELEGRAM_CHAT_ID` — cole no `.env`. Isso
     garante que só esse chat (o do pai do seu amigo) pode usar o bot.
4. **Login da API**: gere uma `SECRET_KEY` com
   `python -c "import secrets; print(secrets.token_hex(32))"` e cole no `.env`. Sem isso o
   sistema ainda funciona (gera uma chave temporária e avisa no log), mas todo mundo perde a
   sessão a cada restart do servidor — não use isso em produção.
5. **Assistente com IA** (opcional): ver seção "Assistente com IA" abaixo.

Rodar localmente:

```bash
uvicorn app.main:app --reload
```

A API sobe em `http://localhost:8000` (endpoints em `/api/...`, `/health` pra checar se subiu).

### Front-end

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Acesse `http://localhost:5173` — a primeira visita redireciona pra `/cadastro`, que só fica
aberta enquanto não existir nenhuma conta (ver seção "Autenticação" abaixo).

> Atenção: `FRONTEND_ORIGIN` no `.env` do **backend** precisa bater exatamente com a URL que
> você acessa o front no navegador (`http://localhost:5173`, e não `127.0.0.1:5173` — são
> origens diferentes pro CORS, mesmo apontando pra mesma máquina).

## Autenticação

Login por token (JWT), cadastro aberto para clientes:

- `POST /api/auth/cadastro` cria contas com **usuário, e-mail e aceite dos termos**. A **primeira
  conta do sistema vira administradora** (e Pro); as demais são clientes e ganham o teste grátis
  do Pro (`TRIAL_DAYS`, padrão 7). Faça o seu cadastro primeiro, antes de divulgar o link.
- Login por usuário **ou e-mail**. Senhas com hash bcrypt. O token JWT vai em
  `Authorization: Bearer <token>` (sem cookie, sem CSRF) e expira em `JWT_EXPIRE_HOURS`.
- Rate limit simples no login: 5 erros seguidos bloqueiam por 5 minutos (em memória).
- Cada cliente enxerga **só os próprios dados** (watchlist, regras, alertas, posições). O dado de
  mercado (cotações, notícias, calendário) é compartilhado.
- O cliente pode **excluir a conta e todos os dados** em `/conta` (LGPD).
- Admin: `/usuarios` lista contas, cria usuários e **libera/rebaixa o Pro à mão** (cliente que
  pagou por fora, cortesia).
- **Ainda não existe "esqueci minha senha"** (precisa de um serviço de e-mail). Até lá, o admin
  recria o acesso.

## Planos e cobrança (Stripe)

| | Free | Pro |
|---|---|---|
| Ativos / regras | `FREE_MAX_SYMBOLS` (3) / `FREE_MAX_RULES` (2) | `PRO_MAX_SYMBOLS` (30) / `PRO_MAX_RULES` (50) |
| Painel, notícias, calendário, posições | sim | sim |
| Telegram, painel de risco, análise matinal, PDF/exportação, assistente e copiloto de IA | não (402) | sim |

IA tem limite diário por usuário (`LLM_DAILY_LIMIT`) para controlar custo. Código em
`app/billing.py`; rotas em `/api/billing/*`.

Para ligar a cobrança:

1. No Stripe, crie um **Produto** com preço **recorrente mensal** e copie o `price_...`.
2. Defina `STRIPE_SECRET_KEY` e `STRIPE_PRICE_ID` no backend (comece com as chaves de **teste**).
3. Crie um **webhook** apontando para `https://SEU_BACKEND/api/billing/webhook` com os eventos
   `checkout.session.completed` e `customer.subscription.created|updated|deleted`, e copie o
   segredo `whsec_...` para `STRIPE_WEBHOOK_SECRET`.
4. Ative o **Customer Portal** no Stripe (é por ele que o cliente cancela e troca o cartão).
5. Teste com o cartão `4242 4242 4242 4242`. Localmente: `stripe listen --forward-to
   localhost:8000/api/billing/webhook`.

`PRO_PRICE_LABEL` é só o texto exibido no site (o valor real é o do preço no Stripe): mantenha os
dois iguais. Sem as chaves, o botão de assinar some e o admin libera o Pro à mão.

### Telegram por cliente

Um único bot atende todos. O cliente Pro gera um código em `/conta` e envia `/vincular CODIGO`
ao bot; a partir daí recebe os próprios alertas e resumos e usa `/add`, `/status`, `/matinal`
etc. na própria watchlist. `TELEGRAM_CHAT_ID` agora só serve para vincular automaticamente o
administrador na primeira migração.

### Migração de bancos antigos

No startup, `app/migrations.py` leva um banco do tempo de usuário único ao modelo novo sem perder
dados: os dados antigos passam a pertencer ao primeiro admin e quem já tinha conta fica no Pro.
Testado em SQLite (`tests/test_migrations.py`); em Postgres a migração é "melhor esforço" e não
foi testada.

## Rodando os testes

Backend:

```bash
pytest
```

Front-end:

```bash
cd frontend
npm run test
```

Backend cobre indicadores técnicos, motor de regras (E/OU), backtest, posições/P&L, dedup,
auth (fluxo JWT completo) e as rotas de API — tudo sem depender de API externa real (LLM é
mockado nos testes). Front-end cobre `AuthContext` (login/logout/persistência de token) e o
hook `useRuleConditions` (montagem do payload de condições da regra composta) — cobertura
pontual, não e2e completo de cada página (validado manualmente, ver "Smoke test" abaixo).

## Uso

1. Acesse `/watchlist` no front (ou use `/add SYMBOL` no bot do Telegram) para cadastrar
   ativos, ex: `AAPL`, `MSFT`, `NVDA`.
2. Para cada ativo, crie regras de alerta na própria tela de watchlist: adicione uma ou mais
   condições (preço acima/abaixo, RSI, cruzamento de médias, MACD, spike de volume, variação %),
   escolha se é "TODAS" (E) ou "QUALQUER" (OU) entre elas, e clique em "Testar regra" pra ver o
   backtest antes de salvar.
3. Registre suas compras/vendas em `/posicoes` pra acompanhar custo médio e P&L — é só um
   registro manual, não afeta nem depende de nenhuma corretora.
4. Use `/assistente` no front (ou `/pergunta <texto>` no Telegram) pra perguntar coisas como
   "por que a AAPL caiu hoje?" — a resposta usa só os dados que o sistema já coletou.
5. O scheduler interno do backend:
   - a cada `QUOTE_POLL_SECONDS` (padrão 60s) busca a cotação atual de cada ativo ativo;
   - a cada `INDICATOR_REFRESH_SECONDS` (padrão 5min) recalcula indicadores e avalia as regras;
   - a cada `NEWS_REFRESH_SECONDS` (padrão 30min) busca notícias novas de cada ativo;
   - todo dia às `CALENDAR_REFRESH_HOUR_UTC` atualiza calendário econômico e de earnings;
   - todo dia às `DAILY_SUMMARY_HOUR_UTC` envia um resumo pelo Telegram (preços + notícias das
     últimas 24h + eventos econômicos de alto impacto do dia + earnings da semana).
6. Quando uma regra dispara: grava no histórico de alertas, aparece no front e é enviado via
   Telegram (respeitando o `cooldown_minutes` de cada regra, pra não spammar).
7. Acesse `/mercado` para ver o painel completo de notícias, calendário econômico e earnings.
8. Baixe um relatório em PDF a qualquer momento pelo botão "Baixar PDF" no front, ou mande
   `/relatorio` para o bot no Telegram — ele gera e envia o PDF na hora, com watchlist, alertas
   recentes, notícias, calendário econômico e earnings.

## Assistente com IA

Usa um LLM só pra **explicar dados que o sistema já coletou**, nunca pra decidir ou executar
nada. Três provedores suportados via `LLM_PROVIDER` no `.env` do backend:

- **`groq`** — grátis, sem cartão de crédito, modelos Llama bem rápidos. Crie a key em
  https://console.groq.com/keys e cole em `GROQ_API_KEY`.
- **`gemini`** — grátis, sem cartão de crédito. Crie a key em
  https://aistudio.google.com/apikey e cole em `GEMINI_API_KEY`. Atenção: contas novas do
  Google às vezes vêm com o projeto associado à key **suspenso** (`CONSUMER_SUSPENDED`) até
  passar por verificação adicional — se isso acontecer, use `groq` ou `anthropic` em vez disso.
- **`anthropic`** — pago (créditos pré-pagos), recomendado quando for pra produção de verdade.
  Crie a key em https://console.anthropic.com e cole em `ANTHROPIC_API_KEY`.

O código dos três é idêntico (mesmos prompts, mesmo comportamento) — só troca o `LLM_PROVIDER`
quando quiser migrar de um pro outro. Sem nenhuma key configurada, o sistema roda normal: o
resumo diário fica em formato de lista simples e o assistente avisa que está desativado.

- **Resumo diário narrativo**: o job `daily_summary` monta os mesmos dados de sempre (preços,
  notícias, eventos econômicos, earnings) e pede pro LLM escrever um parágrafo curto em vez de
  só listar números. Se a API falhar, cai automaticamente pro formato de lista simples — nunca
  quebra o envio do resumo.
- **Chat** (`/assistente` no front, `/pergunta <texto>` no Telegram): responde só com base na
  watchlist/notícias/alertas que já estão no banco. Instruído a dizer "não sei" em vez de
  inventar quando a informação não está disponível, e a nunca recomendar comprar/vender.
- **Contexto nos alertas** (`LLM_ENRICH_ALERTS=true`, desligado por padrão): adiciona uma frase
  de contexto em cada alerta disparado. Fica desligado por padrão porque alertas podem disparar
  com frequência e cada um vira uma chamada de API — ligue só se souber o volume de alertas que
  sua watchlist costuma gerar.

Custo esperado (Groq/Gemini grátis, ou Anthropic Haiku): com uso de baixo volume (1 resumo/dia
+ perguntas ocasionais), fica na faixa de centavos de dólar por mês (ou zero, nos provedores
grátis).

## Deploy 24/7 (grátis / baixo custo)

Dois serviços no **Render** (não pede cartão de crédito no free tier):

### 1. Backend — Web Service (Docker)

1. Crie uma conta grátis em https://render.com (pode entrar com GitHub).
2. Suba este repositório para o GitHub (crie um repo **privado** — `.env` e `frontend/.env`
   não vão junto, estão no `.gitignore`).
3. No painel do Render: **New +** → **Web Service** → conecte o repositório.
4. Environment: **Docker** (ele detecta o `Dockerfile` na raiz automaticamente).
5. Em **Environment Variables**, cole todas as chaves do seu `.env` local (`FINNHUB_API_KEY`,
   `FMP_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SECRET_KEY`, `JWT_EXPIRE_HOURS`,
   provedor de LLM escolhido, etc.) — uma por uma no painel, nunca commitando o arquivo.
   `SECRET_KEY` **precisa** ser fixa aqui (gerada uma vez, colada no painel) — se ficar em
   branco, cada restart gera uma nova e invalida todos os tokens JWT emitidos.
6. Depois de criar o front-end (passo 2 abaixo), volte aqui e configure `FRONTEND_ORIGIN` com a
   URL do site estático do Render (ex: `https://monitor-nasdaq.onrender.com`).
7. Plano **Free**: o serviço "dorme" após ~15 min sem requisições HTTP, e o scheduler interno
   (jobs do APScheduler) só roda enquanto o processo está de pé — no free tier o monitoramento
   não é 100% contínuo. Para monitoramento 24/7 de verdade, migre pro plano **Starter**
   (~US$7/mês), que não dorme.
8. Persistência: o SQLite fica no filesystem do container, que é efêmero no Render — se o
   serviço reiniciar, **contas, assinaturas e dados dos clientes zeram**. Com clientes pagantes
   isso é inaceitável: use um **Render Disk** apontando para o caminho do `DATABASE_URL`
   (ex: `sqlite:////data/nasdaq_monitor.db`) e faça backup dele. O caminho testado é SQLite +
   disco; Postgres exigiria instalar o driver e validar a migração.
9. **Produção para clientes pagantes**: use plano que não durma (Starter ou acima), defina
   `APP_ENV=production` (o app recusa subir sem `SECRET_KEY`), rode **um único processo** (o
   agendador roda dentro dele; mais de um worker duplicaria alertas) e configure o Stripe.

### 2. Front-end — Static Site

> O site tem rotas como `/termos` e `/planos`: o host estático precisa **reescrever tudo para
> `index.html`** (no Render: Redirects/Rewrites, `/*` → `/index.html`, ação *Rewrite*). Defina
> também `VITE_CONTACT_EMAIL` (aparece nos Termos e na Privacidade).

1. No painel do Render: **New +** → **Static Site** → conecte o mesmo repositório.
2. **Root Directory**: `frontend`.
3. **Build Command**: `npm install && npm run build`.
4. **Publish Directory**: `dist`.
5. Em **Environment Variables**, adicione `VITE_API_URL` com a URL do backend (passo 1 acima,
   ex: `https://monitor-nasdaq-api.onrender.com`). **Importante**: essa variável fica embutida
   no build (Vite lê em build time) — se você mudar depois, precisa disparar um novo deploy pra
   valer.
6. Depois do primeiro deploy, copie a URL gerada e cole em `FRONTEND_ORIGIN` no serviço do
   backend (passo 6 da seção anterior), senão o CORS bloqueia tudo.

### Alternativas ao Render

- **Railway**: mesmo fluxo pros dois serviços, mas hoje em dia costuma pedir cartão pra liberar
  o free tier — por isso ficamos com o Render como recomendação principal.
- **Fly.io** (backend) + **Render Static Site / Vercel / Netlify** (front):
  ```bash
  fly launch          # gera fly.toml, escolha "no" para banco gerenciado (usamos SQLite local)
  fly secrets set FINNHUB_API_KEY=... FMP_API_KEY=... TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... SECRET_KEY=... FRONTEND_ORIGIN=...
  fly deploy
  ```
- **VPS próprio** (Oracle Cloud free tier, etc.) pro backend:
  ```bash
  docker compose up -d --build
  ```
  Sobe o backend na porta 8000 com restart automático. Configure um proxy reverso
  (Caddy/Nginx) com HTTPS na frente se for expor publicamente. O front-end (`frontend/dist`,
  gerado por `npm run build`) pode ser servido por qualquer host estático (Nginx, Vercel,
  Netlify, Render Static Site).

## Estrutura do projeto

```
app/                        # backend (API pura)
  main.py                    # FastAPI app + CORS + lifecycle (DB, bot, scheduler)
  config.py                   # variáveis de ambiente
  db.py, models.py, schemas.py
  auth.py                      # hash de senha, JWT, rate limit de login
  indicators.py                 # SMA, EMA, RSI, MACD, Bollinger, volume ratio
  rules_engine.py                # avalia condições/regras (lógica E/OU) contra dados de mercado
  backtest.py                     # roda uma regra contra o histórico antes de salvar
  positions.py                     # custo médio, P&L realizado/não-realizado a partir de transações
  llm_client.py                     # wrapper async multi-provider (Anthropic/Gemini/Groq)
  dedup.py                           # dedup pura de notícias/eventos (testável sem DB/rede)
  scheduler.py                        # jobs periódicos (cotação, regras, notícias, calendários, resumo)
  telegram_bot.py                      # comandos do bot + envio de alertas
  market_data/                          # clientes Finnhub, yfinance e FMP
  reports.py                             # gera o relatório PDF (reportlab)
  routers/                                # auth, watchlist, positions, assistant, reports, api
tests/                                    # testes do backend (indicadores, regras, backtest,
                                            # posições, dedup, API, auth JWT, assistente)

frontend/                   # front-end (SPA)
  src/
    api/client.ts             # fetch wrapper com Authorization: Bearer, trata 401 global
    context/                   # AuthContext (JWT), ToastContext
    components/                 # Navbar, ProtectedRoute, ConfirmModal, CandlestickChart,
                                  # RuleConditionBuilder
    hooks/                       # usePolling, useRuleConditions
    pages/                        # Login, Cadastro, Dashboard, Watchlist, Mercado, Alertas,
                                    # Posicoes, Assistente, Usuarios, AtivoDetalhe
    styles/global.css              # design system (dark theme, tabelas, forms, toasts, chat)
```

## Limitações conhecidas (free tier)

- Dados podem ter alguns minutos de atraso dependendo do plano do Finnhub/yfinance/FMP.
- Finnhub free tier: 60 requisições/minuto — suficiente para uma watchlist pequena/média.
- yfinance é uma biblioteca não-oficial que consome dados públicos do Yahoo Finance; pode
  falhar ocasionalmente se o Yahoo mudar algo — o código já trata erros sem derrubar o serviço.
- Calendário econômico depende da FMP; sem `FMP_API_KEY` configurada essa seção fica vazia mas
  o resto do sistema continua funcionando normalmente.
- Assistente/resumo narrativo dependem de uma API key de LLM configurada; sem ela, tudo cai
  pro comportamento sem IA (sem quebrar nada).
- Backtest é simplificado (não é um motor de backtesting completo): reavalia a regra em janela
  deslizante sobre o histórico do yfinance, não simula slippage/custos/execução real.
- Sem refresh token: expirado o `JWT_EXPIRE_HOURS`, precisa logar de novo — trade-off
  deliberado pra manter a auth simples num app de poucos usuários.
- Sem execução de ordens: qualquer decisão de compra/venda continua manual, feita por você na
  corretora (ex: Exness).
