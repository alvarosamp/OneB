# A ilusão da taxa de acerto (medido em 14/10/2026)

Script: `scripts/build_win_rate_illusion.py`. Resultado: `app/research_results/win_rate_illusion.json`.

**Pergunta.** Serviços de sinais (por exemplo, a VTX) anunciam de 66% a 95% de acerto, contando como acerto qualquer toque no TP1. Que acerto teria quem entrasse **no cara ou coroa** com essa mesma regra?

**Método:**
- **Entradas:** toda hora cheia de jan/2025 a ago/2026, cerca de 9.700 por ativo.
- **Direção:** sorteada.
- **Stop:** 1,5 ATR(14) de 1 hora.
- **Execução:** compra no ask e venda no bid (spread real da Dukascopy); se stop e alvo tocam na mesma barra, conta o stop; até 24 h.

| TP1 a (em R do stop) | Nasdaq: "acerto" | Nasdaq: resultado real | Ouro: "acerto" | Ouro: resultado real |
|---|---|---|---|---|
| 0,1R | **89%** | −0,019R | **87%** | −0,044R |
| 0,2R | **82%** | −0,017R | **79%** | −0,047R |
| 0,3R | **76%** | −0,017R | **73%** | −0,045R |
| 0,5R | **66%** | −0,013R | **63%** | −0,048R |
| 1R | 49% | −0,006R | 47% | −0,040R |

## Leitura

- **A faixa anunciada sai do aleatório.** Entradas no cara ou coroa produzem de 63% a 89% de "acerto" quando o TP1 fica perto da entrada, e o resultado é **negativo em todos os casos**.
- **O que mede a qualidade de um sinal** é o resultado médio por trade (em R ou em dinheiro), depois do custo, comparado com entradas aleatórias, num histórico completo publicado antes do resultado.

**No produto:** a IA responde perguntas sobre taxa de acerto e serviços de sinais com esta tabela (ferramenta `get_win_rate_illusion`, caso `illusion-01` nas avaliações). O material serve para a página de vendas: "assertividade real".
