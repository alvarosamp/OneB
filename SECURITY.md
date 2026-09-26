# Política de segurança

## Versões suportadas

Correções de segurança são aplicadas apenas na branch `master`. Não há releases
mantidas em paralelo.

## Como reportar uma vulnerabilidade

**Não abra uma issue pública.** Use o canal privado do GitHub em
*Security → Report a vulnerability* neste repositório. Inclua:

- descrição do problema e impacto esperado;
- passos de reprodução (ou PoC mínima);
- versão/commit testado.

Expectativa de resposta: confirmação em até 5 dias úteis; correção ou plano de
mitigação acordado antes de qualquer divulgação pública.

## O que conta como problema de segurança

Elevação de privilégio (virar admin sem autorização), acesso a dados de outro
usuário, roubo ou reuso de sessão, execução remota de código, injeção (SQL, comando,
template), SSRF através dos clients de market data, e vazamento de segredos em
logs, respostas de erro ou artefatos de build.

Não contam: falta de rate limit em endpoints públicos de leitura, ausência de
headers considerados "nice to have", e resultados de scanner sem impacto demonstrável.

## Modelo de segurança da aplicação

**Contas e privilégios**

- O cadastro público (`POST /api/auth/cadastro`) é aberto, mas **nunca** concede
  `is_admin`. Antes, a primeira conta criada virava administradora — num deploy
  publicado antes do dono se cadastrar, qualquer visitante ganhava controle total.
- O admin inicial vem de `ADMIN_BOOTSTRAP_USERNAME` / `ADMIN_BOOTSTRAP_PASSWORD`,
  aplicados no startup **somente enquanto o banco não tiver nenhum usuário**.
- Promoções posteriores exigem acesso ao banco: `python -m scripts.promote_admin <usuario>`.

**Sessão**

- *Access token*: JWT curto (`ACCESS_TOKEN_EXPIRE_MINUTES`, padrão 15 min), devolvido
  no corpo da resposta e mantido **apenas em memória** pelo SPA. Não vai para
  `localStorage`: um XSS lê web storage, e o modelo anterior (JWT de 7 dias em
  `localStorage`) significava roubar uma credencial de uma semana, irrevogável.
- *Refresh token*: string opaca de 30 dias em cookie `HttpOnly`, `SameSite=Strict`,
  `Secure` quando `ENVIRONMENT=production`, com `path=/api/auth`. No banco fica só o
  hash SHA-256 — um dump não devolve credenciais utilizáveis.
- Rotação a cada uso, com **detecção de reuso**: se um token já rotacionado
  reaparecer, toda a família é revogada e o dono precisa logar de novo.
- `POST /api/auth/logout` revoga a família inteira no servidor.
- As duas rotas autenticadas por cookie (`/refresh`, `/logout`) exigem o header
  `X-Refresh-Request` — um site atacante não consegue definir header customizado
  cross-site, o que fecha o vetor de CSRF que o cookie reintroduziria.

**Força bruta**

Cinco falhas por usuário em 5 minutos bloqueiam novas tentativas. O contador é
persistido na tabela `login_attempts`, então sobrevive a restart/redeploy e vale para
todas as réplicas — antes vivia num dicionário em memória e zerava a cada reinício.

**Segredos**

`SECRET_KEY` é obrigatória quando `ENVIRONMENT=production`: sem ela o processo
**não sobe**. Em desenvolvimento, uma chave efêmera é gerada com aviso.

## Runbook: suspeita de vazamento de credenciais

1. Revogar o token do bot no @BotFather (`TELEGRAM_BOT_TOKEN`).
2. Revogar e reemitir as chaves de provider (Finnhub, FMP, Tiingo, FRED).
3. Trocar as credenciais de LLM (Anthropic/Gemini/Groq).
4. Gerar nova `SECRET_KEY`
   (`python -c "import secrets; print(secrets.token_hex(32))"`) — isso invalida todos
   os access tokens em circulação.
5. `DELETE FROM refresh_tokens;` — derruba todas as sessões ativas.
6. Auditar `users` (`SELECT username, is_admin, created_at FROM users ORDER BY created_at`)
   procurando admins inesperados.
7. Auditar `login_attempts` em busca de rajadas de tentativas.
8. Redeploy e rotação do `.env` em todos os ambientes.

## Recuperação de senha

Não existe fluxo de "esqueci minha senha" por e-mail. A redefinição é administrativa:
um admin (ou quem tem acesso ao banco) troca o `password_hash` do usuário existente.
**Não recrie o usuário** — o `id` é referenciado por watchlist, posições, alertas e
histórico, e recriar a conta descarta esse histórico silenciosamente.
