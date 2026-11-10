# Plano de melhoria — Monitor NASDAQ + pesquisa

Documento de continuidade (escrito em 2026-11-02) para retomar o trabalho em outra máquina.

## 1. Objetivo

Produto no estilo "plataforma de análise com IA" que ajude o usuário a decidir sobre compra, venda e saída. A pesquisa mostrou que **não há previsão confiável com dados gratuitos**, então o produto honesto é um **monitor de risco e disciplina** com **registro público de sinais**, sem prometer certeza. O app nunca recomenda compra ou venda: ele explica dados.

## 2. O que a pesquisa concluiu (detalhes em `output/research/RESULTADOS.md`)

- Indicadores técnicos, ML e rede neural, macro/VIX, revisões de analistas, resultados trimestrais e compras/vendas de insiders (SEC Form 4): **nenhum bateu comprar e segurar com significância** (|t| > ~2,8 e efeito mantido no teste 2021+).
- O que se repete é **redução de risco**: filtro de tendência (SMA50/200), vol-alvo de 15% e stop de 3 ATR cortam a queda máxima de ~-36% para ~-15% a -26%, com retorno parecido.
- Risco de evento: o ativo se mexe ~3x o normal no dia de resultados.
- Sentimento de notícias: **piloto inconclusivo** (6 dias de dados). Ainda é o único teste aberto.
- Limitações: viés de sobrevivência (universo = vencedores de hoje), sem dados de empresas que saíram do mercado.
- Convenções do backtest: sinal no fechamento de t, execução na abertura de t+1, custo de 10 bps por lado, long-only, treino até 2020 e teste de 2021 em diante.

## 3. O que já existe no código

| Área | Onde |
|---|---|
| Correlação, regimes, eventos | `app/research/{correlation,regimes,events,service}.py` |
| Laboratório de backtest e estratégias | `app/research/{lab,strategies,features}.py`, `scripts/research_*.py` |
| Painel de risco por ativo | `app/research/risk_panel.py`, `GET /api/research/panel/{symbol}` |
| Arquivo de manchetes (coleta a cada 6 h) | `app/research/news_archive.py`, job `archive_news` |
| Sentimento (léxico + LLM opcional) | `app/research/sentiment.py`, `scripts/research_sentiment.py` |
| Dados externos (FRED, analistas, insiders SEC) | `app/research/{external,insiders}.py` |
| Registro de sinais em tempo real (append-only) | `app/research/signal_log.py`, job `log_signals`, `GET /api/research/signals` |
| Páginas | `frontend/src/pages/{Pesquisa,Analise}.tsx`, `components/RiskPanelCard.tsx` |

Testes: backend 121 (pytest) e front 14 (vitest).

## 4. Retomar em outra máquina

```bash
git fetch origin && git checkout plano-melhorias
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-research.txt
cp .env.example .env     # preencher; ver abaixo
cd frontend && npm install
```

- `data/` está no `.gitignore`. **Preços** se recriam com `store.update(symbol)` (yfinance). **Insiders**: `python scripts/fetch_insiders.py` (131 MB, precisa de `SEC_USER_AGENT` com nome e e-mail reais no `.env`; não commite o e-mail).
- **Não se recriam**: o arquivo de manchetes (`data/news/archive.csv`) e o registro de sinais. O registro de sinais foi versionado em `data/signals/log.csv`. Copie `data/news/` da máquina antiga, senão o teste de sentimento recomeça do zero.
- O agendador só acumula dados com o app ligado. Deixe-o rodando em uma máquina só, para não ter dois registros diferentes.
- Se a máquina nova for o único lugar com o registro, faça backup dele; é a prova auditável do produto.

## 5. Plano, por prioridade

**P0 — destravar o que já está montado**
1. Colocar `ANTHROPIC_API_KEY` no `.env` e rodar `python scripts/research_sentiment.py` (hoje só o léxico foi testado).
2. Manter a coleta de manchetes e o `log_signals` rodando por 3 a 6 meses.
3. Resolver a divergência de `master` com o remoto (ver seção 6).

**P1 — produto**
4. ~~Página pública~~ feita em `/publico` (placar do registro de sinais, sem login; `GET /api/public/track-record`). Falta: análise por ticker na versão pública e acabamento visual.
5. Abrir `/analise` no navegador e ajustar o visual (só foi validada por testes e tipos).
6. Mostrar o intervalo de incerteza e o período medido ao lado do placar.
7. Backup/exportação do registro de sinais.

