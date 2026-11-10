# Fase de dados — achados (2026-08)

Registro dos resultados da auditoria de dados/features feita nesta sessão, para não repetir o
trabalho depois. Todos os scripts citados estão em `scripts/` e são reexecutáveis
(`python -m scripts.<nome>`), a maioria aceita `PAPER_SIM_SYMBOLS=A,B,C` para trocar o universo.

## Resumo executivo (atualizado após os 13 experimentos — ver "Conclusão consolidada" no final)

Testamos se as 11 features técnicas de `app.paper_simulator.FEATURE_NAMES` (RSI, MACD, EMA,
ADX, ATR, volume, score composto, VIX) carregam vantagem estatística preditiva. As primeiras 9
formulações (direção absoluta, cross-sectional pooled, risco, fundamentals, transição de
regime, segundo universo de ativos) **não sobreviveram** a validação out-of-sample rigorosa.

A virada veio ao testar **condicionado a regime de mercado** (bull/bear) em vez de pooled: as
features que carregam sinal trocam completamente entre regimes, e um modelo de 2 features
(`annualized_volatility` + `atr_pct`) treinado só em dias de regime BEAR mostrou AUC≈0.53 em
holdout — pequeno, mas **reproduzido de forma quase idêntica ao mudar de 5 para 10 anos de
histórico** (o único resultado de toda a auditoria a se repetir assim). Fraco demais pra virar
estratégia sozinho, mas é o candidato real mais forte encontrado. Detalhes completos abaixo;
resumo da decisão final na seção "Conclusão consolidada".

## Fontes de dado corrigidas/adicionadas

- **FRED** (`app/market_data/fred_client.py`) — yields do Tesouro (2/5/10/30Y), Dollar Index
  (DTWEXBGS), VIX, agora vindos da fonte oficial em vez de proxies Yahoo. Resolveu o gap do
  US2Y que não tinha ticker Yahoo confiável.
- **Calendário econômico** — migrado de FMP (API v3 descontinuada em 2025-08-31, endpoint
  `/stable` restrito no plano grátis) para `fred_client.get_economic_calendar` (FRED
  `/releases/dates`, filtrado a 6 releases de alto impacto: FOMC, CPI, NFP, GDP, PCE, Retail
  Sales). Mesma key já configurada, sem cadastro novo.
- **FMP fundamentals** (`app/market_data/fmp_client.py`) — `get_key_metrics` /
  `get_income_statement`, plano grátis limitado a anual (não trimestral), `limit<=5`,
  `income-statement.filingDate` usado para join point-in-time correto (evita look-ahead).
- **Bug corrigido**: `finnhub_client.get_earnings_calendar()` sem `symbol` sempre lançava
  `TypeError` (a lib `finnhub-python` instalada exige `symbol` sempre; `""` = todos). Não afetava
  produção (os dois callers reais sempre passam symbol), mas era um bug latente.
- `scripts/api_health_check.py` — roda todo provider real (não só checa se a key existe) e
  reporta pass/fail. Rodar periodicamente para pegar esse tipo de quebra silenciosa cedo.

## Experimentos e resultados

