# OneB Market — Guia de Design + Mapa da Plataforma

Documento de apoio para colar no Lovable (ou em qualquer outra ferramenta) e para decidir prioridades do redesign. Os tokens e a estrutura abaixo vieram do código real do app (pasta `frontend/`), não são inventados — assim o Lovable recria algo consistente com o que já existe em produção.

---

## 1. Contexto do produto

No código, o produto se chama **OneB**, com o posicionamento "**Escola + Terminal**": uma escola de investimentos (aulas, lives, comunidade) integrada a um terminal de monitoramento de mercado. O público acompanha tanto ativos brasileiros (Ibovespa, IFIX, ações B3) quanto ativos dos EUA/Nasdaq, com conversão USD/BRL.

Regra de compliance que aparece fixa no rodapé de toda a área logada e deve se manter no redesign:

> "Ferramenta apenas de monitoramento e sugestão. Não executa ordens e não constitui recomendação de investimento. Dados podem ter atraso. Valide qualquer sinal antes de decidir."

---

## 2. Tokens de design (tema escuro, único tema em produção)

| Token | Valor | Uso |
|---|---|---|
| `--bg` | `#050607` | fundo geral (com gradiente radial azul sutil no topo) |
| `--fg` | `#f5f7fa` | texto principal |
| `--muted` | `#9aa4af` | texto secundário |
| `--muted-dim` | `#657180` | labels, timestamps, texto terciário |
| `--card` / `--card-alt` | `#0d1013` / `#12161a` | fundo de cards/painéis (usados em gradiente diagonal) |
| `--border` | `rgba(255,255,255,0.08)` | bordas de painéis, tabelas, divisores |
| `--accent` | `#2684ff` | cor de marca — links ativos, foco, ícone da marca |
| `--up` | `#32d583` | valorização, status positivo |
| `--down` | `#ff5f6d` | desvalorização, severidade alta |
| `--warning` | `#f5b84b` | severidade média, atenção |
| `--chart-up` / `--chart-down` | `#26a69a` / `#ef5350` | cores de candle (padrão TradingView) |
| `--shadow` | `0 18px 55px rgba(0,0,0,0.34)` | sombra de elevação |
| `--surface-glow` | `0 0 0 1px rgba(255,255,255,0.04), 0 20px 70px rgba(0,0,0,0.38)` | brilho sutil de borda em cards |
| raio de borda | `6–8px` (padrão), `12px` (cards maiores) | consistente em toda a UI |
| fonte de interface | `Inter` (400/500/600/700/800) | textos e labels |
| fonte numérica | monoespaçada (ex. `IBM Plex Mono`) | preços, variações, timestamps — dá aparência de terminal |

Painel padrão (`panel`): fundo em gradiente diagonal escuro (`linear-gradient(145deg, rgba(18,22,26,.92), rgba(9,11,13,.96))`), borda 1px `rgba(255,255,255,.08)`, raio 12px, `surface-glow`. Ao passar o mouse, a borda vira azul (`rgba(38,132,255,.28)`).

---

## 3. Componentes-padrão (reaproveitar em qualquer tela nova)

- **Painel** (`panel`): container base de qualquer bloco de conteúdo, com título + subtítulo à esquerda e um link de ação à direita (ex. "ver todos").
- **Card de resumo** (`summary-card` / `metric-card`): label pequeno em maiúsculas, valor grande em fonte mono, badge de variação (▲/▼ colorido) e sparkline opcional.
- **Badge de confiança** (`confidence`): pílula com ponto colorido — verde "Alta", âmbar "Média", cinza "Baixa". Usado em alertas, watchlist e leituras de IA para indicar confiabilidade do sinal, nunca recomendação.
- **Pílula de status** (`status-pill`): mesma lógica de cor (verde/âmbar/vermelho) para status de dados ("ao vivo", "atrasado", "sem dados").
- **Tabela densa** (`dense-table`): cabeçalho em maiúsculas pequenas, linhas com borda inferior sutil, células numéricas em fonte mono.
- **Lista compacta** (`compact-list`): usada em notícias, calendário econômico e alertas recentes — ícone/pílula à esquerda, título + metadado à direita.
- **Sidebar do terminal**: 264px, fundo levemente mais escuro que o conteúdo, itens agrupados por seção com rótulo em maiúsculas, item ativo com barra azul à esquerda.
- **Topbar**: 68px, marca à esquerda (logotipo de 3 barras em gradiente azul), status "Mercado aberto" ao centro-direita, busca/notificações/avatar à direita.
- **Aviso de compliance**: microcopy discreta, itálico, cor `muted-dim`, sempre que houver conteúdo gerado por IA ou sinal técnico.

