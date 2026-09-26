# Pesquisa quantitativa de indicadores — Nasdaq / Ouro (XAUUSD/GC) e universo de ações US

Preparado como pesquisador quantitativo / engenheiro de ML sobre o repositório **"Nasdaq" (plataforma OneB Market)**, com base em leitura direta do código, docs e resultados de auditoria já existentes no projeto, mais um framework de validação adicional entregue junto com este relatório.

**Resumo em uma frase**: a pesquisa já existente no repositório é metodologicamente séria (walk-forward com embargo, Deflated Sharpe Ratio, bootstrap por bloco de data), mas **nenhuma estratégia testada até agora sobreviveu à correção por múltiplos testes** — o único achado que se sustenta em amostras independentes é pequeno (AUC≈0.53) e não é suficiente, sozinho, para operar. Não há evidência de vantagem preditiva robusta pronta para paper trading real hoje. Isso não é uma falha do trabalho — é o resultado honesto de uma investigação bem feita, e é exatamente o tipo de conclusão que este pedido pediu para não maquiar.

---

## 1. Diagnóstico dos dados e do sistema atual

### 1.1 O que o repositório realmente é

O código em `Nasdaq/` não é um bot de execução automática. É a base do **OneB Market**, uma plataforma de monitoramento/alertas/educação (FastAPI + SPA React), com disclaimer explícito no próprio `README.md`: *"Ferramenta apenas de monitoramento e sugestão. Não executa ordens e não constitui recomendação de investimento."* Dentro dela existe uma linha de pesquisa quantitativa (scripts em `scripts/`, resultados em `data/*.json`, docs em `docs/`) que é o objeto real deste relatório, mais um indicador MQL5 solto (`mql5/Indicators/MTF_Liquidity_Structure.mq5`) que implementa a lógica multi-timeframe 4H→1H→15M→5M→1M descrita no pedido, mas que **roda isolado do backend Python e nunca foi validado em dados M1 reais do MT5**.

### 1.2 Instrumentos

| Camada | Instrumentos | Papel |
|---|---|---|
| Universo testado estatisticamente | 24 ações large-cap US (`AAPL, MSFT, NVDA, AMD, AMZN, GOOGL, META, TSLA, AVGO, NFLX, COST, ADBE, CSCO, QCOM, PLTR, SNAP, REGN, VRTX, GILD, AMGN, MDLZ, HON, PYPL, CMCSA`) — `app/paper_simulator.py` | Alvo real de todos os backtests de pesquisa (`statistical_edge_audit`, `cross_sectional_strategy_validation` etc.) |
| Benchmark | QQQ | Referência de retorno relativo |
| Contexto macro (não operado) | `NQ=F`, `ES=F`, `GC=F`, DXY, US2Y/5Y/10Y/30Y, VIX, Brent/WTI, EURUSD | Insumos do `regime_engine.py`, correlação rolling 30d |
| Multi-timeframe MQL5 (XAUUSD/NAS100) | GC=F/NQ=F como proxy diário; MT5 real nunca testado | Único componente alinhado à descrição operacional do usuário (4H→1M), mas sem validação estatística própria |

**Hipótese assumida neste relatório**: como o pedido fala em "Nasdaq e ouro" no sentido do método MT5 (4H/1H/15M/5M/1M), mas o histórico estatisticamente validável no repositório é diário e no universo de 24 ações, este relatório trata os dois como **duas linhas de pesquisa distintas com maturidade muito diferente**: (A) pesquisa cross-sectional diária em ações US (madura, com resultados negativos claros a reportar) e (B) estrutura multi-timeframe em XAUUSD/NQ (embrionária, sem dados suficientes para qualquer ranking). Se a intenção era focar só em (B), isso precisa de dados novos — ver seção 9 e recomendação final.

### 1.3 Dados