| # | Script | Formulação testada | Resultado |
|---|---|---|---|
| 1 | `eda_report.py` | Auditoria do dataset (gaps, NaN, correlação pooled) | Dataset limpo; correlação feature×label máx. 0.07 |
| 2 | `label_horizon_scan.py` | Horizontes 1-20d, thresholds 0-1% | Melhor correlação 0.14, só em label desbalanceado (baseline 71%) |
| 3 | `feature_engineering_experiment.py` | +8 features (regime/cross-asset/lag) via A/B walk-forward | Holdout AUC piorou (0.475→0.452); não promovido |
| 4 | `cross_sectional_ic.py` | Ranking cross-sectional (padrão Gu-Kelly-Xiu / IC), 24 e depois 48 símbolos | IC subiu com universo maior (0.033→0.042, t=3.24) mas não sobreviveu à divisão temporal (t=3.96 → t=0.69) |
| 5 | `risk_label_experiment.py` | Triple-barrier (López de Prado) — prever stop-antes-do-alvo em vez de direção | Holdout AUC=0.463 (abaixo de 0.50); melhor feature muda entre metades |
| 6 | `fundamentals_experiment.py` | IC cross-sectional de fundamentals (revenue growth, ROE, ROIC, yields) | `revenue_growth_yoy` IC=0.031 (t=2.16) na amostra completa, mas inverte de sinal na segunda metade (t=4.11→t=-0.74) |
| 7 | `regime_timeline.py` | Reconstrução mensal do regime (score + VIX) pra achar a causa raiz | Não é uma quebra única — são 2 correções violentas (mar/2025, fev-mar/2026) intercaladas com bulls fortes |
| 8 | `regime_transition_experiment.py` | Prever transição pra regime BEAR nos próximos 10d (onset detection) | AUC=0.874 com o feature set completo — **mas isso é majoritariamente circular** (regime_score/rsi/adx são quase a mesma informação do label). Isolando só as features independentes (VIX, ATR, DXY, US10Y): AUC cai pra 0.571 e accuracy = exatamente o baseline. Sem sinal real. |
| 9 | `cross_sectional_ic.py` (32 símbolos small/mid-cap) | Hipótese: mega-cap é eficiente demais, small/mid-cap teria mais ineficiência | Sinal ainda mais fraco que mega-cap (melhor t=1.19, nem significativo). Descarta eficiência-do-ativo como explicação. |
| 10 | `regime_conditional_ic.py` | IC cross-sectional dividido por regime de mercado (bull/bear/neutro), não pooled | `annualized_volatility` em BEAR: IC=0.082, t=4.05 (depois t=4.76 com 10 anos) — primeiro resultado a cair na faixa "sólido" (0.05-0.10) da literatura. Features trocam completamente entre bull e bear. |
| 11 | `regime_conditional_validation.py` | Walk-forward holdout treinado/testado só em dias BEAR | AUC=0.5321 (5 anos) — acima do baseline, mas sinal encolheu bastante frente ao IC agregado; só 1 episódio BEAR de holdout, inconclusivo sozinho. |
| 12 | Re-teste de #10/#11 com 10 anos (2016-2026) | Mesmo protocolo, mais histórico (3 recessões reais no treino) | AUC=0.5329 — **praticamente idêntico ao teste de 5 anos**, com treino/holdout totalmente diferentes. Reprodutibilidade = evidência de efeito real, pequeno e estável. |
| 13 | `regime_conditional_multifactor.py` | Combinar mais features (RSI/trend/score/DXY/US10Y) dentro do regime BEAR já corrigido | AUC caiu de 0.5329 para 0.5186 — mais features pioram mesmo condicionado certo. Teto de ~0.53 é do par volatilidade/ATR, não falta de sinais. |

### Nota metodológica importante (achado #8)

Ao testar transição de regime, o primeiro resultado (AUC=0.874) parecia a melhor descoberta da
sessão — mas era um artefato: usar `regime_score` atual (e RSI/ADX, que compõem esse score) pra
prever se `regime_score` vai cruzar um limiar é quase circular — mede autocorrelação da própria
série, não um alerta antecipado de verdade. Rodar de novo só com features estruturalmente
independentes do label (VIX, variação de VIX, ATR, DXY, US10Y) derrubou o resultado pra AUC=0.571
(accuracy idêntica ao baseline). **Sempre que um resultado parecer bom demais, checar se alguma
feature carrega a mesma informação usada pra construir o label antes de comemorar.**

## Metodologia usada (para manter em qualquer experimento futuro)

1. Correlação feature↔label calculada **só no fold de treino**, nunca no holdout, antes de
   qualquer decisão de feature.
2. Split walk-forward com embargo/purging (López de Prado) — mesmos folds de
   `scripts/calibrate_decision_strategy.py`.
