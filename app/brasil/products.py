"""Catálogo das classes de investimento mais acessíveis no Brasil.

Regras de imposto e garantia conferidas em 10/2026 (Receita Federal, FGC, Tesouro
Direto, B3). Regra tributária muda: revisar quando houver lei nova e citar a data.

Cada classe tem:
- risk: 1 (muito baixo) a 5 (alto) — oscilação de preço e chance de perda;
- liquidity: quando o dinheiro volta para a conta;
- guarantee: quem garante se o emissor quebrar;
- tax: como o IR é cobrado (o simulador usa `tax_rule`);
- yield_model: como o simulador projeta o rendimento.
"""
from __future__ import annotations

# Tabela regressiva do IR em renda fixa (dias corridos → alíquota).
IR_TABLE = [(180, 0.225), (360, 0.20), (720, 0.175), (None, 0.15)]

PRODUCTS: list[dict] = [
    {
        "key": "poupanca",
        "label": "Poupança",
        "group": "renda_fixa",
        "what": "Conta remunerada do banco. Rende 0,5% ao mês + TR quando a Selic está acima de 8,5% ao ano.",
        "risk": 1,
        "liquidity": "Saque a qualquer hora, mas só rende no 'aniversário' mensal",
        "guarantee": "FGC até R$ 250 mil por CPF e instituição",
        "tax": "Isenta de IR",
        "minimum": "R$ 1",
        "good_for": "Comparação. Quase sempre há opção tão segura quanto e que rende mais.",
        "watch_out": "Com a Selic alta, rende bem menos que o CDI: perde para o Tesouro Selic e CDBs de 100% do CDI mesmo depois do IR.",
        "tax_rule": "exempt",
        "yield_model": "poupanca",
    },
    {
        "key": "tesouro_selic",
        "label": "Tesouro Selic",
        "group": "renda_fixa",
        "what": "Você empresta ao governo federal e recebe a taxa Selic. É o investimento de referência de segurança no país.",
        "risk": 1,
        "liquidity": "Resgate em qualquer dia útil (cai no mesmo dia ou no seguinte)",
        "guarantee": "Tesouro Nacional (risco do governo federal)",
        "tax": "IR regressivo de 22,5% a 15% sobre o lucro; taxa B3 de 0,20% a.a. só no que passar de R$ 10 mil",
        "minimum": "Cerca de R$ 150 (fração mínima de 1% do título)",
        "good_for": "Reserva de emergência e dinheiro que pode ser usado a qualquer momento.",
        "watch_out": "Nos primeiros dias pode render um pouco abaixo do aplicado por causa do ágio; resgatar antes de 30 dias tem IOF.",
        "tax_rule": "regressive",
        "yield_model": "selic",
        "custody": {"rate": 0.002, "exempt_up_to": 10_000},
    },
    {
        "key": "cdb_liquidez",
        "label": "CDB de liquidez diária (100% do CDI)",
        "group": "renda_fixa",
        "what": "Você empresta a um banco e recebe um percentual do CDI, a taxa que os bancos usam entre si.",
        "risk": 1,
        "liquidity": "Resgate diário (confira no produto)",
        "guarantee": "FGC até R$ 250 mil por CPF e instituição (teto global de R$ 1 milhão a cada 4 anos)",
        "tax": "IR regressivo de 22,5% a 15% sobre o lucro",
        "minimum": "Muitas vezes R$ 1 a R$ 100",
        "good_for": "Reserva de emergência, junto ou no lugar do Tesouro Selic.",
        "watch_out": "Compare o % do CDI: 100% é o mínimo razoável para liquidez diária. Bancos pequenos pagam mais porque o risco é maior, e o FGC tem limite.",
        "tax_rule": "regressive",
        "yield_model": "cdi",
        "cdi_pct": 1.0,
    },
    {
        "key": "lci_lca",
        "label": "LCI / LCA",
        "group": "renda_fixa",
        "what": "Títulos de bancos ligados a crédito imobiliário (LCI) ou do agronegócio (LCA). Isentos de IR para pessoa física.",
        "risk": 1,
        "liquidity": "Carência mínima de 9 meses (LCA) ou 12 meses (LCI); muitas só no vencimento",
        "guarantee": "FGC até R$ 250 mil por CPF e instituição",
        "tax": "Isentas de IR para pessoa física",
        "minimum": "Em geral de R$ 100 a R$ 1.000",
        "good_for": "Dinheiro que você sabe que não vai usar antes da carência.",
        "watch_out": "Compare com o CDB depois do IR: 90% do CDI isento equivale a cerca de 106% a 116% do CDI tributado, conforme o prazo.",
        "tax_rule": "exempt",
        "yield_model": "cdi",
        "cdi_pct": 0.90,
    },
    {
        "key": "tesouro_prefixado",
        "label": "Tesouro Prefixado",
        "group": "renda_fixa",
        "what": "Taxa fixa combinada na compra. Você sabe exatamente quanto terá no vencimento.",
        "risk": 2,
        "liquidity": "Pode vender em qualquer dia útil, mas pelo preço do dia (pode ganhar ou perder antes do vencimento)",
        "guarantee": "Tesouro Nacional",
        "tax": "IR regressivo de 22,5% a 15%; taxa B3 de 0,20% a.a.",
        "minimum": "Cerca de R$ 35 a R$ 40",
        "good_for": "Objetivo com data definida (2 a 5 anos), levando até o vencimento.",
        "watch_out": "Se a inflação ou os juros subirem, o preço cai antes do vencimento. A taxa só é garantida se você levar até o fim.",
        "tax_rule": "regressive",
        "yield_model": "prefixado",
        "custody": {"rate": 0.002, "exempt_up_to": 0},
    },
    {
        "key": "tesouro_ipca",
        "label": "Tesouro IPCA+",
        "group": "renda_fixa",
        "what": "Paga a inflação (IPCA) mais uma taxa fixa. Protege o poder de compra no longo prazo.",
        "risk": 2,
        "liquidity": "Pode vender em qualquer dia útil, mas pelo preço do dia (oscila bastante nos vencimentos longos)",
        "guarantee": "Tesouro Nacional",
        "tax": "IR regressivo de 22,5% a 15%; taxa B3 de 0,20% a.a.",
        "minimum": "Cerca de R$ 35 a R$ 60",
        "good_for": "Aposentadoria e objetivos acima de 5 anos.",
        "watch_out": "Em anos de alta de juros o título longo pode cair 10% a 20% no preço. Só é 'seguro' para quem leva até o vencimento.",
        "tax_rule": "regressive",
        "yield_model": "ipca_plus",
        "custody": {"rate": 0.002, "exempt_up_to": 0},
    },
    {
        "key": "fii",
        "label": "Fundos imobiliários (FIIs)",
        "group": "renda_variavel",
        "what": "Cotas de fundos que têm imóveis (galpões, shoppings, escritórios) ou títulos imobiliários. Pagam aluguel todo mês.",
        "risk": 3,
        "liquidity": "Venda na bolsa em dias úteis (D+2), pelo preço do momento",
        "guarantee": "Nenhuma: o preço oscila",
        "tax": "Rendimento mensal isento para pessoa física (regras atuais); lucro na venda paga 20%",
        "minimum": "O preço de 1 cota (muitas entre R$ 10 e R$ 150)",
        "good_for": "Renda mensal e diversificação, com prazo acima de 3 anos.",
        "watch_out": "Rendimento alto demais costuma esconder risco. Prefira fundos grandes e diversificados ou um ETF de FIIs.",
        "tax_rule": "fii",
        "yield_model": "variable",
    },
    {
        "key": "acoes_br",
        "label": "Ações brasileiras via ETF (índice)",
        "group": "renda_variavel",
        "what": "Um ETF de índice (como os que seguem o Ibovespa) compra dezenas de empresas de uma vez. Você vira sócio de um pedaço da economia.",
        "risk": 4,
        "liquidity": "Venda na bolsa em dias úteis (D+2), pelo preço do momento",
        "guarantee": "Nenhuma: pode cair 30% ou mais em crises",
        "tax": "15% sobre o lucro na venda (ETF não tem a isenção de R$ 20 mil/mês das ações)",
        "minimum": "O preço de 1 cota (em geral R$ 10 a R$ 150)",
        "good_for": "Crescimento no longo prazo (5 anos ou mais) para quem aguenta quedas sem vender.",
        "watch_out": "Nos últimos 10 anos a bolsa brasileira muitas vezes rendeu MENOS que o CDI. Ação é para prazo longo e parcela que você aguenta ver cair.",
        "tax_rule": "equity",
        "yield_model": "variable",
    },
    {
        "key": "exterior",
        "label": "Ações globais via ETF (ex.: S&P 500 em reais)",
        "group": "renda_variavel",
        "what": "ETF negociado na B3 que replica um índice de fora (como o S&P 500). Diversifica empresa e moeda.",
        "risk": 4,
        "liquidity": "Venda na bolsa em dias úteis (D+2)",
        "guarantee": "Nenhuma: oscila com a bolsa de fora e com o dólar",
        "tax": "15% sobre o lucro na venda",
        "minimum": "O preço de 1 cota",
        "good_for": "Proteger parte do patrimônio da economia brasileira e do real.",
        "watch_out": "O dólar pode cair e reduzir o ganho em reais. É parcela de diversificação, não aposta.",
        "tax_rule": "equity",
        "yield_model": "variable",
    },
]

BY_KEY = {p["key"]: p for p in PRODUCTS}

RISK_LABEL = {1: "muito baixo", 2: "baixo", 3: "médio", 4: "alto", 5: "muito alto"}


def ir_rate(days: int) -> float:
    for limit, rate in IR_TABLE:
        if limit is None or days <= limit:
            return rate
    return IR_TABLE[-1][1]


def catalog() -> list[dict]:
    return [
        {k: v for k, v in p.items() if k not in ("tax_rule", "yield_model", "custody", "cdi_pct")} | {"risk_label": RISK_LABEL[p["risk"]]}
        for p in PRODUCTS
    ]
