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
from datetime import date

import numpy as np

from app.brasil.outlook import pick_title
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
    ipca_real_rate: float | None = None  # None = taxa do Tesouro IPCA+ de hoje
    prefixado_rate: float | None = None  # None = taxa do Tesouro Prefixado de hoje
    equity_premium: float | None = None
    rates: dict = field(default_factory=dict)
    focus: dict | None = None  # app.brasil.outlook.focus(): Selic e IPCA esperados por ano
    tesouro: dict | None = None  # app.brasil.outlook.tesouro(): taxas dos títulos hoje
    start: date = field(default_factory=date.today)


# Sem o Tesouro disponível: premissas abaixo das taxas de 10/2026.
FALLBACK_IPCA_REAL = 6.5
FALLBACK_PREFIX_DISCOUNT = 1.0  # prefixado = CDI de hoje − 1 p.p.


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


def _add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    return date(d.year + y, m + 1, 1)


def market_context(inp: SimInput) -> dict:
    """Taxas anuais (%) mês a mês no prazo do simulador e os títulos do Tesouro usados.

    Com o Focus: Selic e IPCA saem do valor de hoje e vão, em linha reta, até a mediana
    esperada para dezembro de cada ano; depois do último ano do Focus, ficam constantes.
    O CDI acompanha a Selic com a diferença de hoje. Sem o Focus: tudo constante.
    """
    n = max(inp.months, 1)
    r = inp.rates
    t = np.arange(n) + 0.5  # meio de cada mês
    years = (inp.focus or {}).get("years") or []
    if years:
        xs, selic_pts, ipca_pts = [0.0], [r["selic"]], [r["ipca_12m"]]
        for row in sorted(years, key=lambda y: y["year"]):
            to_dec = (row["year"] - inp.start.year) * 12 + (12 - inp.start.month)
            if to_dec <= 0:
                continue
            xs.append(float(to_dec))
            selic_pts.append(row["selic"])
            ipca_pts.append(row["ipca"])
        selic = np.interp(t, xs, selic_pts)
        ipca = np.interp(t, xs, ipca_pts)
        mode = "focus"
    else:
        selic = np.full(n, float(r["selic"]))
        ipca = np.full(n, float(r["ipca_12m"]))
        mode = "constante"
    cdi = selic - (r["selic"] - r["cdi"])

    target = _add_months(inp.start, inp.months)
    ipca_title = pick_title(inp.tesouro, "Tesouro IPCA+", target)
    prefix_title = pick_title(inp.tesouro, "Tesouro Prefixado", target)
    if inp.ipca_real_rate is not None:
        ipca_real, ipca_src, ipca_title = inp.ipca_real_rate, "informada por você", None
    elif ipca_title:
        ipca_real, ipca_src = ipca_title["buy_rate"], f"Tesouro IPCA+ {ipca_title['maturity'][:4]} hoje"
    else:
        ipca_real, ipca_src = FALLBACK_IPCA_REAL, "premissa: Tesouro indisponível agora"
    if inp.prefixado_rate is not None:
        prefix, prefix_src, prefix_title = inp.prefixado_rate, "informada por você", None
    elif prefix_title:
        prefix, prefix_src = prefix_title["buy_rate"], f"Tesouro Prefixado {prefix_title['maturity'][:4]} hoje"
    else:
        prefix, prefix_src = round(r["cdi"] - FALLBACK_PREFIX_DISCOUNT, 2), "premissa: Tesouro indisponível agora"
    return {
        "mode": mode, "selic": selic, "cdi": cdi, "ipca": ipca,
        "ipca_real": ipca_real, "ipca_real_source": ipca_src, "ipca_title": ipca_title,
        "prefixado": prefix, "prefixado_source": prefix_src, "prefixado_title": prefix_title,
        "last_focus_year": max((y["year"] for y in years), default=None),
    }