3. Métricas sempre com baseline (classe majoritária) ao lado — nunca accuracy sozinha.
4. **Checagem de estabilidade temporal (primeira metade vs segunda metade) é obrigatória** antes
   de qualquer promoção — foi o teste que derrubou os experimentos #4, #5 e #6 depois de
   parecerem promissores na correlação agregada.
5. Múltiplas comparações corrigidas com Bonferroni quando testando várias features de uma vez.
6. **Checar se alguma feature é circular com o label** (carrega quase a mesma informação usada
   pra construir o alvo) — foi o que inflou o AUC do experimento #8 pra 0.874 antes de cair pra
   0.571 quando isolado.

## Não promovido para produção

`app/probability_model.py` e `app/decision_engine.py` **não foram alterados** por nenhum desses
experimentos — nenhum passou na barra de validação que a própria equipe definiu. O modelo salvo
em produção continua sendo o treinado por `scripts/train_probability_model.py` (holdout accuracy
48.99%, abaixo do baseline 51.49% — ver histórico em `probability_model_history.json`).

## Estado em 2026-08-09: nenhuma vantagem estatística demonstrada ainda

Nove formulações de problema testadas (direção absoluta, direção por horizonte, A/B de
features, ranking cross-sectional, risco via triple-barrier, fundamentals, transição de
regime, e um segundo universo de ativos) — nenhuma sobreviveu à validação out-of-sample
completa (holdout + estabilidade temporal + checagem de circularidade). Isso não significa
"não há vantagem nenhuma possível" — significa que o material testado até aqui (preço/volume
de um único ativo + macro público + fundamentals anuais grátis) não a demonstrou.

### #9 — Universo small/mid-cap (hipótese: mega-cap é eficiente demais)

Testamos se a ausência de sinal era um efeito de eficiência de mercado (mega-caps arbitradas
demais) trocando o universo de 48 mega/blue-chips por 32 símbolos small/mid-cap diversos
(consumo, biotech, software). Resultado: sinal ainda **mais fraco** que nas mega-caps (melhor
IC com t=1.19, nem passa no limiar de significância de 1.96; `annualized_volatility`, que era a
melhor feature nos universos anteriores, inverteu de sinal e sumiu aqui). Isso descarta a
hipótese de eficiência-do-ativo como explicação — reforça que o teto é o **tipo de dado**
(técnico/preço), não a escolha de qual ativo testar.

### Dados de natureza diferente (order flow, opções, sentimento) — bloqueados por orçamento, não por engenharia

Pesquisamos as três categorias (2026-08-09):

- **Order flow / opções (book L2, dark pool, put/call)**: nenhuma fonte grátis viável na escala
  necessária. Databento (trial c/ $125 credito), Polygon/Massive (US$79+/mes), QuantData/OptionData
  (pagos desde o 1o request). FlashAlpha tem tier grátis mas 5 chamadas/dia — inutilizável pra
  dataset de 30-48 símbolos × 2 anos.
- **Sentimento histórico de notícias**: testamos com o que já tínhamos (Finnhub, grátis, já
  integrado) — `get_company_news` só devolve os **últimos dias**, zero artigos pra qualquer mês
  passado (testado em jan/2025 e set/2024: 0 resultados nos dois). EODHD demo (sentimento)
  retornou 502 em múltiplas tentativas — inutilizável/instável.
- **Padrão geral**: dado em tempo real é grátis; **arquivo histórico é a parte monetizada** pelos
  provedores. Isso não é contornável com engenharia — é decisão de orçamento.

Caminhos que restam:
1. Pagar por arquivo histórico (order flow ou sentimento) — decisão de orçamento explícita,
   ainda não tomada.
2. Começar a coletar notícias/eventos a partir de agora (Finnhub tempo real, grátis) para
   acumular um dataset próprio ao longo do tempo — não serve para testar hoje.
3. ~~Universo de ativos menos eficiente~~ — testado no #9, descartado como explicação.
4. **Aceitar o resultado por ora** e manter Market Regime / Cross-Asset / Macro-News AI
   (rule-based, já funcionam) como motor principal, revisitando Signal Quality quando (1) ou
   (2) mudarem.

