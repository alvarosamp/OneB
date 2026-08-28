# Linha de base de segurança e operação

## Já aplicado

- JWT Bearer, senha com bcrypt e limitação de tentativas de login.
- CORS restrito a `FRONTEND_ORIGIN`.
- Cabeçalhos de proteção, resposta sem cache para `/api/*` e `X-Request-ID` por requisição.
- Testes, lint, auditoria de dependências, CodeQL e Dependabot automatizados no GitHub.

## Antes do próximo deploy de produção

1. Defina uma `SECRET_KEY` forte e persistente; nunca use a chave efêmera de desenvolvimento.
2. Troque SQLite por PostgreSQL se existir mais de uma instância da API ou do worker.
3. Configure HTTPS obrigatório e HSTS no proxy/serviço de hospedagem.
4. Guarde segredos no cofre do provedor (não em `.env` de produção) e faça rotação periódica.
5. Proteja cadastro público ou crie um fluxo de convites se o serviço não for aberto.
6. Configure alertas para falhas de jobs, dados desatualizados e falhas de autenticação.

## Privacidade e IA

Dados enviados a provedores de LLM devem ser mínimos, sem tokens, senhas ou informação pessoal
desnecessária. Registre finalidade, retenção e base legal antes de atender clientes sob LGPD.