- **Ações**: Tiingo EOD ajustado, diário, 24 símbolos, **2024-08-13 a 2026-08-12** (2 anos, 501 candles/símbolo), qualidade validada (`data_reliability_gate.json`: 0 falhas, 0 gaps suspeitos >5d, 0% OHLC inválido).
- **Macro**: FRED (DXY, yields, VIX) com séries longas (US10Y: 16.135 linhas), cache local.
- **XAUUSD/NQ intraday real**: **não existe no repositório**. yfinance cacheia `15m`/`5m` como fallback operacional, não usado em nenhum backtest. O único teste envolvendo GC=F/NQ=F é um proxy diário grosseiro (`output/mtf_validation/daily_proxy_validation.json`), com **0 sinais completos no ouro e 2 no NQ** em 1-2 anos — amostra estatisticamente inutilizável.
- **Dados pagos não licenciados** (order flow, opções L2, put/call, dark pool): pesquisados e descartados por orçamento, não por falta de engenharia (`docs/data_phase_findings.md`).

### 1.4 Horizonte, sessões e objetivo atual

- Horizonte de decisão padrão da pesquisa: **5 dias úteis** (`HORIZON_DAYS=5`, `app/technical_edge.py`), com testes adicionais em 1/3/10/20 dias.
- Sessões/hora do dia: **não modeladas** — nenhum indicador de sazonalidade intradiária, dia-da-semana ou proximidade de abertura/fechamento foi encontrado no código Python. Existe apenas no nível conceitual do indicador MQL5 (lógica de sessão implícita no multi-timeframe), mas sem parametrização testável.
- Objetivo do motor de decisão (`app/decision_engine.py`): **regras determinísticas** geram a decisão (`BUY_CONTROLLED/WATCH_BUY/SELL_SHORT/WATCH_SHORT/NO_TRADE/AVOID`); um modelo de ML (`probability_model.py`, regressão logística simples) só pode **rebaixar** uma recomendação, nunca aprová-la — e hoje está com acurácia de holdout (48.33%) **abaixo do baseline de classe majoritária**, ou seja, no estado atual ele provavelmente introduz ruído, não sinal.

### 1.5 Custos operacionais

Não há um número único. O simulador "ao vivo" (`paper_simulator.py`) usa 2 bps de taxa + 5 bps de slippage (7 bps round-trip); os scripts de pesquisa/auditoria usam valores mais conservadores, entre **14 e 20 bps round-trip**. Nenhum modelo de spread em pontos/pips (mais apropriado para XAUUSD/futuros) existe — é tudo custo percentual estilo ação. **Isso é uma lacuna real se o objetivo final é migrar para o método MT5 em XAUUSD/NQ**: um spread de 2-3 pontos em ouro ou 1-2 pontos em NQ não é bem representado por um percentual fixo, especialmente em timeframes curtos (5M/1M) onde o custo domina o retorno esperado por trade.

### 1.6 Metodologia de validação já existente (o ponto mais forte do projeto)

Confirmado por leitura de código, não por documentação apenas:

- **Walk-forward sequencial com embargo de 15 dias** entre folds (`scripts/calibrate_decision_strategy.py::_walk_forward_folds`), citando Bailey & López de Prado.
- **Deflated Sharpe Ratio** (`deflated_sharpe_ratio()`) aplicado sobre grids de 288 (long) e 48 (short) configurações — e ele **reprovou as duas** (`data/decision_strategy_calibration.json`: DSR=0.000; `data/short_strategy_calibration.json`: DSR=0.000), fazendo o motor de produção cair de volta para thresholds estáticos hand-picked.
- **Correção de bug real de vazamento**: `row_index` usado como chave de junção entre símbolos foi identificado e corrigido (`scripts/research_folds.py::date_based_folds`) — um erro que teria misturado datas de calendário diferentes entre símbolos com histórico de tamanhos distintos.
- **Bootstrap por bloco de data + teste de permutação intra-data** (`scripts/regime_signal_evidence.py`), com checklist formal de "paper reporting" que inclui explicitamente: *"resultados positivos em papel não são permissão para promover o sinal a uma decisão de produção."*
- **Triple-barrier labeling** testado e descartado por AUC abaixo do baseline.