---

## 4. Mapa completo da plataforma (rotas reais hoje)

### Público / Marketing (sem login)
`/` Landing · `/aulas` · `/aplicacoes` · `/estrategias` · `/comunidade` · `/planos` · `/sobre` · `/login` · `/cadastro`

### Escola (layout com navbar simples, sem sidebar)
`/inicio` Hub (saudação + continuar curso + próxima live) · `/aprendizado` · `/aulas/:slug` Curso · `/lives` · `/perfil` (diário inteligente do trader: diagnóstico, desempenho por ativo/horário/estilo)

### Terminal (layout com sidebar + topbar — é onde entra o dashboard redesenhado)
- `/ferramenta` **Dashboard** ✅ redesenhado
- `/watchlist` Watchlist & Regras de alerta
- `/alertas` Alertas
- `/mercado` Painel de Mercado (notícias globais/por ativo + calendário econômico + earnings)
- `/analise-matinal` Análise Matinal (pré-mercado)
- `/resumo-diario` Resumo do Mercado (relatório diário)
- `/posicoes` Posições & P&L (lançamento manual)
- `/ativo/:symbol` Detalhe do ativo
- `/mesa-tecnica` Mesa Técnica (indicadores)
- `/mesa-ia` Mesa IA (recomendações auditáveis + placar de confiabilidade + memória temporal)
- `/copiloto` Copiloto (decisão explicável, votos de "especialistas" de IA, plano de risco, simulador)
- `/inteligencia` Inteligência de Mercado (radar, explicação, playbooks, diário de decisão)
- `/regime` Regime de mercado
- `/assistente` Assistente IA
- `/saas` Painel comercial do workspace (planos, marca, canais de alerta, templates)
- `/operacoes` Auditoria operacional (saúde de dados/cache/modelo — painel técnico)
- `/como-usar` Guia de uso

### Admin
`/usuarios` (somente admin)

---

## 5. Sugestão de prioridade para redesenhar

1. **Dashboard** — feito.
2. **Watchlist + Alertas** — já compartilham os componentes do dashboard (pílulas, confiança, tabela densa); ganho rápido.
3. **Ativo Detalhe + Mesa Técnica** — telas de gráfico, natural continuar por aqui.
4. **Mesa IA + Copiloto + Inteligência** — todas usam o mesmo conceito de "score/confiança auditável"; vale um padrão visual único para as três.
5. **Mercado + Resumo Diário + Análise Matinal** — conteúdo parecido (notícias, calendário, leitura do dia).
6. **Posições** — tabela + formulário simples.
7. **Operações** — painel técnico/interno, baixo impacto visual para o usuário final.
8. **Escola** (Hub, Aprendizado, Cursos, Lives, Perfil) — é praticamente outro produto dentro do produto; pode ficar numa segunda fase.
9. **Marketing** (Landing, Planos, Sobre) + **SaaS/Usuários** (admin) — última prioridade.

---

## 6. Prompt pronto para colar no Lovable

> Recrie esta tela em React + Tailwind a partir da imagem/descrição anexada. Não crie backend, não use Supabase: o backend é um FastAPI já existente e vou consumir via API REST com autenticação JWT (Bearer token) — deixe pontos claros (hooks/serviços) onde as chamadas de API devem entrar, com dados mockados por enquanto. Tema escuro fixo, paleta: fundo `#050607`, cards `#0d1013`/`#12161a` com borda `rgba(255,255,255,0.08)`, accent azul `#2684ff`, verde `#32d583` para alta, vermelho `#ff5f6d` para baixa, âmbar `#f5b84b` para atenção. Tipografia Inter para textos e uma fonte monoespaçada para números/preços. Componentes reutilizáveis: painel com título+subtítulo, badge de confiança (Alta/Média/Baixa com cor), pílula de status, tabela densa, lista compacta para notícias/eventos.

---

*Gerado a partir do código-fonte real em `frontend/src` (rotas, `global.css`, componentes de página) em 26/08/2026.*
