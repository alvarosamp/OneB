# OneB Market

Sistema de **monitoramento e alerta** (não executa ordens) para uma watchlist de ativos de
mercado: ações, ETFs, índices, commodities e instrumentos macro acompanhados como contexto.
Acompanha preço/volume, calcula indicadores técnicos (SMA, EMA, RSI, MACD, Bollinger,
volume médio) e dispara alertas configuráveis via **Telegram** e num **dashboard web**.

> ⚠️ Ferramenta de apoio à decisão. Não é recomendação de investimento, não executa ordens de
> compra/venda e usa dados de fontes gratuitas que podem ter atraso. Sempre valide antes de
> operar de verdade (ex: na Exness ou outra corretora).

Inclui também um **painel de mercado** com notícias por ativo, calendário econômico,
ouro, câmbio, juros, índices e calendário de earnings, **regras de alerta compostas** (E/OU) com backtest antes de salvar,
**posições/P&L** manuais, e um **assistente com IA** que explica os dados coletados (nunca
recomenda comprar/vender).

## Arquitetura

Backend e front-end são **dois serviços separados**:

- **Backend** (`app/`): FastAPI, API REST pura (JSON), autenticação por **JWT** (Bearer token,
  sem cookie de sessão), SQLite + APScheduler + bot do Telegram.
- **Front-end** (`frontend/`): **React + TypeScript + Vite**, um SPA que consome o backend via
  `fetch`. Mantém o access token (curto) apenas em memória e manda em
  `Authorization: Bearer <token>`; a sessão persiste por um cookie httpOnly de refresh que o
  JavaScript não consegue ler.

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

### Fonte de histórico: Tiingo EOD + fallback yfinance

O projeto pode usar `TIINGO_API_KEY` com `MARKET_DATA_PROVIDER=tiingo` para histórico EOD diário
ajustado por splits/dividendos, recomendado para indicadores, backtests e pesquisa. O `yfinance`
continua como fallback, especialmente para intervalos intraday como `15m`, que não fazem parte do
endpoint EOD da Tiingo. O health operacional mostra o provedor ativo, se a Tiingo está configurada
e se há cache de dados em `/api/operations/health`.

Mais detalhes: `docs/data_tiingo_integration.md`.

### Por que não Investing.com?

O Investing.com não oferece API pública. O único jeito de puxar dados de lá programaticamente
é via scraping não-oficial (bibliotecas como `investiny`), o que viola os termos de uso do site
e quebra sem aviso quando eles mudam o HTML — não é uma base confiável para algo que o pai do
seu amigo vai usar de verdade. Por isso, cotações/notícias/calendário econômico vêm de APIs
oficiais (Finnhub + FMP), que cobrem a mesma necessidade com estabilidade e dentro do free tier.

## Requisitos

| Componente          | Suportado                                  |
|---------------------|--------------------------------------------|
| Python              | 3.11–3.12 (testados no CI)                 |
| Node.js             | 22 (Vite atual exige 20.19+ ou 22.12+)     |
| Docker Compose      | v2                                          |
| Banco (dev)         | SQLite (padrão, sem configuração)          |
| Banco (produção)    | PostgreSQL via `docker-compose.prod.yml`   |

## Setup local

### Docker separado

Para rodar os processos separados em desenvolvimento:

```bash
copy .env.example .env
docker compose up --build
```

ServiÃ§os:

- `api`: FastAPI em `http://localhost:8000`, sem scheduler embutido.
- `worker`: scheduler, coleta de dados, bots e resumos Telegram.
- `frontend`: Vite em `http://localhost:5173`.

### ProduÃ§Ã£o com Docker Compose

O ambiente de produÃ§Ã£o publica somente o Nginx. Ele serve o SPA e encaminha `/api` para o
FastAPI pela rede interna. PostgreSQL, API, worker e simulador nÃ£o expÃµem portas ao host.

