"""Glossário da OneB AI: termos do produto em linguagem simples, com a aula da Academia que aprofunda.

Definições sem números de mercado (o verificador não precisa conferir nada aqui).
"""
from __future__ import annotations

GLOSSARY: dict[str, dict] = {
    "atr": {
        "term": "ATR (Average True Range)",
        "aliases": ("atr", "average true range", "amplitude media", "volatilidade media"),
        "text": "É o tamanho médio do movimento do preço num período (por exemplo, por hora ou por dia), contando também os saltos entre um candle e outro. "
                "O OneB usa o ATR para dar ao stop um tamanho proporcional ao quanto o mercado costuma mexer: stop menor que o ruído normal é atingido à toa.",
        "lesson": "Volatilidade e tamanho de posição",
    },
    "r": {
        "term": "R (risco por operação)",
        "aliases": ("1r", "2r", "3r", " r ", "em r", "risco retorno", "risco-retorno", "multiplo de r"),
        "text": "R é o valor que você arrisca até o stop. Um alvo de 2R ganha o dobro do que se arrisca; perder 1R é perder exatamente o combinado. "
                "Medir em R deixa resultados de ativos e tamanhos diferentes comparáveis.",
        "lesson": "Acerto não é lucro",
    },
    "spread": {
        "term": "Spread",
        "aliases": ("spread",),
        "text": "É a diferença entre o preço de compra (ask) e o de venda (bid). Você paga o spread ao entrar e sair, então ele é um custo garantido. "
                "O que importa é o tamanho dele perto do movimento que você quer capturar: na HonorPro, o do US500.s pesa muito mais que o do US100.s.",
        "lesson": "Horário e spread: quando o custo come o movimento",
    },
    "stop": {
        "term": "Stop (stop loss)",
        "aliases": ("stop loss", "stop"),
        "text": "É o preço em que você aceita estar errado e sai com a perda planejada (1R). Ele limita o prejuízo de cada operação e define o tamanho do lote.",
        "lesson": "Volatilidade e tamanho de posição",
    },
    "lote": {
        "term": "Lote (tamanho da posição)",
        "aliases": ("lote", "lotes", "tamanho da posicao", "contrato"),
        "text": "É a quantidade que você opera. O lote certo sai da conta: risco em dinheiro dividido pela distância do stop vezes o tamanho do contrato. "
                "Se nem o lote mínimo cabe no seu risco, o trade não cabe na sua conta.",
        "lesson": "Volatilidade e tamanho de posição",
    },
    "alvo": {
        "term": "Alvo (take profit, TP)",
        "aliases": ("take profit", "tp1", "tp2", "tp3", "alvo"),
        "text": "É o preço em que você realiza o lucro. Alvos mais longe pagam mais, mas são atingidos menos vezes: no OneB cada alvo mostra a chance medida de ser atingido antes do stop.",
        "lesson": "Acerto não é lucro",
    },
    "faixa80": {
        "term": "Faixa de 80% (amplitude prevista)",
        "aliases": ("faixa de 80", "amplitude prevista", "quanto deve mexer", "previsao de amplitude"),
        "text": "É o intervalo em que a distância entre a máxima e a mínima do próximo pregão costuma ficar em 8 de cada 10 dias. "
                "Vem de um modelo testado com pré-registro; diz quanto o preço deve se mover, nunca para onde.",
        "lesson": "Volatilidade e tamanho de posição",
    },
    "taxabase": {
        "term": "Taxa-base (chance medida)",
        "aliases": ("taxa base", "taxa-base", "chance medida", "grau de confianca", "confianca"),
        "text": "É a frequência real com que um plano bateu o alvo antes do stop em milhares de entradas parecidas no passado, já com o spread. "
                "É o ponto de partida honesto: um sinal só tem valor se fizer melhor que a taxa-base, e nenhuma regra testada fez.",
        "lesson": "64 regras testadas: o que reprovou e por quê",
    },
    "preregistro": {
        "term": "Pré-registro",
        "aliases": ("pre-registro", "pre registro", "preregistro"),
        "text": "É escrever e travar a regra e o critério de aprovação ANTES de olhar o resultado. Impede ajustar a regra até ela 'funcionar' no passado, que é como a maioria dos backtests engana.",
        "lesson": "Fora da amostra e pré-registro",
    },
}
ASK_WORDS = ("o que e", "oq e", "o q e", "oque e", "o que sao", "o que significa", "significa", "explica", "explique", "como funciona", "definicao", "me ensina", "o que quer dizer")


def find_term(normalized_question: str) -> str | None:
    """Chave do termo quando a pergunta pede uma definição ("o que é ATR?")."""
    q = " " + "".join(c if c.isalnum() or c.isspace() else " " for c in normalized_question) + " "
    if not any(w in q for w in ASK_WORDS):
        return None
    for key, item in GLOSSARY.items():
        if any(a in q for a in item["aliases"]):
            return key
    return None
