# OneB: sistema de design do terminal

Referência para qualquer mudança no frontend. Se algo aqui conflitar com o código, o código deve ser corrigido.

## Princípios

1. O terminal é uma ferramenta de trabalho: denso, legível, previsível.
2. Cor tem significado. Verde e vermelho só para alta/queda e P&L. Azul para interação e informação. Amarelo para aviso (dado atrasado, erro recuperável).
3. Todo dado tem quatro estados: carregando, erro, vazio, pronto. Nenhuma tela mostra zeros falsos.
4. Texto em português do Brasil, com acentos, em sentence case.

## Arquivos de estilo

| Arquivo | Papel |
| --- | --- |
| `src/styles/tokens.css` | Única fonte de cores, tipografia, espaço, raio, z-index, layout e movimento. Único lugar onde hex/rgba é permitido. |
| `src/styles/reset.css` | Reset mínimo. |
| `src/styles/base.css` | Corpo, foco visível, `prefers-reduced-motion`, utilitários (`.num`, `.up`, `.down`, `.muted`, `.sr-only`, `.skip-link`). |
| `src/styles/global.css` | Só isolamento do `#root` e barras de rolagem (31 linhas). |
| `src/styles/marketing.css` | Regras das páginas públicas, importado apenas por `MarketingLayout`. Usa tokens. |
| `*.module.css` | Estilo de cada componente/página. |

Temas: classe `dark` (padrão) ou `light` no `<html>`, controlada por `ThemeContext`. Gráficos leem as cores com `getComputedStyle`, então trocam de tema junto.

## Tokens

- Superfícies: `--bg-0..2`, `--surface`, `--surface-raised`, `--surface-hover`, `--border`, `--border-strong`.
- Texto: `--text-primary`, `--text-secondary`, `--text-tertiary`, `--text-on-brand`.
- Interação: `--brand`, `--brand-strong` (fundo de botão primário), `--brand-hover`, `--brand-subtle`, `--brand-border`.
- Mercado: `--positive`, `--negative`, `--negative-text`, `--*-subtle`.
- Aviso/informação: `--warning`, `--info` e variantes `-subtle`.
- Gráficos: `--chart-*`, séries `--series-1..4`, `--series-gold`.
- Tipografia: IBM Plex Sans (self-hosted via `@fontsource`, pesos 400/500/600). Escala `--fs-xs` (12) a `--fs-3xl` (36). Corpo da ferramenta 14px, tabelas 13px, leitura na Academia 16px com `--lh-reading` e `--measure: 70ch`.
- Espaço base 4px (`--sp-1..12`), raios 4/6/10px.

Por que IBM Plex Sans: números tabulares nativos com boa distinção entre 0/O e 1/l, largura contida para tabelas densas e acentos bem desenhados. Carregada localmente, sem requisição externa.

## Números

- Sempre `font-variant-numeric: tabular-nums` (classe `.num` ou `Stat`) e alinhados à direita em tabelas.
- Moeda explícita: `US$ 1.234,56`, `R$ 5,42`. Formatação em `lib/format.ts` (pt-BR).
- Variação com sinal e cor semântica via `ChangeText`.
- Datas da API sem fuso são tratadas como UTC (`parseApiDate`).

## Componentes

`src/components/ui` (exportados por `index.ts`):

- `Button` (`primary`, `secondary`, `ghost`, `danger`; tamanhos `sm`/`md`), `buttonClass` para links com aparência de botão.
- `Badge`, `Chips`/`ChipGroup`, `Tabs`/`TabPanel` (sublinhado ou segmentado).
- `Table`: ordenável, linhas clicáveis, primeira coluna fixa, modo denso, estado vazio.
- `Modal` (`dialog`, `sheet`, `drawer`) com foco preso e Esc.
- `Tooltip`, `Popover`, `Skeleton`, `EmptyState`, `ErrorState`, `Stat`, `ChangeText`, `Field` (`Input`, `Select`, `Textarea`), `Section`, `PageHeader`.
- `AsyncContent`: recebe o resultado de `useApi` e renderiza os quatro estados.

