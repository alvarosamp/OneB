# Publicar o OneB de graça (Vercel + Render + Neon)

Três serviços gratuitos, cada um com uma função:

| Peça | Onde | Por quê |
|---|---|---|
| Site (React) | **Vercel** | Grátis, rápido, HTTPS automático |
| API (Python/FastAPI) | **Render** (plano Free) | Roda o Docker do projeto (`render.yaml`) |
| Banco (PostgreSQL) | **Neon** (plano Free) | Não expira (o Postgres grátis do Render apaga em 30 dias) |

O Vercel repassa tudo que começa com `/api` para o Render (`frontend/vercel.json`). Para o navegador, site e API ficam no mesmo endereço, e o login funciona sem configurar CORS.

Tempo total: uns 20 minutos. Você só precisa de uma conta no GitHub; nas três plataformas, dá para entrar com "Continue with GitHub".

---

## 0. O código precisa estar no GitHub

O Render e o Vercel puxam o código do repositório `alvarosamp/OneB`. Todo o trabalho (seção Brasil, `render.yaml`, `frontend/vercel.json`) precisa estar commitado e enviado (push) para uma branch.

Se o GitHub CLI pedir login de novo:

```bash
gh auth login
```

## 1. Banco no Neon (5 min)

1. Entre em https://neon.tech e clique em **Sign up**, depois em **Continue with GitHub**.
2. Crie um projeto:
   - **Name:** `oneb`;
   - **Postgres version:** 16;
   - **Region:** *AWS US East (N. Virginia)*.
3. Na tela do projeto, clique em **Connect** e copie a **connection string**. Ela começa com `postgresql://` e termina com `?sslmode=require`.
   - Guarde em lugar seguro: ela contém a senha do banco.
   - Não precisa mudar nada nela. O app converte o endereço para o driver certo sozinho.

## 2. API no Render (10 min)

1. Entre em https://render.com e clique em **Get Started**, depois em **GitHub**.
2. No painel, clique em **New +** e escolha **Blueprint**.
3. Conecte o repositório **alvarosamp/OneB** e escolha a branch onde está o código. O Render lê o `render.yaml` e mostra o serviço **oneb-api**.
4. Ele pede os valores marcados como secretos:
   - **DATABASE_URL:** a connection string do Neon;
   - **FRONTEND_ORIGIN:** por enquanto, `https://oneb.vercel.app` (você corrige no passo 4);
   - **ADMIN_BOOTSTRAP_USERNAME:** o seu usuário de admin;
   - **ADMIN_BOOTSTRAP_PASSWORD:** uma senha forte para ele;
   - **FRED_API_KEY:** opcional. É o calendário econômico dos EUA, com chave grátis em fred.stlouisfed.org. Pode deixar vazio.
   - A `SECRET_KEY` é gerada sozinha.
5. Clique em **Apply**. O primeiro deploy leva de 5 a 10 minutos: ele monta o Docker, roda as migrações no Neon e sobe a API.
6. Quando ficar **Live**, abra `https://oneb-api.onrender.com/health`. Deve aparecer `{"status":"ok"}`.

> **Se o endereço não for `oneb-api.onrender.com`** (o nome pode estar ocupado e o Render cria algo como `oneb-api-x1y2.onrender.com`): troque o endereço nas duas linhas de `frontend/vercel.json` e faça push de novo. O teste `tests/test_deploy_config.py` precisa ser ajustado junto, porque ele confere que os dois arquivos combinam.

## 3. Site no Vercel (5 min)

**Opção A, pelo navegador:**

1. Entre em https://vercel.com, clique em **Sign Up** e depois em **Continue with GitHub**.
2. Clique em **Add New…**, escolha **Project** e importe **alvarosamp/OneB**.
3. Em **Root Directory**, clique em **Edit** e escolha **`frontend`**. Esse passo é importante.
4. O resto já vem do `frontend/vercel.json`. Clique em **Deploy**.
5. Anote o endereço gerado, por exemplo `https://oneb-xyz.vercel.app`.

**Opção B, pelo terminal (eu consigo rodar se você fizer só o login):**

```bash
npx vercel login
```

Depois disso, eu rodo `npx vercel --prod` dentro de `frontend/`.

## 4. Ligar um ao outro

1. No Render, abra **oneb-api**, vá em **Environment** e troque **FRONTEND_ORIGIN** pelo endereço real do Vercel. Clique em **Save Changes**; ele reinicia sozinho.
2. Abra o site do Vercel, entre com o usuário admin do passo 2 e vá em **Brasil › Investir**.

## 5. Evitar a "soneca" (opcional, recomendado)

No plano grátis, a API do Render dorme depois de 15 minutos sem visitas. A primeira visita depois disso leva de 30 a 60 segundos e pode dar erro uma vez (é só recarregar). Para manter acordada:

1. Crie uma conta grátis em https://uptimerobot.com.
2. Clique em **New monitor**, escolha **HTTP(s)** e use a URL `https://oneb-api.onrender.com/health`, com intervalo de **5 minutos**.

As 750 horas grátis por mês do Render cobrem um serviço ligado o mês inteiro.

## Atualizações

Cada `git push` na branch escolhida republica o Render e o Vercel sozinhos.

## Limites do plano grátis (para não ter surpresa)

- **Memória de 512 MB no Render.** O app usa pandas e numpy e deve caber, mas se aparecer "Out of memory" nos logs, o próximo passo é o plano Starter (US$ 7/mês) ou a Hostinger.
- **Sem worker.** O job que grava o placar ao vivo de hora em hora (`python -m app.worker`) não roda no plano grátis. As telas funcionam, mas o placar ao vivo não avança. O agendador embutido (notícias, calendário, relatórios) roda enquanto a API está acordada.
- **Disco temporário.** O cache de cotações some a cada deploy e é refeito sozinho. Os dados ficam no Neon.
- **Neon grátis:** 0,5 GB, mais do que suficiente para começar.
- **Telegram e IA (Anthropic):** só funcionam se você adicionar as chaves em **Environment** no Render (`TELEGRAM_BOT_TOKEN`, `ANTHROPIC_API_KEY`).

A publicação completa, com worker e sem soneca, continua sendo a da Hostinger (`HOSTINGER.md`).