**P2 — pesquisa**
8. Teste de sentimento vs retorno quando houver meses de arquivo: critério |t| > ~2,8 e efeito mantido fora da amostra.
9. Se algum sinal passar, testar dados pagos (ver seção 7) com o mesmo protocolo.
10. Incluir uma carteira de ETFs (sem viés de sobrevivência) no registro de sinais.

**P3 — regulação**
11. Antes de cobrar de clientes: confirmar com um advogado a regra da CVM (analista/consultor) e os termos de uso. Não verificado.

## 5b. Andamento (2026-11-09)

- Registro de sinais com 2 fechamentos (60 linhas); sentimento (léxico) com 12 dias de sinal: ainda inconclusivo (o t vem de poucos dias agrupados). Sem `ANTHROPIC_API_KEY` o teste com LLM não rodou.
- Verificação visual no navegador segue bloqueada: o preview do backend não consegue ler `.venv/pyvenv.cfg` (sandbox). Rode `uvicorn` e `npm run dev` à mão.
- `npx tsc --noEmit` não checa nada neste projeto (tsconfig com referências); use `npx tsc -b`. Erro antigo conhecido em `AnaliseMatinal.tsx` ('today' sem uso).

## 5c. MVP vendável (2026-11-09)

Feito: multiusuário (dados isolados por conta, cadastro aberto com e-mail e aceite dos termos),
planos Free/Pro com limites e teste grátis, cobrança Stripe (checkout, portal, webhook), Telegram
por cliente (`/vincular`), landing, `/planos`, `/conta` (excluir conta), termos e privacidade,
migração do banco antigo. Detalhes e passo a passo do Stripe no README.

Falta antes de cobrar (nada disso dá para resolver só com código):
- Revisão jurídica dos Termos/Privacidade e do enquadramento CVM (P3 acima). Os textos são modelo.
- Criar produto/preço/webhook no Stripe e testar o fluxo com chaves de teste (o webhook foi testado
  com assinatura simulada, não contra o Stripe de verdade).
- Hospedar com disco persistente e sem dormir; definir `VITE_CONTACT_EMAIL` e `PRO_PRICE_LABEL`.
- "Esqueci minha senha" (precisa de e-mail transacional).
- Confirmar o preço (R$ 39 é só um valor provisório).

## 6. Pendências de git

- `master` local: 8 commits à frente e 21 atrás de `origin/master`. Não foi feito merge nem rebase. Revise o que há no remoto antes de integrar.
- Verificado em 2026-11-09: `origin/master` tem 21 commits que não estão aqui (439 arquivos: rebrand OneB, `Landing.tsx`, validações de ML/regime em `docs/ml` e `docs/trading`, preparação de deploy). Há sobreposição provável: **`frontend/src/pages/Analise.tsx` existe nos dois lados** (é outra página, com o mesmo nome), além de `App.tsx`, `Navbar.tsx` e `app/main.py`. Integrar exige decisão: renomear a minha para `AnaliseRisco.tsx` e fazer merge de `origin/master` aqui, numa branch própria, nunca direto no `master`.
- A "rodada 5" (ouro e Nasdaq com MT5, `output/research/ouro_nasdaq/`) foi enviada à `origin/plano-melhorias` por outra conversa e já foi incorporada por merge (`139ec95`).
- Esta branch (`plano-melhorias`) contém os 8 commits locais mais este documento.

## 7. Orçamento de dados pagos (preços de nov/2026, divergem entre fontes; confirmar nas páginas oficiais)

| Opção | Custo/mês (USD) | Observação |
|---|---|---|
| Só LLM para sentimento | poucos dólares (estimativa) | sem fonte nova |
| FMP Starter / Premium | ~22 / ~49 | 5 anos de histórico, notícias, desconto de 30% para estudantes |
| Polygon/Massive | ~29 a 199 | opções e classes de ativo cobradas à parte |
| Alpha Vantage | ~50 a 250 | não confirmado qual plano libera sentimento |
| Tiingo (notícias históricas) | sob consulta | histórico para institucionais |

Recomendação: começar sem gastar; só pagar se o sentimento mostrar sinal.

## 8. Decisões já tomadas (não reabrir sem motivo)

- LLM só interpreta; cálculo é determinístico (pandas/numpy).
- Nada de promessa de "precisão"; o placar mostra acertos e erros.
- O e-mail do SEC fica só em variável de ambiente.