def _rate_path(key: str, ctx: dict) -> np.ndarray:
    """Taxa nominal anual (%) de um produto de renda fixa, mês a mês."""
    p = BY_KEY[key]
    model = p["yield_model"]
    if model == "poupanca":
        return np.array([poupanca_annual(s) for s in ctx["selic"]])
    if model == "selic":
        return ctx["selic"] - 0.05  # Tesouro Selic rende levemente abaixo da Selic meta (Selic over)
    if model == "cdi":
        return ctx["cdi"] * p.get("cdi_pct", 1.0)
    if model == "prefixado":
        return np.full(len(ctx["selic"]), float(ctx["prefixado"]))
    if model == "ipca_plus":
        return ((1 + ctx["ipca"] / 100) * (1 + ctx["ipca_real"] / 100) - 1) * 100
    raise ValueError(key)


def _fixed_income_path(key: str, contrib: np.ndarray, ctx: dict) -> tuple[np.ndarray, np.ndarray]:
    """Valor bruto e líquido (se resgatado) ao fim de cada mês 0..n.

    Cada aporte é um lote com a sua própria idade para a tabela regressiva do IR.
    """
    n = len(contrib) - 1
    p = BY_KEY[key]
    rm = (1 + _rate_path(key, ctx) / 100) ** (1 / 12) - 1
    custody = p.get("custody")
    lots = np.zeros(n + 1)
    basis = np.zeros(n + 1)
    gross = np.zeros(n + 1)
    net = np.zeros(n + 1)
    for t in range(n + 1):
        if t > 0:
            lots[:t] *= 1 + rm[t - 1]
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


def _variable_paths(contribs: dict[str, np.ndarray], inp: SimInput, ctx: dict, seed: int = 7) -> tuple[np.ndarray, dict]:
    """Patrimônio líquido de IR por cenário (PATHS × n+1) somando as classes de renda variável.

    Retorno esperado de cada mês = CDI daquele mês + prêmio da classe."""
    keys = [k for k in VARIABLE_ORDER if k in contribs]
    n = len(next(iter(contribs.values()))) - 1
    if not keys:
        return np.zeros((PATHS, n + 1)), {}
    cdi, ipca = ctx["cdi"][:n], ctx["ipca"][:n]
    idx = [VARIABLE_ORDER.index(k) for k in keys]
    params = {}
    mus = np.zeros((n, len(keys)))
    sigmas = []
    for j, k in enumerate(keys):
        prem, vol = VARIABLE_DEFAULTS[k]
        if k == "acoes_br" and inp.equity_premium is not None:
            prem = inp.equity_premium
        expected = cdi + prem
        params[k] = {"expected_annual_pct": round(float(expected.mean()), 2) if n else 0.0, "volatility_pct": round(vol * 100, 1)}
        sm = vol / math.sqrt(12)
        mus[:, j] = np.log(1 + expected / 100) / 12 - sm * sm / 2
        sigmas.append(sm)
    corr = CORRELATION[np.ix_(idx, idx)]
    cov = np.outer(sigmas, sigmas) * corr
    rng = np.random.default_rng(seed)
    noise = rng.multivariate_normal(np.zeros(len(keys)), cov, size=(PATHS, n)) if n else np.zeros((PATHS, 0, len(keys)))
    shocks = noise + mus[None, :, :]
    total_net = np.zeros((PATHS, n + 1))
    # FII: a parte acima da inflação vem como rendimento mensal isento (reinvestido, entra
    # no custo); o resto é valorização da cota, tributada em 20% na venda.
    fii_real = np.clip((1 + (cdi + VARIABLE_DEFAULTS["fii"][0]) / 100) / (1 + ipca / 100) - 1, 0, None)
    fii_yield_m = (1 + fii_real) ** (1 / 12) - 1
    for j, k in enumerate(keys):
        c = contribs[k]
        value = np.zeros(PATHS)
        basis = np.zeros(PATHS)
        tax = FII_TAX if k == "fii" else EQUITY_TAX
        for t in range(n + 1):
            if t > 0:
                growth = np.exp(shocks[:, t - 1, j])
                if k == "fii":
                    div = value * fii_yield_m[t - 1]
                    value = value * growth  # retorno total do cenário
                    # o rendimento já está dentro do retorno total; reinvestido, vira custo
                    basis = basis + div
                else:
                    value = value * growth
            value = value + c[t]
            basis = basis + c[t]
            total_net[:, t] += value - tax * np.clip(value - basis, 0, None)
    return total_net, params


