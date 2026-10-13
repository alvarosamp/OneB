# Índice de evidências — ponto de partida para a continuidade

Data: 09/10/2026. Revisão de documentos, pré-registros e componentes do repositório; sem reexecução dos experimentos. Os resultados abaixo são os registrados nas fontes locais. Não são uma nova auditoria completa dos dados históricos nem certificação de desempenho atual.

Plano de execução: [IA de recomendações](plano_ia_recomendacoes_2026-10-09.md).

## Como interpretar

- **Arquivado:** a versão/regra e o instrumento especificados falharam no protocolo documentado; não rejeita toda estratégia com nome semelhante.
- **Descritivo:** informação útil para contexto ou diagnóstico, sem aprovação direcional.
- **Experimental:** hipótese que ainda precisa de confirmação; resultado nominal positivo não equivale a vantagem.
- **Provisório por dados:** houve incidente que exige investigação/correção, preservando a versão anterior.
- **Não encontrado:** não foi localizado artefato nos caminhos inspecionados; não prova inexistência fora deles.

A evidência mais recente e mais próxima do instrumento/regra relevante prevalece sobre uma sugestão de relatório antigo. Reproduções abertas, EX5 original, futuros e CFDs devem permanecer separados.

## Evidências econômicas e de risco

| Frente | Evidência documentada | Situação e uso | Fonte |
|---|---|---|---|
| Tendência 1/3/12 meses | 164 meses, 2013–2026; 17 CFDs; média mensal −0,08%, IC 95% [−0,23%; +0,06%]; seis exclusões suspeitas após bloqueio silencioso | `NOT_SIGNIFICANT`, provisório por dados; descritivo no produto | [tsmom_v1](tsmom_v1_2026-10-08.md) |
| Calendário macro | Nasdaq/S&P/EURUSD; CPI/payroll/FOMC aumentam volatilidade histórica; direção geral sem aprovação; ouro/WTI pendentes | Contexto de risco. H2 reversão payroll/Nasdaq é hipótese secundária, não sinal aprovado | [calendar_v1](calendar_v1_2026-10-07.md) |
| Gold Fakeout aberto v1 | 1.141 operações OOS; −0,116R, IC 95% [−0,177; −0,056]; custo zero +0,008R com IC incluindo zero | Arquivado; preservar, sem otimizar para salvar v1 | [Gold aberto OOS](gold_fakeout_open_v1_oos_dukascopy_2026-10-06.md) |
| Gold Fakeout EX5 original | 4.280 operações; −0,020R, IC 95% [−0,035; −0,005]; PF 0,88; validação de sinais 93/96 | Arquivado no protocolo/feed testado | [Gold EX5 OOS](gold_fakeout_ex5_oos_dukascopy_2026-10-06.md) |
| 13X EX5 ouro H1 | 590/552 operações nas duas saídas; −0,188/−0,204R; IC 97,5% negativos | Arquivado nesse instrumento/horizonte; não confundir com 13X Nasdaq | [13X OOS](x13_ex5_oos_dukascopy_2026-10-06.md) |
| London Box EX5 ouro H1 | 1.164 operações TP1; −0,068R; PF 0,85; transferência de feed reprovada | Descritivo e arquivado para recomendação; não certifica desempenho no broker | [London OOS](london_ex5_oos_dukascopy_2026-10-07.md) |
| 100 Pips EX5 ouro H1 | 251 operações TP1; −0,008R, IC 97,5% [−0,143; +0,124]; transferência de feed reprovada | Descritivo e arquivado para recomendação | [100 Pips OOS](pips100_ex5_oos_dukascopy_2026-10-07.md) |
| Opening breakout NQ | 765 sessões totais; melhor nominal no holdout: 1.102 operações, PF 1,038, q BH 0,975; 4/8 meses positivos | Experimental. NQ contínuo de terceiro, sem rolagem explícita/bid-ask | [Intraday real](intraday_real_data_results.md) |
| Fade/pullback ouro | 1.282 sessões totais; fade 240 operações, PF 1,068, q 0,865; pullback 67 operações, resultado concentrado em três trades | Experimental; custo provisório e feed de terceiro | [Intraday real](intraday_real_data_results.md) |
| 13x momentum failure/sweep NQ | Momentum positivo no desenvolvimento, −US$ 17.722,27 no holdout; sweep também negativo | Rejeitados nessa parametrização | [Intraday real](intraday_real_data_results.md) |
| ML sobre setups | NQ L1 negativo; RF +US$ 980,47 em 99 operações, MCC 0,073/Brier 0,245; ouro com resultados pequenos/inconsistentes | Sem ganho incremental robusto; não repetir como se não tivesse sido testado | [Intraday real](intraday_real_data_results.md) |
| Filtro de tendência no Gold | Pista inicial de três trades não replicou; semana posterior quatro trades/−64,47 USD/onça | Falha de replicação da pista; não é tese geral sobre tendência | [Replicação Gold](gold_trend_replication_2026-09-27.md) |
| Freio ganho/risco líquido ≥1 | Piorou uma semana; reduziu perda na outra; semanas já consultadas | Diagnóstico econômico, sem vantagem demonstrada | [Qualidade de entrada](manual_advisory_entry_quality_2026-09-29.md) |
| Modelo diário legado | Auditoria 10/09: holdout 48,33% versus base 51,13%; AUC do retreino 0,4567 | Evidência histórica negativa; verificar versão atual antes de afirmar estado em produção | [Auditoria 10/09](../audits/ai_release_audit_2026-09-10.md) |

