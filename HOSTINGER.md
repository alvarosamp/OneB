# Deploy Hostinger: OneB Market

Cole compose.hostinger.yaml no editor Compose e hostinger.env no campo de variaveis.
Nao exige upload de codigo, build, env_file, bind mount ou Caddyfile.
Projeto: oneb-hostinger-01a10dab. Porta HTTP padrao: 18087.
Volumes e rede recebem o prefixo exclusivo do projeto pelo Docker Compose.

Acesse http://IP_DA_VPS:18087/login. Libere TCP 18087 no firewall.
A porta foi verificada neste computador; a disponibilidade na VPS deve ser conferida no painel.
O administrador admin_oneb nasce automaticamente no banco vazio. A senha esta em hostinger.env.
Cadastro publico em /cadastro cria somente usuarios comuns.
Depois do primeiro boot, apague os valores ADMIN_BOOTSTRAP_USERNAME e ADMIN_BOOTSTRAP_PASSWORD
no painel e aplique novamente: o usuario ja persistido continua funcionando.
Nao remova os volumes ao atualizar. Nao escale worker ou paper-simulator.

Para HTTPS, configure um proxy TLS no painel apontando para o frontend, defina
FRONTEND_ORIGIN=https://seu-dominio e REFRESH_COOKIE_SECURE=true.
No acesso HTTP por IP, mantenha REFRESH_COOKIE_SECURE=false; trafego e credenciais
nao sao criptografados. Cookies continuam HttpOnly/SameSite=Strict, com rotacao,
header obrigatorio e verificacao de origem nas operacoes de escrita.

## Componentes preservados
- React/Vite compilado, servido pelo Nginx e proxy /api na mesma origem.
- FastAPI: auth, watchlist, alertas, posicoes, PDF, assistente, mesas tecnicas/IA,
  SaaS/clientes, cursos/progresso, lives, perfil, mercado e operacoes.
- PostgreSQL 16, com migracoes Alembic antes dos processos.
- Worker unico: APScheduler, coletas, bots, resumos e rotinas de modelos.
- Simulador de carteira em processo separado, sem ordens reais.
- Volume appdata para caches/modelos/estado; pgdata para dados relacionais.
Nao existe CRM, Redis, fila ou armazenamento S3 separado no projeto.
Dados locais/clientes/modelos existentes nao sao transportados; ambiente novo inicia vazio.
Ferramentas de pesquisa MetaTrader/Windows exigem seu ambiente original e nao executam no Linux.

## Imagens finais publicadas
alvarocareli/oneb-hostinger-01a10dab-api:20261005-01a10dab-v2
alvarocareli/oneb-hostinger-01a10dab-web:20261005-01a10dab-v2
Arquitetura linux/amd64. A tag v1 do frontend foi substituida no Compose pela v2 corrigida.

## Validacao
Compose config, PostgreSQL e migracoes; bootstrap admin; login/cadastro/privilegios;
refresh/rotacao/logout; bloqueio de origem e header CSRF; frontend e API por localhost
 e IP 192.168.0.123:18087; navegador Edge com login/reload/cookie HttpOnly;
watchlist, criacao/listagem de regras, transacoes, segmentos SaaS/plano, progresso de aulas
 (conclusao/persistencia/desfazer), cursos/lives/perfil/dashboard e PDF.
97 testes backend passaram com as dependencias da imagem; 93 testes frontend passaram.
Worker coletou e gravou 10 instrumentos macro. Imagem limpa auditada sem env/banco/chaves.
Manifests e todas as camadas acessiveis com token anonimo do registry Docker Hub.

## Limites
Nao ha acesso ao painel/VPS para testar firewall, recursos, porta remota ou deploy real.
Credenciais de Finnhub/Tiingo/FMP/FRED/Groq/Gemini e token Telegram foram copiados do .env local
 por solicitacao do usuario. ANTHROPIC_API_KEY e TELEGRAM_CHAT_ID continuam vazios como no arquivo local.
 A configuracao completa passou em compose config; nao foram feitas chamadas ou mensagens com essas credenciais.
Yahoo gratuito depende de disponibilidade/limites externos. Simulador e treinos podem demorar.
O npm ci reportou 7 vulnerabilidades de dependencias (3 moderadas, 4 altas); atualizacao
 dessas dependencias exige validacao separada. Elas nao impediram build ou testes.

O ciclo completo do simulador com historico remoto e treinos nao terminou durante a
janela de validacao; foram confirmados processo e escrita de eventos de inicializacao.

25 testes adicionais locais de simulador, provedores de dados e assistente passaram.
Stack temporaria oneb-validation-01a10dab removida com seus dois volumes e rede.

O hostinger.env inclui todos os campos atuais de app/config.py e ajustes do simulador,
 com valores locais quando existentes e defaults do codigo nos demais. SECRET_KEY e
 credenciais PostgreSQL/admin permanecem exclusivas do ambiente Hostinger.
JWT_EXPIRE_HOURS local foi omitido: o codigo atual usa ACCESS_TOKEN_EXPIRE_MINUTES.
