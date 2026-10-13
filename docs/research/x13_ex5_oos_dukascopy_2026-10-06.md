# 13X (EMA13 + DMI) — EX5 ORIGINAL: teste fora da amostra 2019–2026 (XAUUSD, H1)

**Veredito pré-registrado: ARCHIVE** nas duas hipóteses de saída. Nenhuma ordem.

## Desenho

`configs/preregistration/x13_ex5_oos_dukascopy.json` (LOCK antes de qualquer
execução). O 13X não desenha objetos de entrada: os sinais estão em buffers.
Mapeamento objetivo, sem olhar resultado, confirmado nos 7 anos:

| Buffer | Âncora | Candle | Significado |
|---|---|---|---|
| 2 | mínima (100%) | de alta (99,1%) | seta de compra |
| 3 | máxima (100%) | de baixa (99,8%) | seta de venda |
| 4 | máxima (100%) | — | X |
| 5 | mínima (100%) | — | X |

Hipótese principal: X na máxima encerra compra, X na mínima encerra venda.
Secundária: o inverso. Bonferroni (IC de decisão a 97,5%). O vendedor não dá
stop: stop de proteção 2×ATR(14) H1 (define 1R); limite de 5 dias.

## Validação

| Passo | Resultado |
|---|---|
| A: Model=1 vs ticks reais (XAUUSD.s, 1 semana) | 19/19 marcas idênticas — passou |
| B: XAUUSD.dk vs HonorPro (1 semana, registrado) | 15/19 (recall 79%) — **reprovou por uma marca** |
| B ampliado (abr–set/2026, registrado DEPOIS da reprovação, divulgado) | 407/446 (recall 91%, precisão 93%) — passou; setas de venda 18/22 |

O veredito usa a validação ampliada; a reprovação original fica registrada aqui.

## Resultado (mar/2019–mar/2026, custos conservadores)

7.395 marcas (437 compras, 411 vendas, 6.547 X).

| Hipótese | Trades | Expectância | IC 97,5% | Acerto | PF | Recente (abr/25–mar/26) |
|---|---:|---:|---|---:|---:|---:|
| Principal | 590 | **−0,188R** | −0,271 a −0,098 | 24% | 0,57 | −0,159R |
| Secundária | 552 | **−0,204R** | −0,298 a −0,108 | 32% | 0,59 | −0,206R |

As duas são claramente negativas, também no período recente. O 13X entra depois
de um candle forte na direção do sinal e o movimento não continua o bastante
para pagar a saída.

## Observação (hipótese nova, NÃO testada)

Um sinal consistentemente negativo pode, em tese, ter valor ao contrário. Isso
não pode ser concluído destes mesmos dados (seria escolher pelo resultado).
Se for de interesse, registrar como hipótese nova e testar em outro ativo ou em
dados futuros (shadow), com custos dos dois lados.