```bash
cp .env.production.example .env.production
# edite .env.production, ajuste DOMAIN/FRONTEND_ORIGIN e substitua todos os CHANGE_ME
docker compose --env-file .env.production -f docker-compose.prod.yml config --quiet
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

No Windows PowerShell, use `Copy-Item .env.production.example .env.production` no primeiro comando.
Na VPS, o Caddy publica as portas 80/443, obtÃ©m e renova o certificado TLS automaticamente e
encaminha o trÃ¡fego para o frontend. O registro A do `DOMAIN` precisa apontar para a VPS antes
do primeiro boot. Os dados do PostgreSQL ficam no volume `pgdata`; modelos, caches e estado do
simulador ficam em `appdata`.

Para acompanhar o primeiro deploy:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f migrate api frontend caddy
```

O serviÃ§o `migrate` aplica o Alembic e precisa terminar com cÃ³digo 0 antes dos demais processos.
O `worker` Ã© o Ãºnico processo que roda automaÃ§Ãµes; nÃ£o o escale, pois isso duplicaria alertas,
coletas e mensagens. Libere TCP 80/443 e UDP 443 no firewall da VPS. Configure `DOMAIN` sem
protocolo e `FRONTEND_ORIGIN` com `https://`; o cookie de refresh Ã© `Secure` em produÃ§Ã£o.

Backup bÃ¡sico do banco:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T db \
  pg_dump -U oneb -d oneb -Fc > oneb.dump
```

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

Acesse `http://localhost:5173` — a primeira visita redireciona pra `/cadastro`, onde qualquer
usuário pode criar conta e entrar em seguida (ver seção "Autenticação" abaixo).

> Atenção: `FRONTEND_ORIGIN` no `.env` do **backend** precisa bater exatamente com a URL que
> você acessa o front no navegador (`http://localhost:5173`, e não `127.0.0.1:5173` — são
> origens diferentes pro CORS, mesmo apontando pra mesma máquina).

## Autenticação

Sessão em duas partes: um **access token** curto que vive só em memória do navegador e um
**refresh token** de 30 dias num cookie `HttpOnly`.

- **Cadastro aberto**: `POST /api/auth/cadastro` cria a conta e já devolve um token para entrar.
  O cadastro público **nunca** concede admin. (Antes, a primeira conta criada virava
  administradora — num deploy publicado antes de você se cadastrar, qualquer visitante que
  chegasse primeiro ganhava controle total.)
- **Primeiro admin**: preencha `ADMIN_BOOTSTRAP_USERNAME` e `ADMIN_BOOTSTRAP_PASSWORD` no `.env`.
  Essa conta é criada como admin no startup, **somente enquanto o banco não tiver nenhum
  usuário**. Depois disso, promova alguém com `python -m scripts.promote_admin <usuario>`.
- Admins podem criar contas e escolher permissão de admin na tela `/usuarios`.
- Senhas ficam com hash bcrypt (nunca em texto plano).
- **Access token**: JWT de `ACCESS_TOKEN_EXPIRE_MINUTES` (padrão 15 min), guardado apenas em
  memória pelo SPA — nunca em `localStorage`, porque web storage é legível por qualquer XSS.
- **Refresh token**: string opaca de `REFRESH_TOKEN_EXPIRE_DAYS` (padrão 30) em cookie
  `HttpOnly`, `SameSite=Strict`, `Secure` quando `ENVIRONMENT=production`, guardada no banco
  apenas como hash SHA-256. É rotacionada a cada uso; se um token já rotacionado reaparecer
  (sinal de credencial copiada), a família inteira é revogada.
- O front renova o access token em silêncio quando ele expira — na prática você não é
  deslogado no meio do uso, e o `logout` revoga a sessão **no servidor**.
- As duas rotas autenticadas por cookie (`/api/auth/refresh` e `/api/auth/logout`) exigem o
  header `X-Refresh-Request`, o que fecha o vetor de CSRF que o cookie reintroduziria.
- Rate limit no login: 5 tentativas erradas em 5 minutos bloqueiam o usuário. O contador é
  **persistido no banco** (tabela `login_attempts`), então sobrevive a restart/redeploy e vale
  para todas as réplicas.