O que **não** existe e este relatório supre parcialmente (código entregue na seção 10): Purged K-Fold não-sequencial, mutual information, permutation importance de features, SHAP, HMM/clustering de regime, e um teste de significância conjunta formal (SPA/White's Reality Check) — o DSR cobre uma aproximação Gaussiana desse problema, mas assume retornos normais entre configurações, o que a própria implementação do repositório admite no docstring.

---

## 2. Catálogo de famílias de indicadores — implementado vs. lacuna

| Família | Implementado no repo | Onde | Lacuna |
|---|---|---|---|
| **Tendência** | SMA, EMA, ADX/DMI (Wilder) | `app/indicators.py` | Inclinação normalizada da média, eficiência de tendência (Kaufman ER), regressão linear rolling (slope/R²) — nenhum encontrado |
| **Momentum** | RSI (Wilder), MACD | `app/indicators.py` | ROC puro, estocástico, momentum normalizado por volatilidade (ex. RSI(ATR)) — não encontrados |
| **Volatilidade** | ATR (Wilder), Bollinger Bands, volatilidade anualizada (desvio-padrão simples) | `app/indicators.py` | Volatilidade realizada de alta frequência, Parkinson, Garman-Klass, Bollinger bandwidth explícito, vol. implícita — nenhum encontrado (o VIX entra só como nível macro, não como estrutura a termo) |
| **Volume/microestrutura** | volume_ratio (vol atual / SMA20) | `app/indicators.py` | VWAP e distância à VWAP, OBV, delta, imbalance, perfil de volume — nenhum encontrado (dados diários de ações via Tiingo não trazem volume intradiário/book, então boa parte desta família é estruturalmente inviável sem dados novos) |
| **Estrutura de mercado** | swing highs/lows, pivôs clássicos (Python); swing + BOS + liquidity sweep (MQL5) | `app/indicators.py`, `mql5/Indicators/MTF_Liquidity_Structure.mq5` | Overnight range, gap de abertura, compressão de range (squeeze) formal — Bollinger squeeze foi testado uma vez (`indicator_setup_audit`) e reprovado |
| **Sazonalidade** | — | — | **Ausente por completo**: nenhum indicador de dia-da-semana, mês, proximidade de abertura US, vencimento de opções/futuros foi encontrado em nenhum lugar do código |
| **Intermercado (Nasdaq)** | Correlação rolling 30d com DXY, yields, VIX (`regime_engine.py`); features cruzadas testadas (`dxy_x_volatility`, `us10y_x_ema_gap`, `us10y_x_volatility`) | `app/regime_engine.py`, `data/statistical_edge_audit.json` | Amplitude de mercado (advance/decline, % acima da MM50/200) e semicondutores como fator dedicado (SOX/SMH) — não encontrados como feature própria |
| **Intermercado (ouro)** | Correlação com DXY/yields via o mesmo `regime_engine.py` genérico | `app/regime_engine.py` | Juros reais (TIPS/breakeven), prata (XAG), petróleo como feature dedicada de ouro, inflação (breakeven ou CPI surprise) — não encontrados como features específicas de ouro; o sistema trata ouro só como mais um item da lista macro, sem um bloco de regras próprio |
| **Regimes de mercado** | Score de regras fixas -100/+100 (tendência/momentum/vol/estrutura), explicitamente marcado no código como *"not validated"* | `app/regime_engine.py` | HMM, clustering (KMeans/GMM) — não encontrados; o único "regime" estatisticamente validado no repo é uma dummy binária BEAR vs. não-BEAR, não uma taxonomia completa |

**Métodos de descoberta/seleção de features**:

| Método pedido | Status no repo | Status após este trabalho |
|---|---|---|
| Regressão linear/logística regularizada | Regressão logística simples, sem regularização L1/L2 explícita (`app/probability_model.py`, numpy puro) | — |
| Random Forest / XGBoost / LightGBM / CatBoost | Não encontrado em nenhum script de pesquisa | Não implementado neste trabalho (ver recomendação — dado o tamanho de amostra atual, um modelo de árvore complexo tem risco de overfitting mais alto que regressão linear regularizada; ver seção 7) |
| Permutation importance | Só permutação de LABEL para p-valor (`regime_signal_evidence.py`), não permutação de FEATURE para importância | **Entregue**: `rigorous_validation.py::walk_forward_permutation_importance` |
| SHAP | Ausente | Não incluído neste pacote (ver seção 9 — só faz sentido depois de um modelo não-linear justificado por dados suficientes) |
| Mutual information | Ausente (tudo é IC/Spearman) | **Entregue**: `rigorous_validation.py::mutual_information_ranking` |
| Seleção sequencial de features | Ausente | Não implementado (baixa prioridade com 2 anos de dados — risco de overfitting da própria seleção é alto; ver seção 7) |
| HMM / clustering de regime | Ausente | **Entregue**: `rigorous_validation.py::fit_predict_hmm_regime_walkforward` (com aviso: é candidato de pesquisa, não substitui `regime_engine.py` sem validação própria) |
| Modelos temporais (LSTM etc.) | Ausente | **Não recomendado ainda** — os baselines simples já testados (regressão logística, IC linear) não bateram o baseline na maioria dos casos; não há justificativa para pular direto a modelos mais complexos (ver seção 7) |
| Interações automáticas / symbolic regression | Parcialmente: interações manuais (`dxy_x_volatility` etc.) testadas e com sinal instável | Não implementado — risco de mineração de dados é alto demais com 2 anos de histórico |

---

## 3 e 4. Ranking de indicadores — evidências dentro e fora da amostra

**Nasdaq / universo de ações US** (única linha com dados suficientes para ranking real):

| Indicador / combinação | Evidência in-sample | Evidência out-of-sample | Veredito |
|---|---|---|---|
| `annualized_volatility` + `atr_pct`, condicionado a regime BEAR | IC=0.082, t=4.05 (depois t=4.76 com 10 anos de histórico) | **AUC=0.5321 em holdout de 5 anos nunca visto; AUC=0.5329 em reteste de 10 anos com treino/holdout totalmente diferentes** (`docs/data_phase_findings.md`, experimentos 10-12) | **Único candidato com evidência real de generalização** — pequeno, mas estável entre duas amostras independentes. Ainda não suficiente para operar sozinho. |
| `adx14` (IC por horizonte) | Melhor IC isolado no horizonte 20d: 0.0601 (t=6.255) | Walk-forward quantile validation: 20 de 32 spreads fora de amostra **negativos**, incluindo casos onde o IC de treino era positivo (`data/statistical_edge_audit.json`) | **Rejeitado como sinal isolado confiável** — parece bom in-sample, degrada fora dela |
| `low20_rebound_pct` | IC=0.0605 (t=4.69), horizonte 20d | Mesma degradação do walk-forward quantile acima | **Rejeitado** pelo mesmo motivo |
| Sinal de consenso de 8 features (technical edge score) | t-stat=3.742, hit rate 57.64%, retorno anualizado headline ~39.56% | 20/32 spreads holdout negativos no mesmo teste walk-forward | **Rejeitado** — o resultado headline é dirigido por overfitting de configuração, não sobrevive ao holdout |
| Estratégia cross-sectional (rebalance mensal) | Retorno total 23.836% em 13 meses, hit rate 61.5% | t-stat mensal = **0.872 (não significativo)**, drawdown máx -24.45%, amostra de só 13 meses | **`RESEARCH` / promissor mas não conclusivo** — amostra pequena demais para qualquer afirmação estatística |
| `rsi_reversal_long` (setup clássico) | 38 sinais, retorno médio líquido 0.59%, win rate 50%, profit factor 1.52 | Não passou na barra de produção do próprio audit (`indicator_setup_audit_2026-08-13.md`) | **`RESEARCH`** — melhor dos 8 setups clássicos testados, mas amostra de 38 trades é pequena demais para confiar |
| `revenue_growth_yoy` (fundamentals) | IC=0.031 (t=2.16) | **Inverte de sinal** entre a 1ª e 2ª metade da amostra (t=2.16 → t=-0.74) | **Rejeitado** — instabilidade de sinal entre períodos é o oposto de robustez |
| Experimento "onset de regime BEAR", features completas | AUC=0.874 | **Circular** — features derivadas do próprio label; isolando features independentes, caiu para AUC=0.571 = baseline | **Rejeitado e documentado como armadilha metodológica** pela própria equipe |
| Demais 7 dos 8 setups técnicos clássicos (`breakdown_short`, `bollinger_squeeze_breakout_long`, `volume_breakout_long`, `trend_pullback_long`, etc.) | Variado | Nenhum passou na barra de produção | **Rejeitados** |
| Probability model (regressão logística sobre 11 features) | Treino: 54.64% accuracy | Holdout: **48.33%**, abaixo do baseline de classe majoritária (~51-52%), piorando entre retreinos | **Rejeitado no estado atual** — está ativo em produção só para "downgrade", mas seu desempenho sugere que hoje ele adiciona ruído |

**Ouro (XAUUSD/GC) e Nasdaq via estrutura multi-timeframe MQL5**: **não há ranking possível com rigor hoje.** A única validação existente é o proxy diário com 0 sinais completos em ouro e 2 em NQ — abaixo de qualquer limiar mínimo de amostra para qualquer afirmação estatística (mesmo o próprio protocolo do repo exige ≥24 períodos não sobrepostos antes de mostrar métricas anualizadas — `regime_bear_economic_validation.json`). Isto não é uma rejeição do método MT5 em si; é a constatação de que **ele nunca foi testado o suficiente para ranquear**.

---

## 5. Indicadores rejeitados e motivo

| Indicador/estratégia | Motivo da rejeição |
|---|---|
| `adx14`, `low20_rebound_pct` isolados | IC in-sample positivo não replica no walk-forward holdout (maioria dos spreads negativos) |
| Sinal de consenso de 8 features | Mesmo padrão — bom in-sample, degrada fora dela; t-stat headline não sobrevive a holdout real |
| `revenue_growth_yoy` | Sinal inverte de direção entre metades da amostra — instabilidade temporal |
| Features derivadas do próprio label (onset BEAR "ingênuo") | Vazamento de informação (circularidade), não é sinal real |
| 7 de 8 setups técnicos clássicos (`breakdown_short`, `bollinger_squeeze_breakout_long`, `volume_breakout_long` bruto, `trend_pullback_long` bruto etc.) | Não passaram na barra de produção após custo de 20 bps round-trip |
| Multi-fator dentro do regime BEAR (adicionar mais features ao par vencedor) | AUC caiu de 0.5329 para 0.5186 ao somar mais features — teto genuíno de informação, não falta de tentativa |
| Calibração otimizada de thresholds (long, 288 configs) | DSR=0.000 — o melhor Sharpe encontrado (1.841) é indistinguível do máximo esperado por acaso ao testar 288 configurações (2.6115 esperado por chance) |
| Calibração otimizada de thresholds (short, 48 configs) | DSR=0.000, Sharpe médio negativo (-0.4055) |
| `probability_model.py` (regressão logística) | Holdout abaixo do baseline de classe majoritária, piorando com o tempo |
| Estrutura MQL5 aplicada a proxy diário de GC=F/NQ=F | Amostra de 0-2 sinais completos — insuficiente para qualquer conclusão, não uma rejeição do método em si |

**Nota sobre correção de múltiplos testes**: o repositório já corrige Bonferroni em pelo menos um ponto (`docs/data_phase_findings.md`) e usa DSR nas calibrações de estratégia. Este relatório recomenda complementar com **Benjamini-Hochberg (FDR)** na etapa de triagem de indicadores individuais — Bonferroni é excessivamente conservador com 40 features testadas em paralelo (exigiria p<0.00125 por teste), o que pode descartar sinais fracos-mas-reais só porque o número de testes é alto; FDR aceita uma pequena fração esperada de falsos positivos entre os aprovados, mais apropriado para um estágio de triagem que ainda será seguido por walk-forward e DSR na estratégia final. Ambas as funções (Bonferroni implícito e BH) estão disponíveis no código entregue.

---

## 6. Combinações de features com ganho incremental

A única combinação testada com evidência de ganho incremental real e **negativo** de forma instrutiva: adicionar mais features ao par `annualized_volatility + atr_pct` dentro do regime BEAR **piorou** o AUC (0.5329 → 0.5186, experimento #13 de `docs/data_phase_findings.md`). Isso é evidência de um teto de informação genuíno nesse subconjunto de dados, não de falta de tentativa — e é exatamente o tipo de teste de ganho incremental que o pedido original exige (avaliar utilidade incremental, não só poder isolado).

Nenhuma outra combinação testada no repositório passou em um teste formal de ganho incremental pareado por fold. O código entregue (`incremental_gain_test`) formaliza esse teste (Wilcoxon pareado entre scores de fold do baseline vs. baseline+candidato) para qualquer indicador novo que for testado daqui para frente — a regra prática recomendada: **um indicador só deve entrar no conjunto de produção se (a) tiver AUC/IC individual acima do baseline em holdout independente, E (b) passar no teste de ganho incremental pareado ao ser somado ao conjunto já aprovado, E (c) sobreviver à correção de múltiplos testes (BH ou DSR/SPA conforme o nível — feature ou estratégia).**

---

## 7. Comparação entre modelos simples e complexos

Dado o tamanho real de amostra disponível (2 anos, 24 símbolos, ~10.368 linhas painel, mas com forte correlação cross-sectional dentro do mesmo dia — o número de "observações efetivamente independentes" é muito menor que 10.368, algo próximo do número de dias únicos, ~500), a recomendação é:

1. **Baseline 0 (obrigatório, e já existe implicitamente)**: buy-and-hold do universo / QQQ. O repositório já compara contra QQQ como benchmark relativo.
2. **Baseline 1**: regra de decisão simples de 1-2 features (o que hoje já domina em `decision_engine.py`) — supera qualquer modelo complexo se o modelo complexo não bater ele com folga estatisticamente significativa.
3. **Regressão logística regularizada (L1/L2)**: ainda não testada no repo (`probability_model.py` é sem regularização) — deveria vir ANTES de qualquer árvore/boosting, dado o tamanho de amostra.
4. **Random Forest / XGBoost / LightGBM**: **não recomendado ainda** com o histórico atual. Com ~500 dias efetivos e múltiplos regimes distintos (o próprio repo identificou ≥2 quebras estruturais violentas em mar/2025 e fev-mar/2026), um modelo de árvore com capacidade suficiente para capturar não-linearidades tem alta propensão a decorar ruído específico de regime — e o próprio experimento #13 mostra que MAIS features já pioram o resultado com um modelo linear simples. Adicionar capacidade de modelo antes de esgotar a robustez do modelo simples inverte a ordem certa de investigação.
5. **Modelos temporais (LSTM, temporal CNN, etc.)**: **não recomendado** — nem os baselines simples bateram consistentemente a barra de significância; não há justificativa para pular para modelos que exigem ainda mais dados e são ainda mais propensos a overfitting sutil (leakage temporal é mais fácil de introduzir acidentalmente em arquiteturas sequenciais).

Conclusão desta seção: **o teto do projeto hoje não é a complexidade do modelo, é o tamanho e a qualidade da amostra e a real existência (ou não) de sinal explorável líquido de custo.** Investir em XGBoost/LSTM agora seria resolver o problema errado.

---

## 8. Regimes em que cada sinal funciona ou falha

- **`annualized_volatility + atr_pct`**: funciona (fracamente, IC≈0.08, AUC≈0.53) especificamente dentro do **regime BEAR** definido pelo `regime_engine.py`. Não há evidência de que funcione em regime de alta ou lateral — não foi testado separadamente nesses regimes no material disponível (lacuna a fechar, ver seção 9).
- **Setups técnicos clássicos** (`indicator_setup_audit`): testados sobre 2 anos "pooled", sem quebra por regime — não se sabe se `rsi_reversal_long` (o único setup com resultados razoáveis) funciona igualmente bem em alta e baixa vol, o que é uma lacuna real.
- **Estratégia cross-sectional mensal**: 13 meses é curto demais para cobrir múltiplos regimes de forma que permita qualquer afirmação sobre estabilidade entre eles.
- **Regime engine (score -100/+100)**: nunca foi validado quantitativamente contra outcomes reais — é hand-picked. O próprio código admite isso.
- **HMM de regime (entregue neste trabalho)**: é um candidato para substituir/complementar o regime hand-picked por algo aprendido dos dados, mas **ainda não foi rodado contra os dados reais do repositório neste trabalho** (ver seção 9 — seria o primeiro passo de follow-up).

---

## 9. Proposta de experimento walk-forward reproduzível

Protocolo recomendado para qualquer indicador novo ou re-teste de indicador existente:

1. **Split**: `PurgedKFoldEmbargo` (código entregue) com `n_splits=5`, `label_horizon_days` igual ao horizonte testado, `embargo_days >= label_horizon_days` (para o horizonte de 5 dias já usado no repo, embargo mínimo de 5 dias; o repo já usa 15 dias no walk-forward sequencial, que é ainda mais conservador — manter esse padrão quando possível).
2. **Seleção de features**: calcular IC (já existe, `scripts/cross_sectional_ic.py`) + `mutual_information_ranking` (novo) SOMENTE no fold de treino de cada iteração — nunca no dataset completo.
3. **Importância**: `walk_forward_permutation_importance` (novo) para confirmar que a importância aparente de uma feature não é artefato de correlação espúria com outra já incluída.
4. **Modelo**: começar por regressão logística L1/L2 (baseline ainda não testado no repo) antes de qualquer árvore/boosting.
5. **Ganho incremental**: `incremental_gain_test` (novo) comparando conjunto atual de produção (`FEATURE_NAMES` do `paper_simulator.py`) vs. conjunto atual + candidato.
6. **Custo e métricas financeiras**: `financial_metrics` com `TradeCosts(round_trip_bps=20)` como padrão conservador (alinhado ao `indicator_setup_audit`), reportando Sharpe, Sortino, max drawdown, profit factor, expectancy e contagem de trades por fold — **rejeitar automaticamente qualquer resultado com menos de ~20-24 trades não sobrepostos**, seguindo o próprio limiar que o repositório já usa (`regime_bear_economic_validation.json`).
7. **Correção de múltiplos testes**: se testando N indicadores em paralelo → `benjamini_hochberg` sobre os p-valores individuais. Se testando N configurações de UMA estratégia → `deflated_sharpe_ratio` (versão corrigida por skew/kurtosis entregue aqui) e/ou `spa_test_pvalue` (teste formal de Hansen/White, não só a aproximação Gaussiana do DSR).
8. **Regime**: repetir os passos 2-7 condicionado a cada regime (via `regime_engine.py` atual E via `fit_predict_hmm_regime_walkforward` como candidato alternativo), reportando separadamente — nunca "pooled" sem checar se o resultado é dirigido por um único regime, como já aconteceu no experimento #10-13 do próprio repo.
9. **Amostra mínima**: qualquer métrica anualizada só deve ser reportada com ≥24 períodos de retorno não sobrepostos, replicando o próprio limiar do repositório.

Follow-ups concretos recomendados (não executados neste trabalho por dependerem de dados que precisam ser buscados/gerados):
- Rodar `fit_predict_hmm_regime_walkforward` sobre o painel de 24 símbolos e comparar a taxonomia de regime resultante contra o `regime_engine.py` atual (concordância, e se o IC do par vencedor muda por regime aprendido vs. regime por regra).
- Exportar candles M1 reais do MT5 para XAUUSD e NAS100 (o script `scripts/validate_mtf_liquidity.py --csv` já existe no repo para consumir esse CSV — só falta o dado) e rodar a mesma bateria de walk-forward + custo em pontos/pips sobre a lógica de estrutura multi-timeframe.
- Modelar custo em pontos/spread real para XAUUSD/NQ em vez de bps percentuais, antes de qualquer teste sério nesses instrumentos.

---

## 10. Código, configurações e documentação para repetir a análise

Entregue junto com este relatório: **`rigorous_validation.py`** — módulo Python autocontido (numpy/pandas/scipy/scikit-learn; hmmlearn opcional) implementando:

- `PurgedKFoldEmbargo` — split temporal com purge de sobreposição de label + embargo
- `mutual_information_ranking` — MI classif./regressão, fit só no treino
- `walk_forward_permutation_importance` — importância de feature por embaralhamento, calculada corretamente por fold
- `probabilistic_sharpe_ratio` e `deflated_sharpe_ratio` — versão com correção de skew/kurtosis (a versão do repositório assume normalidade)
- `spa_test_pvalue` — aproximação do teste de Hansen (SPA) / White's Reality Check via bootstrap de bloco estacionário
- `benjamini_hochberg` — correção de FDR para triagem de múltiplos indicadores
- `fit_predict_hmm_regime_walkforward` — regime não-supervisionado (HMM Gaussiano, fallback KMeans), treinado e decodificado sem olhar o futuro
- `financial_metrics` / `net_returns_from_signal` — métricas líquidas de custo (retorno, Sharpe, Sortino, max DD, profit factor, expectancy, win rate), com custo aplicado só na troca de posição
- `classification_metrics` — AUC, precision, recall, balanced accuracy, MCC, Brier
- `incremental_gain_test` — teste pareado (Wilcoxon) de ganho incremental entre conjuntos de features

O arquivo inclui um self-test executável (`python rigorous_validation.py`) com dados sintéticos que valida o pipeline de ponta a ponta (confirmado rodando nesta sessão, sem erros). Este módulo é intencionalmente desacoplado do resto do repositório para poder ser importado por qualquer script em `scripts/` sem gerar dependência circular — ele espera apenas DataFrames pandas no mesmo formato já usado por `scripts/statistical_edge_audit.py` (coluna de data de calendário real, não `row_index`).

---

## 11. Recomendação final

| Item avaliado | Classificação |
|---|---|
| Sinal `annualized_volatility + atr_pct` em regime BEAR | **Experimental** — evidência real e replicada (duas amostras independentes, AUC≈0.53), mas pequena demais para operar sozinha. Vale continuar pesquisando (testar em outros regimes, testar combinação com custo real, aumentar amostra) antes de qualquer promoção. |
| Estratégia cross-sectional mensal (23.8% em 13 meses) | **Precisa de mais dados** — t-stat não significativo (0.872), amostra de 13 meses é curta demais para qualquer conclusão, apesar do retorno headline atrativo. |
| `rsi_reversal_long` e demais setups técnicos clássicos | **Rejeitado para produção** — não passaram na barra após custo; `rsi_reversal_long` isolado é `RESEARCH` (38 trades, insuficiente). |
| Calibração de thresholds long/short (grid search) | **Rejeitado** — DSR=0.000 nos dois casos; o motor de produção corretamente não usa essa calibração. |
| `probability_model.py` atual | **Rejeitado no estado atual** — abaixo do baseline em holdout; recomenda-se pausar seu uso até retreino com regularização e reavaliação. |
| Estrutura multi-timeframe MQL5 em XAUUSD/NQ (o método operacional descrito no pedido) | **Precisa de mais dados** — não existe evidência estatística válida ainda, positiva ou negativa; a lacuna é de dados M1 reais, não de metodologia (o script de validação já existe, só falta o CSV do MT5). |
| Sistema como um todo, para paper trading real com dinheiro (mesmo que fictício) guiado por essas features | **Não aprovado para paper trading ainda** — nenhuma combinação testada até agora sobrevive simultaneamente a: holdout independente + custo realista + correção de múltiplos testes + amostra mínima de trades. O próprio `automation_readiness_report.json` do repositório já chega à mesma conclusão (`HUMAN_APPROVAL_REQUIRED`). |

**Não há, hoje, evidência robusta de vantagem preditiva líquida de custo, estatisticamente significativa após correção para múltiplos testes, e estável entre regimes/períodos, para nenhum indicador ou combinação testada.** O achado mais promissor (volatilidade condicionada a regime BEAR) é real, mas pequeno e insuficiente sozinho. Isso é uma conclusão negativa confiável, não um resultado otimista construído sobre overfitting — e é exatamente o tipo de honestidade que a pesquisa quantitativa séria exige antes de arriscar capital, mesmo em paper trading.
