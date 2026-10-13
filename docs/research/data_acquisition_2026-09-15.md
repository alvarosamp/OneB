# Expansão de dados — 2026-09-15

## Objetivo

Reduzir as limitações do estudo de indicadores para Nasdaq e ouro sem misturar
instrumentos diferentes ou criar uma série contínua sem regra de rolagem.

## Dados obtidos

| Fonte | Série | Observações | Uso |
|---|---|---:|---|
| FRED | DFII10, juro real US 10Y | 5.929 | Contexto causal do ouro e Nasdaq |
| FRED | T10YIE, breakeven US 10Y | 5.930 | Regime de inflação |
| FRED | DCOILWTICO | 6.691 | WTI diário |
| FRED | DCOILBRENTEU | 6.773 | Brent diário |
| Tiingo | QQQ/SPY M5, janeiro de 2025 | 6.139 / 6.146 | Prova de cobertura e esquema |

Todas as séries FRED são utilizadas com defasagem conservadora de um pregão.

## Coletas em andamento

- Dukascopy NAS100 CFD M5 bid/ask, 2023-01-01 a 2026-09-15. O coletor foi
  ajustado para lotes de 14 dias porque lotes de 30 dias produziam CSV vazio.
  Destino: `D:\OneB\market-data\dukascopy-nas100-2023-2026`.
- Tiingo QQQ e SPY M5 com extended hours, 2021-01-01 a 2026-09-15.
  Destino: `D:\OneB\market-data\research-ready\intermarket-v2`.

## Separação obrigatória dos instrumentos

- NAS100 Dukascopy é CFD e serve para portabilidade de sinais e modelagem de
  spread; não é evidência de execução em NQ.
- QQQ/SPY são ETFs e servem para confirmação/força relativa; não substituem
  o preço, volume, sessão ou custos dos futuros.
- A validação final de NQ e GC continua exigindo contratos CME individuais,
  BBO/trades e regra de rolagem documentada, preferencialmente via Databento
  CME Globex MDP 3.0 ou CME DataMine.

## Resultado preliminar após as novas séries macro

No Nasdaq, dólar amplo diário, WTI, breakeven de 10 anos e juros de 2/5 anos
entraram no topo do ranking de desenvolvimento/holdout. O melhor q-value de
Benjamini-Hochberg ficou em aproximadamente 0,17, ainda acima do limite de
0,10. No ouro, nenhuma nova variável oficial superou a correção de múltiplos
testes. Portanto, nenhum sinal foi promovido para paper trading.

## Retomada em 2026-09-25

### Consolidação e interface em 2026-09-26

- QQQ parcial: 313.660 barras M5, 1.308 sessões; 3.399 duplicatas e 724
  registros OHLC inválidos removidos. Último bloco completo termina antes de
  2025-04-01. Arquivo em `D:\OneB\market-data\research-ready\intermarket-v2\partial`.
- Dukascopy: 89 blocos bid; coleta interrompida por HTTP 429. Ask e consolidação
  final indisponíveis. Tiingo também retornou HTTP 429; preservar cache.
- MT5 sincronizado: 32.834 barras XAUUSD.s (145 sessões) e 2.510 US100.s
  (11 sessões). Esses CFDs não substituem futuros NQ/GC individuais.
- Auditoria ao vivo em 2026-09-25 encontrou tick do broker +180 minutos
  em relação ao UTC do computador. Não aplicar deslocamento fixo retrospectivo
  sem verificar horário de verão e histórico do servidor.
- Cartões na Mesa IA e endpoint `/api/technical/intraday-cards` apresentam
  evidência e bloqueios. Preço é ocultado quando o horário não foi verificado;
  entradas, stops, alvos e probabilidades permanecem vazios. Snapshot vencido
  sempre retorna NO_TRADE. Não existe sinal aprovado para paper trading.
- Reprodução London Box: holdout 158 trades, PF 1,107, q=0,705.
  Gap Drive proxy: 331 trades, PF 0,748, q=0,982. Resultados não constituem
  validação dos binários proprietários originais nem vantagem robusta.

Os números abaixo registram inspeções anteriores, não o estado final atual.

- A unidade `D:\` foi reconectada. A coleta Dukascopy tinha parado no bid
  de abril de 2025 e foi retomada pelos blocos já salvos. Na última inspeção
  havia 78 blocos bid de 14 dias; o ask e o arquivo consolidado ainda não
  estavam completos.
- A coleta Tiingo anterior havia terminado em HTTP 429 no QQQ de junho de
  2025. O exportador agora salva cada mês em `intermarket-v2/chunks`, de modo
  que pode ser retomado sem repetir meses já recebidos. Na última inspeção
  havia 30 blocos QQQ desde janeiro de 2021.
- A auditoria preliminar de 12 blocos QQQ de 2021 encontrou 75.161 linhas
  brutas, 878 timestamps repetidos nas fronteiras dos blocos e 91 linhas OHLC
  inconsistentes. O exportador consolida timestamps e exclui essas linhas,
  registrando a quantidade descartada no manifesto final.
- Nenhum ranking novo foi produzido com esses dados parciais. A pesquisa
  intradiária será reexecutada somente após os arquivos finais e auditoria
  de cobertura, spread e integridade.