- **Esqueci minha senha**: não há e-mail configurado, então a redefinição é administrativa —
  um admin usa `POST /api/auth/usuarios/{id}/senha`, ou, se ninguém tiver acesso de admin,
  `python -m scripts.reset_password <usuario>`. O usuário **não** é recriado: o `id` é
  referenciado por watchlist, posições, alertas e histórico, e recriar a conta descartaria
  tudo isso. Trocar a senha derruba todas as sessões ativas daquele usuário.

Detalhes do modelo de ameaça, runbook de vazamento e canal de reporte: [`SECURITY.md`](SECURITY.md).

## Migrations do banco

Em desenvolvimento (SQLite) o schema é criado no boot direto a partir dos modelos — nada a fazer.
Em produção, o schema é versionado com Alembic:

```bash
alembic upgrade head      # aplica as migrations pendentes
alembic downgrade -1      # volta uma migration
alembic revision --autogenerate -m "descricao"   # depois de mudar app/models.py
```

O `docker-compose.prod.yml` roda `alembic upgrade head` num serviço `migrate` que precisa
terminar com sucesso antes de API, worker e simulador subirem.

## Rodando os testes

Backend:

```bash
pytest
```

Validacao do simulador com dados reais do Yahoo Finance:

```bash
python scripts/run_simulation_validation.py
```

No Docker:

```bash
docker compose up --build -d
docker compose exec api python scripts/run_simulation_validation.py
docker compose logs -f paper-simulator
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
   - em dias úteis, às `MACRO_INTELLIGENCE_HOUR_UTC` (padrão 23h UTC), atualiza os históricos
     macro e persiste tendências, correlações, mudanças de regime e hipóteses de antecedência;
   - todo dia às `CALENDAR_REFRESH_HOUR_UTC` atualiza calendário econômico e de earnings;
   - todo dia às `DAILY_SUMMARY_HOUR_UTC` envia um resumo pelo Telegram (preços + notícias das
     últimas 24h + eventos econômicos de alto impacto do dia + earnings da semana).
6. Quando uma regra dispara: grava no histórico de alertas, aparece no front e é enviado via
   Telegram (respeitando o `cooldown_minutes` de cada regra, pra não spammar).
7. Acesse `/mercado` para ver o painel completo de notícias, calendário econômico e earnings.
8. Baixe um relatório em PDF a qualquer momento pelo botão "Baixar PDF" no front, ou mande
   `/relatorio` para o bot no Telegram — ele gera e envia o PDF na hora, com watchlist, alertas
   recentes, notícias, calendário econômico e earnings.

### Modo simulacao confiavel

O Docker sobe tambem o servico `paper-simulator`, que roda uma carteira ficticia de **US$200** em
segundo plano. Ele nao envia ordem real. A cada ciclo ele:

1. busca historico OHLCV pelo Yahoo Finance via `yfinance`;
2. recalibra filtros tecnicos com RSI, medias, MACD, volume, ATR e volatilidade;
3. mede falsos positivos olhando o retorno dos 5 pregoes seguintes em sinais historicos;
4. so permite compra se a precisao historica for pelo menos 58% e o retorno medio for positivo;
5. compra apenas acoes inteiras que caibam no caixa, sem alavancagem;
6. gerencia posicoes com stop de 1 ATR, alvo de 2 ATR e saida por virada de tendencia.

Arquivos para acompanhar:

- `data/paper_simulator_events.jsonl`: calibracoes, decisoes, compras, vendas, stops e motivos de espera.
- `data/paper_simulator_state.json`: caixa, posicoes abertas e trades fechados.
- `data/simulation_validation_report.json`: relatorio gerado pelo comando de validacao.

Uma resposta `NO_TRADE` pode ser a decisao correta. Se o filtro historico ficar abaixo do minimo
de confianca, o simulador preserva o caixa em vez de forcar uma entrada.

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
   `FMP_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SECRET_KEY`, `ENVIRONMENT=production`,
   provedor de LLM escolhido, etc.) — uma por uma no painel, nunca commitando o arquivo.
   `SECRET_KEY` **precisa** ser fixa aqui (gerada uma vez, colada no painel) — se ficar em
   branco, cada restart gera uma nova e invalida todos os tokens JWT emitidos.
6. Depois de criar o front-end (passo 2 abaixo), volte aqui e configure `FRONTEND_ORIGIN` com a
   URL do site estático do Render (ex: `https://oneb-market.onrender.com`).