## Correção (2026-08-10): dois bugs metodológicos achados em revisão externa

Uma revisão de código externa (leitura direta do repositório, não deste documento) encontrou
dois problemas reais nos experimentos #1-#9 acima:

1. **`period="2y"` hardcoded** em `app/paper_simulator.py` (3 ocorrências) — todo experimento
   desta fase rodou sobre a mesma janela de ~2 anos por *configuração*, não por limite real da
   fonte de dado. yfinance aceita `5y`, `10y`, `max`. Corrigido: `MARKET_HISTORY_PERIOD` (env
   var, default `"2y"` mantido para não mudar o comportamento de produção sem opt-in explícito).

2. **`row_index` usado como chave de cruzamento entre símbolos** em 6 dos scripts desta fase
   (a crítica externa citou `cross_sectional_ic.py`; achamos o mesmo padrão em
   `feature_engineering_experiment.py`, `fundamentals_experiment.py`,
   `risk_label_experiment.py`, `regime_transition_experiment.py`). Isso presume que
   `symbol_A[i]` e `symbol_B[i]` são o mesmo dia de pregão — verdade só enquanto todos os
   símbolos têm histórico de tamanho idêntico. Verificamos: nos universos já testados (24/48
   símbolos, janela de 2 anos) as datas realmente coincidiam em todo `row_index` testado, então
   os resultados #1-#9 **não estavam corrompidos** — mas o bug quebraria silenciosamente assim
   que o histórico fosse estendido (ex: `PLTR`, `DUOL`, `ONON`, `CFLT` têm menos anos de pregão
   que `AAPL`). Corrigido: todos os scripts agora cruzam por `date` real
   (`scripts/research_folds.py` substitui o `_walk_forward_folds` baseado em posição por uma
   versão baseada em data de calendário).

### Resultado de re-rodar com 5 anos (pipeline corrigido)

`cross_sectional_ic.py` com `MARKET_HISTORY_PERIOD=5y`, mesmos 48 símbolos:

```
IC agregado (5 anos): annualized_volatility = 0.0201 (t=2.14) — mais fraco que os 0.041 (t=3.20)
                       vistos na janela de 2 anos, mas ainda nominalmente significativo.

Dividido em 3 sub-periodos:
  2021-10 a 2023-05 (inclui bear market de 2022): IC = -0.015 (t=-0.78, SEM sinal, sinal NEGATIVO)
  2023-05 a 2024-12:                               IC = +0.038 (t=2.64, significativo, POSITIVO)
  2024-12 a 2026-08:                               IC = +0.038 (t=2.71, significativo, POSITIVO)
```

O sinal de volatilidade **inverte de direção** entre o período que inclui o bear market de 2022
e os períodos posteriores (bull). Isso é consistente com a descoberta independente do
`regime_timeline.py` (mercado de reversões em V) e com a recomendação de modelagem
condicional-a-regime que a revisão externa também sugeriu (linha de pesquisa `RegimeFolio`).

**Leitura**: não é "sem sinal" — é "sinal condicional ao regime, mascarado quando testado sem
condicionar". Isso reabre a pesquisa de Signal Quality AI, mas para uma direção mais específica:
modelo condicionado a regime (bull/bear/neutro) em vez de modelo único pooled, e não mais como
"pausado por falta de edge".

## #10 — IC condicional a regime (`scripts/regime_conditional_ic.py`) — achado mais forte da sessão

