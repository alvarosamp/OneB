# Site público no Vercel

O deploy da raiz usa `serverless:app`, compila o frontend e registra `frontend/dist`
com `app.frontend()` para publicar os arquivos pelo CDN. Site e `/api` ficam no
mesmo domínio, sem Render. A promoção ao CDN é explícita porque a API tem middleware.

Este é um modo público de consulta, com visitante sem privilégios de administrador.
O banco é novo, temporário e exclusivo de cada instância: nenhuma conta ou carteira
real é carregada. Aulas e conteúdo inicial são preparados no início da instância.
Consultas e o simulador Brasil funcionam sem login; gravações, progresso, cadastro,
chamadas pagas de IA e administração ficam indisponíveis. O aviso aparece no site.

O scheduler e o bot contínuos não rodam em Functions. Caches de cotações usam `/tmp`.
O resumo técnico consulta os preços sob demanda, com cache de 5 minutos. A tela
consulta o resumo a cada 5 minutos enquanto visível, ao voltar à aba e ao recuperar
a conexão. Sem visitas, não há coleta contínua. `data_checked_at` informa a consulta
à fonte e `data_as_of` o pregão base; `generated_at` é apenas a montagem do texto.
Falhas da fonte, base antiga e ausência de notícias/calendário são indicadas na tela.
Esses dados podem desaparecer entre invocações. Um serviço persistente e um banco
externo continuam necessários para contas pessoais, histórico e tarefas contínuas.

O deploy autenticado original continua disponível com `app.main:app` e as próprias
variáveis de ambiente. Nunca use o modo público para conectar um banco pessoal.

Validação: `python -m pytest tests/test_vercel_public.py tests/test_brasil.py` e
`npm run build --prefix frontend`. Para publicar, use a raiz do repositório e o
projeto `nasdaq` na equipe `teste-tor-s-projects`.
