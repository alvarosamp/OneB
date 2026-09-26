# Auditoria independente de dados, ML e sistema quantitativo

Data da auditoria: 2026-09-10
Escopo: código, dados persistidos, features/labels, splits, treinamento, backtests, artefatos, operação e controles de risco presentes neste repositório.
Veredito: **NÃO ESTÁ PRONTO PARA LANÇAMENTO**. O uso defensável hoje é pesquisa exploratória, sem promoção a shadow operacional, paper trading de validação ou capital real.

## 1. Resumo executivo

Há controles positivos: OHLCV persistido sem duplicidade ou inconsistência básica, features majoritariamente causais, custos e slippage explícitos em parte dos simuladores, quality gate, limites de posição, registro de previsões e um modo de observação que bloqueia ações enquanto não há evidência online suficiente. O produto também declara que não envia ordens a corretoras.

Esses controles não compensam as evidências negativas:

- O modelo ativo obteve acurácia holdout de **0,4833**, abaixo do baseline de classe majoritária de **0,5113**. O retreino reproduzido nesta auditoria também obteve AUC **0,4567**, Brier **0,2532** e foi rejeitado pelo novo gate.
- Das 28 recomendações com outcome no banco, 9 foram `HIT` e 19 `FALSE_POSITIVE`: **32,14% de acerto**. A amostra é pequena, mas já é incompatível com promoção.
- O replay profundo persistido perdeu **5,06%**, com 20% de acerto e profit factor 0,12.
- O relatório de automação reprova todos os folds long e short. Nenhum fold atingiu todos os critérios.
- O dataset separa datas de treino/validação/teste, porém não purga labels de 1, 5, 10 e 20 dias nas fronteiras. A distância é de somente um dia útil nas duas fronteiras; labels de treino e validação usam preços do bloco seguinte.
- O backtest forma o sinal com o fechamento da barra `i` e executa a compra no mesmo fechamento. Sem leilão MOC submetido antes do fechamento e sem feature disponível antes da ordem, o fill não é reproduzível em produção.
- A calibração testa centenas de combinações em todas as janelas e escolhe a melhor sobre o agregado dessas mesmas janelas. Não há um teste final intocado após a seleção.
- O data gate renovado nesta auditoria falhou: os 24 históricos EOD usados pela pesquisa terminam em 2026-08-20, **21 dias corridos** antes da auditoria.
- Não existe manifesto imutável do `research_dataset_v1.csv`; o modelo ativo não registra hash do dataset, commit, configuração ou métricas de calibração. O treino exato não pode ser reconstruído.

Conclusão: a evidência disponível demonstra ausência de edge robusto e falhas de desenho experimental. Não se trata apenas de “faltar mais testes”; os resultados atuais são ativamente contrários à promoção.

## 2. Linhagem observada

```text
Tiingo EOD ajustado (primário) ─┐
yfinance ajustado (fallback) ──┼─> MarketDataService ─> CSV + meta JSON em data/raw/prices
FRED (macro oficial) ──────────┤                         │
yfinance (proxies macro) ─────┤                         ├─> indicadores/feature_vector
Finnhub (quote/notícias) ──────┤                         ├─> ResearchDataset v1
FMP (fundamentos) ─────────────┘                         │    ├─> labels futuros 1/5/10/20d
                                                        │    └─> train/validation/test
                                                        ├─> calibração de regras/backtests
                                                        └─> regressão logística
                                                             ├─> probability_model.json
                                                             └─> decision_engine
                                                                  ├─> quality_gate
                                                                  ├─> risk_engine
                                                                  ├─> RecommendationDecision/SQLite
                                                                  └─> UI/Telegram/paper simulator

Scheduler ─> coleta periódica + outcome de 5d + recalibração semanal + candidato de modelo
Logs/artefatos ─> JSON/JSONL/SQLite ─> health, scoreboard e auditorias manuais
```

Disponibilidade temporal real não está completamente modelada. Preço EOD é tratado como disponível na própria data; FRED é alinhado por data e forward-fill, mas não há vintage ALFRED nem `available_at` por observação; notícias têm `published_at` e `fetched_at`, porém o arquivo de pesquisa existente cobre apenas 248 itens, um símbolo e aproximadamente uma semana.

## 3. Achados por severidade

### Críticos