7. Plano **Free**: o serviço "dorme" após ~15 min sem requisições HTTP, e o scheduler interno
   (jobs do APScheduler) só roda enquanto o processo está de pé — no free tier o monitoramento
   não é 100% contínuo. Para monitoramento 24/7 de verdade, migre pro plano **Starter**
   (~US$7/mês), que não dorme.
8. Persistência: o SQLite fica no filesystem do container, que é efêmero no Render — se o
   serviço reiniciar, **o histórico de preços/alertas E as contas de usuário/senha zeram** (o
   cadastro reabre sozinho, o que é seguro mas incômodo). Pra persistir de verdade, adicione um
   **Render Disk** (storage persistente, custo baixo) apontando pro caminho do `DATABASE_URL`,
   ou migre para o Render Postgres (free tier disponível) trocando `DATABASE_URL` — o
   SQLAlchemy já suporta ambos sem mudar código. Recomendo fortemente configurar isso antes de
   considerar o deploy "definitivo".

### 2. Front-end — Static Site

1. No painel do Render: **New +** → **Static Site** → conecte o mesmo repositório.
2. **Root Directory**: `frontend`.
3. **Build Command**: `npm install && npm run build`.
4. **Publish Directory**: `dist`.
5. Em **Environment Variables**, adicione `VITE_API_URL` com a URL do backend (passo 1 acima,
   ex: `https://oneb-market-api.onrender.com`). **Importante**: essa variável fica embutida
   no build (Vite lê em build time) — se você mudar depois, precisa disparar um novo deploy pra
   valer.
6. Depois do primeiro deploy, copie a URL gerada e cole em `FRONTEND_ORIGIN` no serviço do
   backend (passo 6 da seção anterior), senão o CORS bloqueia tudo.

### Front-end no Vercel

O front-end (`frontend/`) é uma SPA Vite/React pura — encaixa bem no Vercel. O backend
(FastAPI + APScheduler + SQLite + bot do Telegram) **não** roda no Vercel (é um processo
persistente com jobs em background, incompatível com funções serverless); ele continua num
serviço à parte (Render, Fly.io, VPS — ver seção anterior).

1. Crie uma conta grátis em https://vercel.com (pode entrar com GitHub) e suba este
   repositório para o GitHub primeiro (repo **privado** — `.env` não vai junto, já está no
   `.gitignore`).
2. No painel do Vercel: **Add New** → **Project** → importe o repositório.
3. **Root Directory**: `frontend` (existe um `frontend/vercel.json` já configurado com o
   rewrite de SPA — sem ele, atualizar a página em qualquer rota tipo `/mesa-ia` dá 404).
   O Vercel detecta o preset Vite automaticamente (`npm run build`, saída em `dist`).
4. Em **Environment Variables**, adicione `VITE_API_URL` apontando pro backend (ex:
   `https://oneb-market-api.onrender.com`). **Importante**: essa variável é lida em build
   time pelo Vite — mudar depois exige um novo deploy (Vercel → Deployments → Redeploy).
5. Depois do primeiro deploy, copie a URL gerada (ex: `https://seu-projeto.vercel.app`) e
   cole em `FRONTEND_ORIGIN` no serviço do backend, senão o CORS bloqueia as chamadas da API.
6. Deploys automáticos: todo push na branch principal do GitHub gera um novo deploy sozinho.

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
- Sem e-mail transacional: a redefinição de senha é administrativa (ver "Autenticação"),
  não existe fluxo de "esqueci minha senha" self-service.
- O worker é singleton por convenção de deployment: os `job_defaults` do APScheduler
  (`max_instances`, `coalesce`) evitam sobreposição **dentro** de um processo, mas subir dois
  workers ainda duplicaria alertas e coletas. Não escale esse serviço.
- Sem execução de ordens: qualquer decisão de compra/venda continua manual, feita por você na
  corretora (ex: Exness).

## Licença

Apache License 2.0 — ver [`LICENSE`](LICENSE).