def _pct(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _reasons(key: str, inp: SimInput, ctx: dict) -> str:
    m = inp.months
    if key == "tesouro_selic":
        return "Resgate em qualquer dia útil e risco do governo federal: é a base de segurança. Se surgir uma emergência, você não precisa vender nada no prejuízo."
    if key == "cdb_liquidez":
        return "Rende o mesmo que o Tesouro Selic (100% do CDI), muitas vezes com aplicação mínima menor, e o FGC cobre até R$ 250 mil por banco."
    if key == "lci_lca":
        equiv = 90 / (1 - ir_rate(m * 30))
        return f"Isenta de IR: com {_months_text(m)}, 90% do CDI isento equivale a cerca de {equiv:.0f}% do CDI de um CDB. Só use dinheiro que pode ficar parado na carência."
    if key == "tesouro_prefixado":
        return (f"Trava a taxa de hoje até uma data: {_pct(ctx['prefixado'])}% ao ano ({ctx['prefixado_source']}). "
                "Escolha um vencimento perto da data do seu objetivo e leve até o fim: assim a oscilação do caminho não importa.")
    if key == "tesouro_ipca":
        return (f"Garante ganho acima da inflação por muitos anos: IPCA + {_pct(ctx['ipca_real'])}% ao ano ({ctx['ipca_real_source']}). "
                "Protege o poder de compra até a data do seu objetivo, se você levar até o vencimento.")
    if key == "fii":
        return "Renda mensal isenta de IR e exposição a imóveis com pouco dinheiro. Prefira um ETF de FIIs ou fundos grandes e diversificados."
    if key == "acoes_br":
        extra = " Você disse que manteria o investimento numa queda, o que é essencial aqui." if inp.drop_reaction != "vender" else " Fica pequena porque vender na queda transforma oscilação em perda."
        return f"Com {_months_text(m)} há tempo para atravessar quedas. Pelo ETF você vira sócio de dezenas de empresas e não depende de acertar uma.{extra}"
    if key == "exterior":
        return "Diversifica fora da economia brasileira e do real. Se o Brasil for mal, essa parte tende a segurar o resultado."
    return ""


def _yearly_path(ctx: dict, start: date) -> list[dict]:
    """Média de cada ano do prazo (até 6 anos), para mostrar na tela."""
    out = []
    n = len(ctx["selic"])
    for i in range(0, min(n, 72), 12):
        sl = slice(i, min(i + 12, n))
        out.append({"year": i // 12 + 1, "from": _add_months(start, i).isoformat()[:7],
                    "selic": round(float(ctx["selic"][sl].mean()), 2), "cdi": round(float(ctx["cdi"][sl].mean()), 2),
                    "ipca": round(float(ctx["ipca"][sl].mean()), 2)})
    return out


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
    ctx = market_context(inp)
    fixed_keys = [k for k in contribs if k not in VARIABLE_ORDER]
    var_contribs = {k: v for k, v in contribs.items() if k in VARIABLE_ORDER}
    fixed_net = np.zeros(n + 1)
    by_product = []
    for k in fixed_keys:
        g, net = _fixed_income_path(k, contribs[k], ctx)
        fixed_net += net
        by_product.append({"key": k, "invested": round(float(contribs[k].sum()), 2), "gross": round(float(g[-1]), 2), "net": round(float(net[-1]), 2),
                           "annual_rate_pct": round(float(_rate_path(k, ctx).mean()), 2)})
    var_net, var_params = _variable_paths(var_contribs, inp, ctx) if var_contribs else (np.zeros((PATHS, n + 1)), {})
    for k in var_contribs:
        by_product.append({"key": k, "invested": round(float(var_contribs[k].sum()), 2), "expected_annual_pct": var_params[k]["expected_annual_pct"],
                           "volatility_pct": var_params[k]["volatility_pct"]})
    total = fixed_net[None, :] + var_net
    p10, p50, p90 = np.percentile(total, [10, 50, 90], axis=0)

    flows = np.zeros(n + 1)
    flows[0] = inp.initial
    flows[1:] = inp.monthly
    _, poup = _fixed_income_path("poupanca", flows, ctx)
    invested = np.cumsum(flows)
    deflator = np.concatenate([[1.0], np.cumprod((1 + ctx["ipca"][:n] / 100) ** (1 / 12))])

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
            "liquidity": prod["liquidity"], "guarantee": prod["guarantee"], "tax": prod["tax"], "reason": _reasons(k, inp, ctx),
        })
    if var_contribs and loss_prob > 0.05:
        warnings.append(f"Em {loss_prob * 100:.0f}% dos cenários o resultado final fica abaixo do total aportado. É o preço da parte em renda variável.")
    selic_min = min((t["min_investment"] for t in (inp.tesouro or {}).get("titles", []) if t["name"] == "Tesouro Selic"), default=200.0)
    if "tesouro_selic" in alloc_pct and 0 < initial_left * alloc_pct["tesouro_selic"] / 100 < selic_min and inp.monthly * alloc_pct["tesouro_selic"] / 100 < selic_min:
        warnings.append(f"A compra mínima do Tesouro Selic hoje é de cerca de {brl(selic_min)}. Até juntar esse valor, use o CDB de liquidez diária.")
    end_date = _add_months(inp.start, n)
    if ctx["mode"] == "constante" and n >= 120:
        warnings.append("A projeção do mercado (Focus) está indisponível agora: supomos o CDI e o IPCA de hoje constantes, uma simplificação forte em prazos longos.")
    elif ctx["mode"] == "focus" and ctx["last_focus_year"] and end_date.year > ctx["last_focus_year"]:
        warnings.append(f"Depois de {ctx['last_focus_year']}, último ano projetado pelo mercado, mantivemos a Selic em {_pct(ctx['selic'][-1])}% e o IPCA em "
                        f"{_pct(ctx['ipca'][-1])}% ao ano. Use a projeção como ordem de grandeza.")
    if ctx["ipca_title"] and "tesouro_ipca" in alloc_pct and end_date > date.fromisoformat(ctx["ipca_title"]["maturity"]):
        warnings.append("Seu prazo passa do vencimento mais longo do Tesouro IPCA+ à venda; supomos reinvestir na mesma taxa.")

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
            "ipca_real_rate": ctx["ipca_real"],
            "ipca_real_source": ctx["ipca_real_source"],
            "prefixado_rate": ctx["prefixado"],
            "prefixado_source": ctx["prefixado_source"],
            "rates_mode": ctx["mode"],
            "path": _yearly_path(ctx, inp.start),
            "focus_as_of": (inp.focus or {}).get("as_of"),
            "tesouro_as_of": (inp.tesouro or {}).get("as_of"),
            "variable": {k: {"premium_over_cdi": (inp.equity_premium if k == "acoes_br" and inp.equity_premium is not None else VARIABLE_DEFAULTS[k][0]),
                             "volatility_pct": VARIABLE_DEFAULTS[k][1] * 100} for k in VARIABLE_ORDER},
            "rates_as_of": inp.rates.get("series", {}).get("cdi", {}).get("as_of"),
            "rates_stale": inp.rates.get("stale", False),
            "scenarios": PATHS if var_contribs else 0,
        },
        "warnings": warnings,
        "disclaimer": DISCLAIMER,
    }
