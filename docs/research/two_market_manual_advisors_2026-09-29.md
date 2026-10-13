# Dois orientadores manuais, evidências separadas

O software não abre, altera nem encerra posições. Sua saída pretendida é um
plano para decisão humana: `BUY_CANDIDATE`, `SELL_CANDIDATE` ou `NO_TRADE`,
com instante da quote, preço executável estimado, stop, alvo, tempo limite de
saída e razões auditáveis. Nenhuma probabilidade de acerto é inferida de score.

Políticas independentes em `configs/manual_advisors_v1.json`; avaliação comum em
`scripts/two_market_advisory.py`. O motor exige o **mesmo símbolo e família**
no sinal, na quote e na política. Falta de sinal, quote, custo, validação,
relógio reconciliado ou relação líquida adequada resulta em `NO_TRADE`.
Quotes inválidas também falham fechadas. Um candidato futuro continuaria sendo
somente apoio humano, sem acesso a funções de ordem ou credenciais MT5.

| Mercado | Instrumento pretendido no broker | Gatilho em pesquisa | Impedimento atual |
|---|---|---|---|
| Ouro | XAUUSD.s CFD/spot, M10 | EX5 Gold Fakeout original | Apenas dez dias com ticks; replicação negativa; comissão/slippage e relógio não certificados |
| Nasdaq | US100.s CFD, M1 | EX5 Nasdaq Gap Drive original | Sem gatilho original certificado na captura; custos da conta desconhecidos; sessão/relógio não certificados |

NQ contínuo de terceiros, NAS100 da Dukascopy e US100.s da HonorPro **não são
o mesmo instrumento**. O NQ histórico é útil para formular hipóteses de
breakout, não para comprovar execução no US100.s. O ano de NAS100 bid/ask de
outro feed pode testar transferência, mas não substitui quotes HonorPro nem
contrato NQ/MNQ individual. Também não misturar GC com XAUUSD.s.

Status atual dos dois orientadores: **experimental / não aprovado para paper
trading**. O filtro de relação líquida ≥1,0 foi testado retrospectivamente no
ouro: piorou a primeira semana e reduziu, sem eliminar, a perda na segunda.
Ver `manual_advisory_entry_quality_2026-09-29.md`. Isso é um requisito de
qualidade da entrada, não evidência de vantagem.

Próximas experiências, sem escolher parâmetros pelos resultados já vistos:

1. Ouro: congelar regra, custos e limite de quote antes de capturar novas
   semanas com o EX5 e ticks bid/ask do **mesmo** símbolo. Avaliar estabilidade
   por dia e mês, posições censuradas, horários e ganho incremental do freio.
2. Nasdaq: primeiro obter gatilho causal e sessão correta do EX5 no US100.s;
   em seguida capturar bid/ask histórico do broker e especificação de custo.
   Enquanto isso, manter opening breakout no NQ como hipótese separada, não
   transplantar seu ranking para o CFD.
3. Só após amostra ampla e validação temporal realmente posterior: comparar
   baselines, corrigir múltiplos testes, verificar calibração se houver modelo
   probabilístico e liberar cartões **apenas para paper trading manual**.

Reprodução rápida: `python -m pytest tests/test_original_gold_ticks.py
tests/test_two_market_advisory.py -q`. Os testes verificam segregação dos
instrumentos, impedimento por evidência/custos, cálculo bid/ask, relógio,
quote inválida e ausência de execução automática.