| ID | Problema | Evidência concreta | Impacto |
|---|---|---|---|
| C1 | Modelo pior que baseline | `data/probability_model.json`: holdout 0,4833 vs baseline 0,5113. Retreino reproduzido: AUC 0,4567. | A probabilidade não deve influenciar decisão ou sizing. |
| C2 | Leakage nas fronteiras | `app/research_dataset.py::_add_labels` calcula futuro antes de `_assign_splits`; `data/ml_release_audit.json` registra gap de 1 dia útil contra purge necessário de 2/6/11/21. | Labels de um bloco incorporam preços do bloco seguinte. |
| C3 | Seleção sem teste final intocado | `scripts/calibrate_decision_strategy.py::main` executa todo o grid em todos os folds e escolhe `candidates[0]`; o mesmo agregado decide confiabilidade. | O resultado escolhido é in-sample em relação à busca de hiperparâmetros. |
| C4 | Execução impossível no mesmo fechamento | `scripts/calibrate_decision_strategy.py::replay`: features e score da barra `i`; entrada por `_buy_execution(close[i])`. | Look-ahead operacional e fills otimistas. |

### Altos

| ID | Problema | Evidência concreta | Impacto |
|---|---|---|---|
| A1 | Desempenho online fraco | `data/nasdaq_monitor.db`, `recommendation_decisions`: 9 HIT, 19 FALSE_POSITIVE, 4 PENDING em 2026-09-10. | 32,14% não sustenta promoção. |
| A2 | Dados de pesquisa antigos | `data/data_reliability_gate.json`: FAIL, 24/24 símbolos `STALE_HISTORY`, último candle 2026-08-20. | Pesquisa e retreino não representam o estado atual. |
| A3 | Estratégias reprovadas | `data/automation_readiness_report.json`: 0/4 folds aprovados em long e 0/4 em short. Replay profundo: -5,06%, PF 0,12. | Não há base para automatizar decisões. |
| A4 | Índices usados como relógio comum | `paper_simulator._opportunity_score` e replays acessam ativo e benchmark pelo mesmo `iloc[i]`; o “dia” vem do primeiro ativo. | Feriado, IPO, suspensão ou lacuna desloca instrumentos e cria sinal incorreto. |
| A5 | Proveniência incompleta | Não existe `research_dataset_v1.csv.manifest.json`; modelo ativo não contém `dataset_sha256`, `git_commit`, `config_sha256` ou `trained_at`. | Dataset e treino exatos não são reconstruíveis. |
| A6 | Retreino automático sem aprovação robusta | O scheduler chama treino semanalmente. Antes desta auditoria, o script salvava qualquer candidato diretamente. | Modelo ruim podia substituir o ativo silenciosamente. Corrigido no working tree por promoção fail-closed e artefato candidato separado. |
| A7 | Universo com viés de sobrevivência | Lista fixa atual de 24 ações; não há composição histórica do Nasdaq nem ativos delistados. | Backtest pode excluir fracassos e não mede a estratégia de seleção real. |
| A8 | Dados macro não point-in-time | `fred_client` usa observações atuais e cache simples; documentação reconhece necessidade de ALFRED quando revisões importam. | Revisões macro podem contaminar backtests. |
| A9 | Dependências não reproduzíveis | `requirements.txt` usa somente limites `>=`; manifesto de notícias mostra execução em Python 3.14, enquanto CI usa 3.11/3.12. | Builds futuros podem produzir resultados diferentes ou quebrar. |

### Médios

| ID | Problema | Evidência concreta | Impacto |
|---|---|---|---|
| M1 | Validação de calendário simplista | Gates procuram gaps `>5d`, sem calendário oficial de sessões/feriados por bolsa. | Buracos menores e candles em sessões indevidas passam. |
| M2 | Cache não versionado/atômico | `MarketDataService.save_bars` sobrescreve CSV e metadata; não há snapshot imutável nem reconciliação de revisões. | Corrupção parcial e impossibilidade de reconstruir vintage. |
| M3 | Fonte única ainda pode liberar decisão | `validate_symbol_data` classifica uma fonte disponível com issue como `MEDIUM`; default de decisão exige apenas `MEDIUM`. | Falta de confirmação cruzada não bloqueia por padrão. |
| M4 | Drift limitado | `probability_model.health` observa apenas histórico de accuracy; não há PSI/KS por feature, missingness por feature ou performance por regime. | Mudanças silenciosas de distribuição podem não ser vistas. |
| M5 | Rollback/model registry insuficiente | Um único `probability_model.json` ativo e histórico apenas de métricas; sem artefatos versionados, assinatura ou promoção auditável. | Recuperação e atribuição de incidentes são frágeis. |
| M6 | Duplicidade operacional | Banco possui dois itens ativos para AAPL, NVDA e SNAP. | Coleta, alertas e amostras online podem ser duplicados. |
| M7 | Arquivo de notícias inadequado para ML | 248 linhas, um símbolo, aproximadamente 2026-08-03 a 2026-08-09; audit status `WARN`. | Não suporta validação de sinal textual ou generalização. |

