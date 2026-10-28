# Site público no Vercel

O deploy da raiz usa `serverless:app`, compila o frontend e serve os arquivos de
`public/` pelo CDN. Site e `/api` ficam no mesmo domínio, sem Render.

Este é um modo público de consulta, com visitante sem privilégios de administrador.
O banco é novo, temporário e exclusivo de cada instância: nenhuma conta ou carteira
real é carregada. Aulas e conteúdo inicial são preparados no início da instância.
Consultas e o simulador Brasil funcionam sem login; gravações, progresso, cadastro,
chamadas pagas de IA e administração ficam indisponíveis. O aviso aparece no site.

O scheduler e o bot contínuos não rodam em Functions. Caches de cotações usam `/tmp`.
Esses dados podem desaparecer entre invocações. Um serviço persistente e um banco
externo continuam necessários para contas pessoais, histórico e tarefas contínuas.

O deploy autenticado original continua disponível com `app.main:app` e as próprias
variáveis de ambiente. Nunca use o modo público para conectar um banco pessoal.

Validação: `python -m pytest tests/test_vercel_public.py tests/test_brasil.py` e
`npm run build --prefix frontend`. Para publicar, use a raiz do repositório e o
projeto `nasdaq` na equipe `teste-tor-s-projects`.