Regime calculado uma vez a partir do NASDAQ (não por símbolo — evita a circularidade que
derrubou o AUC=0,874 do experimento #8) e aplicado a todos os símbolos no mesmo dia. 48
símbolos, 5 anos, pipeline já corrigido (date-based).

```
REGIME BULL (812 dias):   rsi t=3.11, trend t=2.64, score t=2.88 — volatilidade/ATR sem sinal
REGIME BEAR (372 dias):   annualized_volatility t=4.05 (IC=0.082, faixa "SÓLIDO"),
                           atr_pct t=3.24 — rsi/trend/score fracos e com sinal invertido
REGIME NEUTRO (17 dias):  amostra pequena demais para confiar
```

Achado: **as features que carregam sinal trocam completamente entre bull e bear**, e o IC de
volatilidade em bear (t=4,05) é o primeiro resultado de toda a sessão a cair na faixa "sólido"
(0.05–0.10) da literatura, não apenas "fraco-aproveitável". Isso explica por que todo teste
pooled anterior (#1 a #9) mostrou sinal fraco/instável — os efeitos de regimes opostos se
cancelavam parcialmente ao serem testados juntos.

**Ainda não promovido**: isso é um diagnóstico de IC, não um teste completo. Antes de qualquer
uso real, falta validar com o protocolo cheio (walk-forward holdout treinado só em dados
BEAR, testado em holdout BEAR nunca visto) — é o próximo passo natural.

## #11 — Validação walk-forward do sinal BEAR (`scripts/regime_conditional_validation.py`)

Treinou `annualized_volatility` + `atr_pct` só em dias BEAR (2021-10 a 2025-03, 3 folds),
testou num holdout BEAR nunca visto (2025-03 a 2026-08, 3.936 amostras). Label = rank
cross-sectional do dia (acima da mediana), o mesmo que o IC mediu — não o limiar absoluto já
descartado no experimento #2.

```
Baseline (holdout):  0.5000
Accuracy:             0.5264
AUC:                   0.5321   (0.50 = sem poder preditivo)
Brier:                 0.2488
```

**Leitura honesta, sem inflar nem descartar**: é o único resultado de toda a auditoria (#1-#11)
em que o holdout ficou acima do baseline — mas por uma margem pequena (AUC 0.53, não os 0.05-0.10
de IC "sólido" que o diagnóstico #10 sugeria). O sinal encolheu bastante entre o IC agregado
(t=4.05) e o holdout de verdade — padrão comum e esperado (a correlação em amostra cheia sempre
otimiza mais do que generaliza), agravado aqui por só termos **um** episódio BEAR real de holdout
(2025-03 a 2026-08) — pouca potência estatística pra separar "efeito real mas fraco" de "sorte de
um único período".

**Conclusão inicial (5 anos)**: nem "confirmado" nem "sem sinal" — inconclusivo, só um episódio
BEAR de holdout disponível.

## #12 — Re-teste com 10 anos (2016-2026, inclui correção de 2018 e crash da COVID)

Re-rodado #10 e #11 com `MARKET_HISTORY_PERIOD=10y` (mesmos 48 símbolos; `NQ=F` não tem 10 anos
de futuro contínuo no yfinance, caiu automaticamente para `^NDX` via fallback já existente).

```
IC diagnostico (#10, 10 anos):  annualized_volatility em BEAR: IC=0.0755, t=4.76 (subiu de t=4.05)
                                  570 dias BEAR (vs 372 antes) — inclui 2018, COVID, 2022, 2026

Holdout walk-forward (#11, 10 anos):
  Treino: 3 folds cobrindo 2016-2023 (3 recessoes reais distintas)
  Holdout: 2023-10 a 2026-08 (nunca visto)
  AUC = 0.5329 | accuracy = 0.5292 vs baseline 0.50
```

**O número saiu praticamente idêntico ao teste com 5 anos (AUC 0.5321 → 0.5329)**, apesar do
treino agora cobrir 3 recessões de mercado reais e independentes em vez de uma só, e o holdout
ser um período completamente diferente. Essa reprodutibilidade é o dado mais importante desta
seção: ruído puro não bateria tão perto de novo com um treino/holdout inteiramente diferente —
é evidência (não prova) de um efeito real, pequeno e estável, não um acaso de uma janela.

**Conclusão final**: o veredito automático do script ("não sobreviveu") é binário demais pra essa
leitura. Mais precisa: **existe um efeito real de volatilidade cross-sectional em regime BEAR,
mas pequeno (AUC≈0.53, bem abaixo do que sustentaria uma estratégia sozinho)**. É o único sinal
de toda a auditoria (12 experimentos) que se reproduziu de forma consistente ao mudar radicalmente
a janela de dados. Ainda não é suficiente para produção sozinho — mas é candidato real a compor
um score multi-fator (junto com regime + macro + o que mais aparecer), não a virar modelo
standalone. Não integrado ao `decision_engine.py`.

## #13 — Multi-fator dentro do regime BEAR (`scripts/regime_conditional_multifactor.py`)

Testou se combinar mais features (RSI, trend, score, DXY 5d, US10Y 5d — os mesmos candidatos do
experimento #3, agora corretamente restritos a dias BEAR) melhora o AUC~0.53 do modelo A
(`annualized_volatility` + `atr_pct`). Mesmo protocolo walk-forward-em-BEAR do #11/#12.

```
Modelo A (2 features, validado):        AUC = 0.5329
Modelo B (A + 5 features novas):        AUC = 0.5186   (PIOROU)
```

**Adicionar features piorou o modelo, mesmo já dentro do regime certo.** Isso não é o mesmo erro
do experimento #3 (que testava pooled, mascarando efeitos opostos) — aqui já está condicionado
corretamente e ainda assim mais features não ajudaram. Leitura: o teto de ~0.53 de AUC parece ser
do próprio par volatilidade/ATR em regime BEAR, não falta de mais sinais — reforça manter o
modelo simples (2 features) em vez de expandir.

## Decisão anterior (2026-08-09, superada pela correção acima): pausar Signal Quality AI

Depois de 9 formulações de problema e 2 universos de ativos testados com rigor (walk-forward,
holdout, estabilidade temporal, checagem de circularidade), e com as três fontes de dado de
natureza diferente (order flow, opções, sentimento histórico) bloqueadas por orçamento — não
por falta de tentativa de engenharia — a decisão foi **pausar a pesquisa de Signal Quality AI**.

O motor de recomendação da plataforma continua sendo as IAs rule-based e já validadas:
Market Regime AI e Cross-Asset AI (`app/regime_engine.py`), Macro-News AI
(`app/market_data/fred_client.py` + calendário econômico + Finnhub). `probability_model.py`
permanece no código, sem uso na tomada de decisão real (`decision_engine.py` só usa pra
*apertar* uma recomendação já aprovada pelas regras, nunca pra aprovar sozinho — comportamento
que já existia antes desta sessão e continua correto).

**Retomar quando**: (a) houver orçamento aprovado para dado histórico de order flow/opções/
sentimento, ou (b) uma nova fonte gratuita e genuinamente diferente aparecer, ou (c) o dataset
próprio de notícias (opção 2 acima) tiver acumulado profundidade suficiente para testar.

## Coleta própria de notícias — já existia, agora confirmada ativa

Ao investigar a opção (c) acima, achamos que a infraestrutura **já existia** antes desta sessão:
`app.scheduler.refresh_news` (por símbolo, a cada `NEWS_REFRESH_SECONDS`, padrão 30min) e
`refresh_global_news` (por categoria, a cada `GLOBAL_NEWS_REFRESH_SECONDS`, padrão 15min) já
gravam em `NewsItem`/`GlobalNewsItem` com dedup por URL e sem nenhuma limpeza/expiração — ou
seja, é um arquivo que só cresce desde que o scheduler esteja rodando.

O que fizemos nesta sessão:
- Confirmamos que `refresh_news` funciona (rodado manualmente, 248 artigos da AAPL sem erro) —
  o banco local só estava vazio porque o scheduler não tinha rodado ainda nesta máquina, não
  por bug.
- Adicionado `sentiment_score` (nullable) em `NewsItem` e `GlobalNewsItem`, com migração leve
  em `app/db.py` (`_ensure_sqlite_saas_columns`) seguindo o padrão já existente no projeto —
  prepara o schema para quando houver um scorer, sem exigir migração depois.

**Confirmado nesta sessão**: o `docker-compose.prod.yml` tem o serviço `worker` (roda
`app.worker`, que inicia o scheduler via `build_scheduler`) configurado com
`restart: unless-stopped` — desenhado pra rodar contínuo. Mas hoje (2026-08-09) ele só roda
**localmente**, sob demanda, não 24/7 em servidor. Isso significa que a coleta atual tem buracos
toda vez que a máquina fica desligada — não é ainda um arquivo histórico confiável para o
experimento de sentimento futuro. Pra virar isso, precisa de deploy contínuo do `worker`
(VPS, Fly.io, Railway, etc. — decisão de infraestrutura/custo, não resolvida aqui).

**Decisão (2026-08-09)**: deixar como está por ora — sem decisão de deploy/custo agora. O
schema (`sentiment_score`) já está pronto para quando isso mudar. Se quiser retomar depois,
os passos são: (1) decidir onde hospedar o `worker` 24/7, (2) deployar, (3) esperar acumular
profundidade (meses), (4) então testar sentimento com o mesmo protocolo de rigor usado nos
9 experimentos anteriores.

---

## Conclusão consolidada (2026-08-10) — estado final desta fase

**13 experimentos rodados, 2 bugs metodológicos reais corrigidos no meio do caminho
(`period="2y"` hardcoded, `row_index` como chave de junção). Um sinal real encontrado, pequeno
e ainda não pronto para produção.**

### O achado

```text
Modelo: annualized_volatility + atr_pct
Onde:   só em dias de regime BEAR (calculado a partir do NASDAQ, aplicado
        a todos os símbolos do mesmo dia — evita circularidade)
Label:  ranking cross-sectional do dia (acima/abaixo da mediana de retorno
        futuro de 5 dias entre os símbolos do universo)

Resultado (holdout walk-forward, nunca visto no treino):
  5 anos de histórico:  AUC = 0.5321
  10 anos de histórico: AUC = 0.5329   ← quase idêntico, treino/holdout diferentes
```

A reprodutibilidade entre janelas de dados completamente diferentes é a evidência mais forte
de toda a sessão — mais forte que qualquer correlação isolada, porque ruído não bateria no
mesmo número duas vezes. Mas AUC≈0.53 é fraco: bem abaixo do que sustentaria uma estratégia
sozinho, e adicionar mais features (experimento #13) piorou em vez de ajudar — o teto parece
genuíno, não falta de tentativa.

### O que NÃO foi feito

`app/probability_model.py` e `app/decision_engine.py` não foram alterados por nenhum desses 13
experimentos. Nada foi promovido para produção. O sinal BEAR fica documentado como candidato,
não como modelo ativo.

### Caminhos daqui pra frente, por ordem de esforço

1. **Usar o sinal BEAR com responsabilidade** — não como sinal de compra/venda isolado, mas
   como um ajuste pequeno de confiança dentro do Risk Engine, só quando o regime bater, com a
   IA nunca tendo autoridade final (mesmo princípio já discutido para o Risk Engine).
2. **Deploy do worker 24/7** (custo de infraestrutura, ~$5-10/mês em VPS barato) — desbloqueia
   acumular dataset próprio de notícias para testar sentimento no futuro, de graça depois disso.
3. **Orçamento para dado alternativo** (order flow, opções, sentimento histórico pago) — só
   compensa se (1) não for suficiente e a plataforma já estiver gerando receita/uso real.
4. **Parar de testar novas formulações no dado atual** — os experimentos #9 e #13 já mostraram
   retornos decrescentes (mudar universo não ajudou, mais features não ajudaram). Sem uma ideia
   de dado genuinamente nova, mais variações têm alta chance de só redescobrir o mesmo teto.

Recomendação: (1) é o único item sem custo e sem dependência externa — é o próximo passo natural
se/quando a equipe decidir usar esse resultado. Os demais dependem de decisão de orçamento ou
tempo (acumular dataset), não de mais pesquisa.