### Baixos / pontos positivos

- No dataset persistido, 10.368 linhas e 24 símbolos não apresentaram datas duplicadas, missing OHLCV ou candles OHLC inválidos no gate independente.
- Máximas/mínimas recentes usam `shift(1)` antes do rolling, reduzindo look-ahead nessa feature específica.
- Tiingo usa OHLCV ajustado; o fallback yfinance usa `auto_adjust=True`.
- O decision health gate entra em `OBSERVATION_ONLY` com amostra insuficiente e em `PROTECTED` com acerto baixo.
- Existem limites de posição/exposição e bloqueio por dados no `risk_engine`.
- Não foi encontrado adapter de corretora nem envio de ordem real; o escopo atual é monitor/alerta/simulação.

## 4. Reprodutibilidade

Classificação: **baixa (1/5)**.

O dataset tem configuração e resumo, mas não hash/manifesto de inputs. Os caches possuem metadata de fonte/período, porém não hashes nem snapshots imutáveis. O modelo ativo não referencia o dataset. Requisitos não são travados por lockfile Python. O registro de experimentos existe, porém permite `git_commit="unknown"`, aceita dicionários livres e não garante que o artefato apontado exista ou corresponda ao hash registrado.

O novo candidato criado durante esta auditoria registra `trained_at`, commit, hash determinístico dos frames e hash da configuração. Isso melhora execuções futuras, mas não reconstitui retroativamente o modelo ativo nem resolve vintages de dados.

## 5. Avaliação separada

| Dimensão | Nota | Avaliação |
|---|---:|---|
| Qualidade dos dados | 2/5 | Integridade OHLCV básica é boa; frescor, point-in-time, snapshots, reconciliação, calendário e governança/licença não estão fechados. |
| Validade científica | 1/5 | Leakage de fronteira, seleção sobre as janelas avaliadas, fill no mesmo close, universo sobrevivente e múltiplas explorações impedem inferência confiável. |
| Desempenho preditivo | 1/5 | Modelo abaixo do baseline; 32,14% online; estratégias/replay reprovados. |
| Confiabilidade operacional | 2/5 | Há scheduler, logs e gates, mas faltam promoção formal, rollback completo, observabilidade de drift e atualização idempotente/versionada. |
| Controle de risco | 2/5 | Limites e observation-only são bons; faltam adapter comum entre backtest/paper/live, kill switch operacional externo e evidência de execução. |

## 6. Correções em prioridade

1. **Congelar promoção**: não usar o modelo ativo para probabilidade, veto ou sizing; manter apenas observação. O novo gate já impede que um candidato abaixo do baseline substitua o ativo.
2. **Refazer o protocolo temporal**: adicionar `feature_available_at`, `label_end_at`, purge mínimo de 20 sessões e embargo conforme sobreposição; reservar teste final imutável usado uma única vez.
3. **Corrigir relógio e execução**: alinhar todos os instrumentos por timestamp; gerar sinal após fechamento e executar somente na abertura seguinte (ou modelar MOC de maneira comprovável). Backtest deve usar OHLC intrabar para stops com regra explícita de prioridade quando stop e target ocorrem na mesma barra.
4. **Versionar dados**: ingestão incremental idempotente, escrita atômica, snapshot por execução, hash de cada input, schema version, provider timestamps, corporate actions e relatório de reconciliação.
5. **Revalidar do zero**: baseline buy-and-hold/cash/regra simples, nested walk-forward, custos em cenários 1x/2x/3x, block bootstrap, DSR/múltiplos testes, métricas por ano/regime/símbolo e intervalos de confiança.
6. **Point-in-time e universo histórico**: ALFRED/vintages macro, timestamp real de disponibilidade de notícia/fundamento e composição histórica com delistados.
7. **Operação**: registry versionado de candidato/aprovado/rejeitado, rollback testado, alertas de stale/missing/schema/drift, runbook e kill switch fora do processo de aplicação.
8. **Governança**: registrar licença e permissão para cada campo/provedor, retenção, redistribuição e termos comerciais antes de expor dados em SaaS.

## 7. Testes e controles adicionados

