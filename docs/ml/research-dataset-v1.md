# ResearchDataset v1

Base inicial para treinar e validar as futuras IAs do OneB.

## Objetivo

Transformar candles confiaveis em uma tabela de pesquisa com:

- dados diarios limpos por ativo;
- indicadores tecnicos calculados de forma reproduzivel;
- contexto relativo contra QQQ;
- retornos futuros em 1, 5, 10 e 20 dias;
- drawdown e runup futuros;
- label simples de 5 dias: `good`, `neutral` ou `bad`;
- separacao temporal entre `train`, `validation` e `test`.

Essa base ainda nao e um modelo de compra/venda. Ela e o alimento limpo para a IA comecar a aprender.

## Como gerar

```bash
python -m scripts.build_research_dataset --period 2y --min-rows 240
```

Saidas:

- `data/research/research_dataset_v1.csv`
- `data/research/research_dataset_v1.summary.json`

## Resultado da primeira geracao

Gerado em 2026-08-13 com historico de 2 anos.

- Status: `PASS`
- Ativos: 24
- Linhas prontas para pesquisa: 10.368
- Features numericas: 33
- Fonte dos candles: Tiingo
- Benchmark relativo: QQQ
- Issues do dataset: nenhuma

## O que cada linha representa

Cada linha e uma fotografia de um ativo em uma data.

Exemplo conceitual:

```text
AAPL em 2025-03-10:
  indicadores conhecidos ate 2025-03-10
  retorno futuro depois de 5 dias
  drawdown futuro depois de 5 dias
  label_5d = good/neutral/bad
```

As features usam somente informacao conhecida ate a data da linha. Os retornos futuros entram apenas como labels para treino e validacao.

## Splits

O dataset separa as datas em ordem cronologica:

- `train`: primeiras 70% das datas;
- `validation`: proximas 15%;
- `test`: ultimas 15%.

Isso evita que a IA aprenda olhando o futuro.

## Proximo passo

Usar essa base para criar o primeiro modelo simples:

- ranking dos ativos da watchlist;
- probabilidade de retorno positivo em 5 dias;
- explicacao com as principais features;
- bloqueio quando a qualidade do dado ou do modelo estiver fraca.
