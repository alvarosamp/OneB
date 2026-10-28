"""Simulador educacional: quanto investir em cada CLASSE, por quê, e quanto pode virar.

Fluxo:
1. Perfil (conservador, moderado, arrojado) a partir de prazo, reação a quedas e experiência.
2. Reserva de emergência primeiro (6 meses de gastos) em produtos de resgate imediato.
3. Divisão do resto por classe, conforme o prazo e o perfil, com o motivo de cada parte.
4. Projeção mês a mês, líquida de IR (tabela regressiva por aporte) e taxa de custódia,
   comparada com a poupança. Renda variável usa 2.000 cenários (Monte Carlo com semente
   fixa) e mostra a faixa de 80% em vez de um número único.

Premissas (todas devolvidas na resposta e editáveis): CDI, Selic e IPCA atuais
constantes no prazo todo; IPCA+ e prefixado com a taxa informada; renda variável com
retorno esperado = CDI + prêmio e volatilidade histórica típica. Não há garantia.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from app.brasil.products import BY_KEY, ir_rate
from app.brasil.rates import poupanca_annual

DISCLAIMER = (
    "Simulação educacional por classe de investimento, com premissas declaradas. Não é recomendação de compra "
    "de nenhum ativo específico nem consultoria (Resoluções CVM 19 e 20). Rentabilidade passada e projetada não "
    "é garantia. Antes de investir, confira o produto, a instituição e a garantia."
)

# Renda variável: (prêmio sobre o CDI em p.p. ao ano, volatilidade anual).
# Volatilidades típicas medidas em 10 anos: Ibovespa ~24%, S&P 500 em reais ~18%, IFIX ~11%.
VARIABLE_DEFAULTS = {"acoes_br": (2.0, 0.24), "exterior": (1.0, 0.18), "fii": (1.0, 0.11)}
CORRELATION = np.array([
    [1.0, 0.25, 0.55],   # acoes_br
    [0.25, 1.0, 0.10],   # exterior
    [0.55, 0.10, 1.0],   # fii
])
VARIABLE_ORDER = ["acoes_br", "exterior", "fii"]
FII_TAX = 0.20
EQUITY_TAX = 0.15
PATHS = 2000

PROFILE_TEXT = {
    "conservador": "Prioriza não ver o dinheiro cair. Quase tudo em renda fixa, com resgate fácil ou prazo definido.",
    "moderado": "Aceita oscilação numa parte do dinheiro para buscar mais retorno no médio e longo prazo.",
    "arrojado": "Aguenta quedas fortes no caminho porque o prazo é longo e o foco é crescer o patrimônio.",
}

# Divisão por faixa de prazo e perfil (percentuais somam 100).
ALLOCATIONS = {
    "curto": {p: {"tesouro_selic": 40, "cdb_liquidez": 30, "lci_lca": 30} for p in PROFILE_TEXT},
    "medio": {
        "conservador": {"tesouro_selic": 30, "lci_lca": 30, "tesouro_prefixado": 20, "tesouro_ipca": 20},
        "moderado": {"tesouro_selic": 20, "lci_lca": 25, "tesouro_prefixado": 15, "tesouro_ipca": 20, "fii": 10, "acoes_br": 10},
        "arrojado": {"tesouro_selic": 15, "lci_lca": 15, "tesouro_prefixado": 10, "tesouro_ipca": 20, "fii": 15, "acoes_br": 15, "exterior": 10},
    },
    "longo": {
        "conservador": {"tesouro_selic": 25, "lci_lca": 15, "tesouro_ipca": 40, "fii": 10, "acoes_br": 5, "exterior": 5},
        "moderado": {"tesouro_selic": 15, "tesouro_ipca": 35, "fii": 15, "acoes_br": 20, "exterior": 15},
        "arrojado": {"tesouro_selic": 10, "tesouro_ipca": 25, "fii": 15, "acoes_br": 30, "exterior": 20},
    },
}
RESERVE_SPLIT = {"tesouro_selic": 50, "cdb_liquidez": 50}


@dataclass
class SimInput:
    initial: float
    monthly: float
    months: int
    goal: str  # reserva | objetivo | aposentadoria
    has_reserve: bool = True
    monthly_expenses: float | None = None
    drop_reaction: str = "esperar"  # vender | esperar | comprar
    experience: str = "nenhuma"  # nenhuma | pouca | boa
    ipca_real_rate: float = 6.5
    prefixado_rate: float | None = None
    equity_premium: float | None = None
    rates: dict = field(default_factory=dict)


def brl(x: float) -> str:
    return "R$ " + f"{x:,.0f}".replace(",", ".")


def horizon_bucket(months: int) -> str:
    return "curto" if months < 24 else "medio" if months < 60 else "longo"


def profile(inp: SimInput) -> dict:
    factors = []
    horizon_pts = 0 if inp.months < 24 else 1 if inp.months < 60 else 2
    reaction_pts = {"vender": 0, "esperar": 1, "comprar": 2}.get(inp.drop_reaction, 1)
    exp_pts = {"nenhuma": 0, "pouca": 1, "boa": 2}.get(inp.experience, 0)
    score = horizon_pts + reaction_pts + exp_pts
    key = "conservador" if score <= 2 else "moderado" if score <= 4 else "arrojado"
    factors.append(f"Prazo de {_months_text(inp.months)}: " + ["curto, o dinheiro não pode oscilar", "médio, permite um pouco de oscilação", "longo, dá tempo de atravessar quedas"][horizon_pts] + ".")
    factors.append({"vender": "Você venderia numa queda de 20%: isso transforma oscilação em prejuízo, então a parte de bolsa fica menor.",
                    "esperar": "Você esperaria passar uma queda de 20%: essa paciência é o que faz a renda variável funcionar.",
                    "comprar": "Você aproveitaria uma queda para comprar mais: perfil que tolera oscilação."}.get(inp.drop_reaction, ""))
    factors.append({"nenhuma": "Sem experiência ainda: começamos pelo mais simples e explicamos cada passo.",
                    "pouca": "Alguma experiência: dá para incluir classes com oscilação, sem exagero.",
                    "boa": "Boa experiência: você já conhece oscilação de preço."}.get(inp.experience, ""))
    if inp.drop_reaction == "vender" and key == "arrojado":
        key = "moderado"
        factors.append("Mesmo com prazo longo, limitamos a moderado porque vender na queda é o erro que mais custa.")
    if inp.months < 24 and key != "conservador":
        key = "conservador"
        factors.append("Com menos de 2 anos, qualquer perfil fica em renda fixa: não há tempo para recuperar uma queda.")
    return {"key": key, "label": key.capitalize(), "text": PROFILE_TEXT[key], "factors": [f for f in factors if f]}


def _months_text(m: int) -> str:
    if m < 12:
        return f"{m} {'mês' if m == 1 else 'meses'}"
    years = m / 12
    return f"{years:.0f} {'ano' if round(years) == 1 else 'anos'}" if m % 12 == 0 else f"{years:.1f} anos".replace(".", ",")


def _annual_rate(key: str, inp: SimInput) -> float:
    """Taxa nominal anual (%) de produtos de renda fixa."""
    r = inp.rates
    p = BY_KEY[key]
    model = p["yield_model"]
    if model == "poupanca":
        return poupanca_annual(r["selic"])
    if model == "selic":
        return r["selic"] - 0.05  # Tesouro Selic rende levemente abaixo da Selic meta (Selic over)
    if model == "cdi":
        return r["cdi"] * p.get("cdi_pct", 1.0)
    if model == "prefixado":
        return inp.prefixado_rate if inp.prefixado_rate is not None else round(r["cdi"] - 1.0, 2)
    if model == "ipca_plus":
        return ((1 + r["ipca_12m"] / 100) * (1 + inp.ipca_real_rate / 100) - 1) * 100
    raise ValueError(key)


def _fixed_income_path(key: str, contrib: np.ndarray, inp: SimInput) -> tuple[np.ndarray, np.ndarray]:
    """Valor bruto e líquido (se resgatado) ao fim de cada mês 0..n.

    Cada aporte é um lote com a sua própria idade para a tabela regressiva do IR.
    """
    n = len(contrib) - 1
    p = BY_KEY[key]
    rm = (1 + _annual_rate(key, inp) / 100) ** (1 / 12) - 1
    custody = p.get("custody")
    lots = np.zeros(n + 1)
    basis = np.zeros(n + 1)
    gross = np.zeros(n + 1)
    net = np.zeros(n + 1)
    for t in range(n + 1):
        if t > 0:
            lots[:t] *= 1 + rm
            if custody:
                total = lots[:t].sum()
                fee = custody["rate"] / 12 * max(0.0, total - custody["exempt_up_to"])
                if total > 0:
                    lots[:t] *= 1 - fee / total
        lots[t] += contrib[t]
        basis[t] += contrib[t]
        total = lots[: t + 1].sum()
        gross[t] = total
        if p["tax_rule"] == "exempt":
            net[t] = total
        else:
            gains = lots[: t + 1] - basis[: t + 1]
            ages = (t - np.arange(t + 1)) * 30
            rates = np.array([ir_rate(int(a)) for a in ages])
            net[t] = total - float(np.sum(np.clip(gains, 0, None) * rates))
    return gross, net


def _variable_paths(contribs: dict[str, np.ndarray], inp: SimInput, seed: int = 7) -> tuple[np.ndarray, dict]:
    """Patrimônio líquido de IR por cenário (PATHS × n+1) somando as classes de renda variável."""
    keys = [k for k in VARIABLE_ORDER if k in contribs]
    n = len(next(iter(contribs.values()))) - 1
    if not keys:
        return np.zeros((PATHS, n + 1)), {}
    cdi = inp.rates["cdi"]
    ipca = inp.rates["ipca_12m"]
    idx = [VARIABLE_ORDER.index(k) for k in keys]
    params = {}
    mus, sigmas = [], []
    for k in keys:
        prem, vol = VARIABLE_DEFAULTS[k]
        if k == "acoes_br" and inp.equity_premium is not None:
            prem = inp.equity_premium
        expected = cdi + prem
        params[k] = {"expected_annual_pct": round(expected, 2), "volatility_pct": round(vol * 100, 1)}
        sm = vol / math.sqrt(12)
        mus.append(math.log(1 + expected / 100) / 12 - sm * sm / 2)
        sigmas.append(sm)
    corr = CORRELATION[np.ix_(idx, idx)]
    cov = np.outer(sigmas, sigmas) * corr
    rng = np.random.default_rng(seed)
    shocks = rng.multivariate_normal(np.array(mus), cov, size=(PATHS, n)) if n else np.zeros((PATHS, 0, len(keys)))
    total_net = np.zeros((PATHS, n + 1))
    # FII: parte do retorno vem como rendimento mensal isento (reinvestido, entra no custo);
    # o resto é valorização da cota, tributada em 20% na venda.
    fii_yield_m = max(0.0, (1 + (cdi + VARIABLE_DEFAULTS["fii"][0]) / 100) / (1 + ipca / 100) - 1)
    fii_yield_m = (1 + fii_yield_m) ** (1 / 12) - 1
    for j, k in enumerate(keys):
        c = contribs[k]
        value = np.zeros(PATHS)
        basis = np.zeros(PATHS)
        tax = FII_TAX if k == "fii" else EQUITY_TAX
        for t in range(n + 1):
            if t > 0:
                growth = np.exp(shocks[:, t - 1, j])
                if k == "fii":
                    div = value * fii_yield_m
                    value = value * growth  # retorno total do cenário
                    # o rendimento já está dentro do retorno total; reinvestido, vira custo
                    basis = basis + div
                else:
                    value = value * growth
            value = value + c[t]
            basis = basis + c[t]
            total_net[:, t] += value - tax * np.clip(value - basis, 0, None)
    return total_net, params


def _reasons(key: str, inp: SimInput, prof: str) -> str:
    m = inp.months
    if key == "tesouro_selic":
        return "Resgate em qualquer dia útil e risco do governo federal: é a base de segurança. Se surgir uma emergência, você não precisa vender nada no prejuízo."
    if key == "cdb_liquidez":
        return "Rende o mesmo que o Tesouro Selic (100% do CDI), muitas vezes com aplicação mínima menor, e o FGC cobre até R$ 250 mil por banco."
    if key == "lci_lca":
        equiv = 90 / (1 - ir_rate(m * 30))
        return f"Isenta de IR: com {_months_text(m)}, 90% do CDI isento equivale a cerca de {equiv:.0f}% do CDI de um CDB. Só use dinheiro que pode ficar parado na carência."
    if key == "tesouro_prefixado":
        return "Trava a taxa de hoje até uma data. Escolha um vencimento perto da data do seu objetivo e leve até o fim: assim a oscilação do caminho não importa."
    if key == "tesouro_ipca":
        real = f"{inp.ipca_real_rate:g}".replace(".", ",")
        return f"Garante ganho acima da inflação por muitos anos (premissa: IPCA + {real}% ao ano). Protege o poder de compra até a data do seu objetivo."
    if key == "fii":
        return "Renda mensal isenta de IR e exposição a imóveis com pouco dinheiro. Prefira um ETF de FIIs ou fundos grandes e diversificados."
    if key == "acoes_br":
        extra = " Você disse que manteria o investimento numa queda, o que é essencial aqui." if inp.drop_reaction != "vender" else " Fica pequena porque vender na queda transforma oscilação em perda."
        return f"Com {_months_text(m)} há tempo para atravessar quedas. Pelo ETF você vira sócio de dezenas de empresas e não depende de acertar uma.{extra}"
    if key == "exterior":
        return "Diversifica fora da economia brasileira e do real. Se o Brasil for mal, essa parte tende a segurar o resultado."
    return ""


def simulate(inp: SimInput) -> dict:
    n = inp.months
    prof = profile(inp)
    bucket = "curto" if inp.goal == "reserva" else horizon_bucket(n)
    if inp.goal == "reserva":
        alloc_pct = dict(RESERVE_SPLIT)
    else:
        alloc_pct = dict(ALLOCATIONS[bucket][prof["key"]])
        if bucket == "curto" and n < 12:  # LCI/LCA tem carência de 9 a 12 meses
            alloc_pct = {"tesouro_selic": 50, "cdb_liquidez": 50}

    contribs: dict[str, np.ndarray] = {}

    def add(key: str, month: int, amount: float):
        if amount <= 0:
            return
        contribs.setdefault(key, np.zeros(n + 1))[month] += amount

    steps: list[dict] = []
    warnings: list[str] = []
    reserve_info = None
    initial_left = inp.initial
    reserve_left = 0.0
    if inp.goal != "reserva" and not inp.has_reserve:
        if inp.monthly_expenses and inp.monthly_expenses > 0:
            target = 6 * inp.monthly_expenses
        else:
            target = inp.initial
            warnings.append("Sem os gastos mensais, consideramos todo o valor inicial como reserva. Informe os gastos para um cálculo melhor.")
        from_initial = min(inp.initial, target)
        initial_left = inp.initial - from_initial
        reserve_left = target - from_initial
        for k, p in RESERVE_SPLIT.items():
            add(k, 0, from_initial * p / 100)
        months_to_fill = math.ceil(reserve_left / inp.monthly) if reserve_left > 0 and inp.monthly > 0 else 0
        reserve_info = {"target": round(target, 2), "months_to_fill": months_to_fill}
        steps.append({
            "title": "1. Monte a reserva de emergência",
            "text": f"Antes de buscar rendimento, guarde {brl(target)} (6 meses de gastos) em Tesouro Selic ou CDB de liquidez diária. "
            + (f"Com seus aportes, ela fica pronta em {months_to_fill} {'mês' if months_to_fill == 1 else 'meses'}; só depois o dinheiro segue para o objetivo." if months_to_fill else "O valor inicial já cobre a reserva."),
        })
    for k, p in alloc_pct.items():
        add(k, 0, initial_left * p / 100)
    for t in range(1, n + 1):
        amount = inp.monthly
        if reserve_left > 0:
            to_res = min(amount, reserve_left)
            reserve_left -= to_res
            for k, p in RESERVE_SPLIT.items():
                add(k, t, to_res * p / 100)
            amount -= to_res
        for k, p in alloc_pct.items():
            add(k, t, amount * p / 100)

    goal_text = {"reserva": "sua reserva de emergência", "objetivo": f"seu objetivo em {_months_text(n)}", "aposentadoria": f"o longo prazo ({_months_text(n)})"}[inp.goal]
    steps.append({
        "title": f"{len(steps) + 1}. Divida o dinheiro de {goal_text}",
        "text": "Cada parte tem um papel: segurança, proteção da inflação ou crescimento. A divisão abaixo é por tipo de investimento; o produto específico você escolhe comparando taxa, prazo e garantia.",
    })
    steps.append({
        "title": f"{len(steps) + 1}. Automatize e revise uma vez por ano",
        "text": "Programe o aporte mensal para o dia do salário. Uma vez por ano, confira se a divisão continua parecida com a planejada e ajuste com os aportes novos, sem vender no susto.",
    })

    # Projeção
    fixed_keys = [k for k in contribs if k not in VARIABLE_ORDER]
    var_contribs = {k: v for k, v in contribs.items() if k in VARIABLE_ORDER}
    fixed_net = np.zeros(n + 1)
    by_product = []
    for k in fixed_keys:
        g, net = _fixed_income_path(k, contribs[k], inp)
        fixed_net += net
        by_product.append({"key": k, "invested": round(float(contribs[k].sum()), 2), "gross": round(float(g[-1]), 2), "net": round(float(net[-1]), 2),
                           "annual_rate_pct": round(_annual_rate(k, inp), 2)})
    var_net, var_params = _variable_paths(var_contribs, inp) if var_contribs else (np.zeros((PATHS, n + 1)), {})
    for k in var_contribs:
        by_product.append({"key": k, "invested": round(float(var_contribs[k].sum()), 2), "expected_annual_pct": var_params[k]["expected_annual_pct"],
                           "volatility_pct": var_params[k]["volatility_pct"]})
    total = fixed_net[None, :] + var_net
    p10, p50, p90 = np.percentile(total, [10, 50, 90], axis=0)

    flows = np.zeros(n + 1)
    flows[0] = inp.initial
    flows[1:] = inp.monthly
    _, poup = _fixed_income_path("poupanca", flows, inp)
    invested = np.cumsum(flows)
    ipca_m = (1 + inp.rates["ipca_12m"] / 100) ** (1 / 12) - 1
    deflator = (1 + ipca_m) ** np.arange(n + 1)

    points = sorted({*range(0, n + 1, 12 if n > 24 else 1), n})
    timeline = [{"month": t, "invested": round(float(invested[t]), 2), "p10": round(float(p10[t]), 2), "p50": round(float(p50[t]), 2),
                 "p90": round(float(p90[t]), 2), "poupanca": round(float(poup[t]), 2)} for t in points]
    loss_prob = float(np.mean(total[:, -1] < invested[-1])) if var_contribs else 0.0

    total_inv = float(invested[-1]) or 1.0
    fill = reserve_info["months_to_fill"] if reserve_info else 0
    if fill >= n and inp.goal != "reserva" and reserve_info:
        warnings.append("Com esse aporte, a reserva de emergência ocupa o prazo inteiro. Tudo bem: ela é o primeiro objetivo. Aumente o aporte ou o prazo para sobrar para o resto.")
    allocation = []
    for k, p in alloc_pct.items():
        prod = BY_KEY[k]
        allocation.append({
            "key": k, "label": prod["label"], "pct": p, "group": prod["group"], "risk": prod["risk"],
            "initial_amount": round(initial_left * p / 100, 2), "monthly_amount": round(inp.monthly * p / 100, 2),
            "monthly_from": fill + 1 if fill else 1,
            "liquidity": prod["liquidity"], "guarantee": prod["guarantee"], "tax": prod["tax"], "reason": _reasons(k, inp, prof["key"]),
        })
    if var_contribs and loss_prob > 0.05:
        warnings.append(f"Em {loss_prob * 100:.0f}% dos cenários o resultado final fica abaixo do total aportado. É o preço da parte em renda variável.")
    if "tesouro_selic" in alloc_pct and 0 < initial_left * alloc_pct["tesouro_selic"] / 100 < 150 and inp.monthly * alloc_pct["tesouro_selic"] / 100 < 150:
        warnings.append("Valores abaixo de cerca de R$ 150 podem não comprar a fração mínima do Tesouro Selic; use o CDB de liquidez diária até juntar.")
    if n >= 120:
        warnings.append("Em prazos longos, supor CDI e IPCA constantes é uma simplificação forte. Use a projeção como ordem de grandeza.")

    years = n / 12
    return {
        "profile": prof,
        "horizon": bucket,
        "steps": steps,
        "reserve": reserve_info,
        "allocation": allocation,
        "projection": {
            "months": n,
            "invested": round(total_inv, 2),
            "p10": round(float(p10[-1]), 2),
            "median": round(float(p50[-1]), 2),
            "p90": round(float(p90[-1]), 2),
            "median_today_money": round(float(p50[-1] / deflator[-1]), 2),
            "poupanca": round(float(poup[-1]), 2),
            "vs_poupanca": round(float(p50[-1] - poup[-1]), 2),
            "loss_probability": round(loss_prob, 3),
            "has_variable": bool(var_contribs),
            "by_product": by_product,
            "timeline": timeline,
            "years": round(years, 1),
        },
        "assumptions": {
            "selic": inp.rates["selic"], "cdi": inp.rates["cdi"], "ipca_12m": inp.rates["ipca_12m"],
            "poupanca": round(poupanca_annual(inp.rates["selic"]), 2),
            "ipca_real_rate": inp.ipca_real_rate,
            "prefixado_rate": inp.prefixado_rate if inp.prefixado_rate is not None else round(inp.rates["cdi"] - 1.0, 2),
            "variable": {k: {"premium_over_cdi": (inp.equity_premium if k == "acoes_br" and inp.equity_premium is not None else VARIABLE_DEFAULTS[k][0]),
                             "volatility_pct": VARIABLE_DEFAULTS[k][1] * 100} for k in VARIABLE_ORDER},
            "rates_as_of": inp.rates.get("series", {}).get("cdi", {}).get("as_of"),
            "rates_stale": inp.rates.get("stale", False),
            "scenarios": PATHS if var_contribs else 0,
        },
        "warnings": warnings,
        "disclaimer": DISCLAIMER,
    }