- `app/ml_release_audit.py`: valida schema, OHLCV, duplicidade, splits, purge de labels, recomputação de labels, manifesto, baseline do modelo, proveniência, métricas e frescor.
- `scripts/audit_ai_release.py`: gera `data/ml_release_audit.json` e retorna código 1 de forma fail-closed.
- `tests/test_ml_release_audit.py`: cobre leakage de fronteira, fixture purgada, baseline ingênuo, artefato ausente e promoção fail-closed.
- `scripts/train_probability_model.py`: agora salva primeiro `probability_model.candidate.json`, calcula AUC/Brier/erro de calibração, registra hashes e só promove quando todos os critérios passam. O modelo ativo foi preservado na reprodução desta auditoria.

Ainda recomendados: testes de alinhamento por timestamp com calendários diferentes, causalidade de cada feature, next-bar execution, PIT macro/news, corrupção concorrente do cache, rollback, alertas e parity treino/inferência end-to-end.

## 8. Checklist mensurável de lançamento

### Gate de dados

- [ ] 100% dos símbolos esperados presentes; zero duplicidades e zero OHLC inválido.
- [ ] Frescor EOD <= 1 sessão; intraday <= 2 intervalos; alerta e bloqueio automáticos.
- [ ] Manifesto com hashes de todos os inputs/outputs, commit, configuração, versão de schema e ambiente.
- [ ] Reconstrução bit a bit de três execuções históricas escolhidas aleatoriamente.
- [ ] Evidência contratual de licença/redistribuição por provedor e campo.

### Gate científico/modelo

- [ ] Purge >= maior horizonte (20 sessões) e teste final congelado.
- [ ] Nested walk-forward: seleção somente no treino interno; avaliação externa sem tuning.
- [ ] ROC-AUC com limite inferior do IC 95% > 0,50; Brier melhor que baseline; ECE <= 0,05.
- [ ] Resultado estável por ano, regime e ativo; nenhum bloco essencial depende de um único mês.
- [ ] Correção por múltiplos testes aprovada (DSR >= 0,95 ou protocolo equivalente pré-registrado).

### Gate de estratégia/execução

- [ ] Pelo menos 200 trades independentes após custos; PF > 1,20 e limite inferior bootstrap > 1,00.
- [ ] Sharpe líquido > 0,80, max drawdown <= 15% e retorno positivo em >= 5 de 6 folds.
- [ ] Continua aprovado com custos/slippage a 2x e sem fill no mesmo fechamento.
- [ ] Benchmark simples e atribuição separada de modelo, estratégia e execução.

### Gate operacional

- [ ] 60 sessões de shadow, >= 1.000 previsões, zero decisão com dado inválido e parity treino/inferência de 100%.
- [ ] Drift por feature/score/outcome e por regime, com thresholds e owner definidos.
- [ ] Candidato nunca promove automaticamente sem relatório aprovado e assinatura humana.
- [ ] Rollback e kill switch testados; RTO <= 15 min, RPO <= 1 execução.
- [ ] Logs estruturados, correlacionados, retidos e protegidos contra alteração.

## 9. Estágios e condições de avanço

| Estágio | Situação | Evidência/condição para avançar |
|---|---|---|
| Não está pronto | **Veredito atual** | C1-C4, dados stale, modelo e resultados online abaixo do baseline. |
| Pronto somente para pesquisa | Ainda não formalmente aprovado | Renovar dados, fechar manifesto/PIT, corrigir leakage/relógio e reproduzir dataset/modelo. |
| Pronto para shadow mode | Não | Gates de dados e científicos aprovados; 0 execução/sizing; telemetria completa. |
| Pronto para paper trading | Não | Shadow por 60 sessões aprovado e estratégia líquida robusta com next-bar execution. |
| Pronto para capital limitado | Não | Paper por >= 90 sessões, critérios de risco/execução aprovados, rollback/kill switch testados. |
| Pronto para produção | Não | Auditoria externa final, licença comercial, operação 24x7 e limites aprovados por responsável humano. |

## 10. Comandos reproduzíveis usados

```powershell
.\.venv\Scripts\python.exe -m pytest -q
$env:MARKET_DATA_CACHE_ONLY='true'; .\.venv\Scripts\python.exe -m scripts.data_reliability_gate
$env:MARKET_DATA_CACHE_ONLY='true'; .\.venv\Scripts\python.exe -m scripts.train_probability_model
.\.venv\Scripts\python.exe -m scripts.audit_ai_release
```

Resultados: suíte original 146 testes aprovada; 5 novos testes aprovados; data gate retornou 1 com 24 históricos stale; candidato do modelo retornou 1 e foi rejeitado; release audit retornou 1 com veredito `NOT_READY`.