`src/components/terminal`: `AppShell`, `Sidebar`, `Topbar`, `BottomNav` (mobile), `CommandPalette` (Ctrl K), `MarketTicker`, `MarketStatus`, `ChartPanel`, `AnalysisPanel`, `DecisionBadge`, `AttentionLevel`, `DataAge`, `ConceptLink`, `TabbedPage`, `RedirectTo`.

Ícones: lucide-react, 16px, traço 1.75 (`ui/icon.ts`). Ícones acompanham texto; botão só com ícone precisa de `aria-label`.

## Dados

- `useApi<T>(path, { pollMs, isEmpty, enabled })` devolve `{ data, status, error, lastUpdated, refreshing, retry, mutate }`. Cache em módulo com stale-while-revalidate; 404 vira vazio; polling pausa com a aba oculta.
- `DataAge` mostra a idade do dado e fica amarelo quando atrasado.
- Erros oferecem "Tentar de novo".

## Vocabulário de decisão

`lib/decisionState.ts` traduz o backend para três estados, sempre acompanhados do viés:

| Backend | Rótulo |
| --- | --- |
| `BUY_CONTROLLED`, `SELL_SHORT` | Setup em formação |
| `WATCH_BUY`, `WATCH_SHORT` | Observar |
| `NO_TRADE`, `WAIT`, `AVOID` | Sem setup |

Viés: "viés de alta" ou "viés de baixa". Nunca "compre" ou "venda".

Atenção no Radar (`lib/attentionScore.ts`): pontuação explicável (movimento, notícias, alertas, resultados, preço ausente, dado velho) com níveis alta/média/baixa e o motivo de cada ponto visível no tooltip.

## Texto

- Sentence case em títulos, botões e abas.
- Botões com verbo exato ("Criar alerta", "Salvar posição"); o toast repete o verbo ("Alerta criado").
- Sem jargão de marketing dentro da ferramenta.
- Textos do backend passam por `lib/text.ts` (`ptBR`) para acentos e vírgula decimal até o backend ser corrigido.

## Proibições

- Brilho, sombras coloridas, glassmorphism, gradientes decorativos (páginas públicas podem manter um gradiente contido).
- Emoji e dingbats. Ícone de "brilho" e a palavra "IA" espalhada pela interface.
- Eyebrows em caixa alta, separador "·" em metadados, "→" em botões.
- Grades de cards idênticos como layout padrão.
- Animações de entrada e efeitos de digitação. Movimento só em resposta a ação ou mudança de dado, e desligado com `prefers-reduced-motion`.
- Hex ou rgba fora de `tokens.css`.

## Rotas

| Rota | Página |
| --- | --- |
| `/ferramenta` | Hoje |
| `/mercado` | Mercado (Notícias, Calendário, Câmbio, Resultados) |
| `/analise?tab=visao-geral\|regime\|tecnica\|macro` | Análise |
| `/radar` | Radar |
| `/watchlist` | Watchlist (regras e playbooks) |
| `/alertas` | Alertas |
| `/carteira?tab=posicoes\|operacoes\|desempenho` | Carteira |
| `/assistente?modo=...` | Assistente (5 modos) |
| `/ativo/:symbol` | Ativo |
| `/academia`, `/academia/trilhas/:slug`, `/academia/lives`, `/aulas/:slug` | Academia |
| `/configuracoes?tab=conta\|workspace\|usuarios\|sistema` | Configurações |
| `/ajuda` | Ajuda |

Rotas antigas redirecionam com `<Navigate replace>` (ver `App.tsx`).

## Mobile

Abaixo de 768px a sidebar vira navegação inferior (`BottomNav`, 56px) com Hoje, Mercado, ações rápidas (+), Alertas e Assistente; o menu completo abre pela topbar. Tabelas mantêm a primeira coluna fixa e rolam na horizontal dentro do próprio contêiner, nunca a página.