Os números são específicos das regras, custos e dados de cada relatório. Lucros monetários de NQ e resultados em unidade de preço de XAUUSD não devem ser somados nem convertidos em rentabilidade de conta sem contrato/exposição.

## Pesquisa pré-registrada pendente

`configs/preregistration/lab_v1.json` e `LOCK.json`, congelados em 06/10:

- Cinco ativos: XAUUSD, NAS100, SPX500, EURUSD e WTI.
- 70 combinações: sete famílias × dois parâmetros × cinco ativos.
- Descoberta: 01/03/2019–31/12/2022; confirmação: 01/01/2023–31/03/2026.
- BH q≤0,10 e pelo menos 100 operações na descoberta; confirmação apenas sobreviventes, uma vez.
- Confirmação: IC 95% da expectância >0 e média recente >0.
- Parte da confirmação XAUUSD já foi consultada em pesquisas Gold/13X; ressalva registrada no próprio protocolo.
- Em 09/10, não encontrei resultados em `D:\OneB\research\lab_v1` ou `output\lab_v1`. `app/research_paths.py` aponta para D: quando a raiz existe; ela estava acessível.

Antes de rodar: corrigir conversão de p=0 em 1, contagem incompleta de testes, inferência/dependência e proveniência do executor. Uma correção material exige nota/versionamento antes de novos resultados, sem escolha de parâmetros pelo desempenho.

## Infraestrutura disponível, sujeita a revisão

| Componente | Implementação | Próxima verificação |
|---|---|---|
| Setups e execução causal | `app/setups/`, `app/execution_sim.py`, `app/baselines.py` | Paridade replay/online, bid/ask, tempo, custos e censuras |
| Registro de oportunidades | `app/opportunity.py`, `app/opportunity_ledger.py`, rotas de oportunidades | Integridade, decisões prévias ao resultado, recusas e versões |
| Estatísticas prospectivas | `app/forward_stats.py` | Bootstrap por blocos, poder/amostra efetiva e comparação pareada |
| Qualidade do sinal | `app/signal_quality.py` | Mediana antes do split, inferência divergente, rótulo, calibração e gate absoluto |
| Assistente com evidências | `app/oneb_ai/` | Cobertura das avaliações, bloqueios, resposta estruturada e números |
| Alertas macro e tendência | `app/calendar_risk.py`, `app/trend.py`, `app/research_results/` | Estado provisório, proveniência e interpretação correta |
| Recuperação Dukascopy | `scripts/dukascopy_canary.py`, downloaders, reverify e retry | Estado real dos processos, fila/retentativa, saída completa e impacto nos dados |

Código existente não significa validação econômica nem operação contínua confirmada.

## Documentos que orientam a interpretação

| Grupo | Documentos | Uso na continuidade |
|---|---|---|
| Arquitetura e contratos | [Plano 05/10](../plans/oneb_ai_recommendation_plan.md), [dois orientadores](two_market_manual_advisors_2026-09-29.md), [contrato intraday](intraday_data_contract.md) | Reaproveitar estrutura. Prioridades de Gold/13X foram superadas por testes posteriores |
| Histórico exploratório | `vendor_indicators_results.md`, `vendor_original_results_2026-09-27.md`, `timeframes_hours_experiment_2026-09-27.md`, `trend_regime_replay_2026-09-27.md` | Registro de tentativas e períodos já vistos; pistas não viram confirmação |
| Captura/replicação | `vendor_signal_audit.md`, `vendor_original_parameters_2026-09-26.md`, `mt5_original_indicator_test_2026-09-26.md`, `original_week_validation_2026-09-27.md` | Entender identidade dos sinais, objetos, feed e causalidade |
| Aquisição e custos | `data_acquisition_2026-09-15.md`, `broker_data_followup_2026-09-27.md`, `gold_economic_pilot_2026-09-27.md`, `fontes_intradiarias_alternativas.md` | Linhagem e limites. Revalidar cobertura/custos atuais antes de usar |
| Diagnósticos iniciais | `indicator_strategy_assessment.md`, `vendor_indicators_assessment.md`, `relatorio_pesquisa_quantitativa_2026-09-10.md` | Algumas propostas já foram executadas depois. Conferir contra resultados recentes |
| Referência de produto | [Revisão Vortex 06/10](vortex_claims_review_2026-10-06.md) | Inspiração de interface e necessidade de rastreabilidade; alegações comerciais não definem meta estatística |

Nenhuma nova verificação do site Vortex foi feita nesta tarefa; o índice apenas aponta a revisão local existente.

## Atualização futura

Cada novo resultado deve registrar: ID da campanha, versão/hash da regra, instrumento/feed, dados/hash, período e histórico de consultas, custos, universo de tentativas, avaliação, decisão e relação com a versão anterior. Manter resultados negativos e correções lado a lado. Atualizar o índice por conclusão verificável, não por data de execução de script.
