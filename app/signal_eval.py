"""'Avaliar um sinal': lê o sinal como o cliente recebeu e mede a chance real de cada alvo.

Não diz se o sinal é bom ou ruim pela direção (nenhuma regra de direção passou nos testes do OneB).
Mede o que dá para medir: com AQUELE stop e AQUELES alvos, quantas vezes o alvo veio antes do stop
em entradas de hora em hora nos últimos 60 dias (barras de 5 min, spread da corretora, até 24 h), o
resultado médio por trade e o lote. O sinal só prova valor se o placar dele superar essa taxa-base.
"""
from __future__ import annotations

import math
import re
import unicodedata

import numpy as np
import pandas as pd

HORIZON_BARS = 288  # 24 h de barras de 5 min

ASSET_ALIASES = {
    "XAUUSD": ("xauusd", "xau/usd", "xau", "ouro", "gold", "gc"),
    "NAS100": ("nas100", "us100", "ustec", "nasdaq", "nq", "ndx", "tech100", "nas 100", "us 100"),
    "SPX500": ("spx500", "us500", "s&p500", "s&p 500", "s&p", "sp500", "spx", "es"),
    "EURUSD": ("eurusd", "eur/usd", "euro"),
}
LONG_WORDS = ("compra", "comprar", "comprado", "buy", "long", "alta")
SHORT_WORDS = ("venda", "vender", "vendido", "sell", "short", "baixa")
# ordem importa: rótulos mais longos antes ("stop loss" antes de "stop", "tp1" antes de "tp")
LABELS = [
    ("stop", r"stop\s*loss|stoploss|s/l|\bsl\b|\bstop\b|\bstp\b"),
    # "TP1", "Alvo 2": o dígito do número do alvo faz parte do rótulo; "TP 4186" não (o preço fica de fora)
    ("target", r"take\s*profit(?:\s*[1-9](?![\d.,]))?|\b(?:tp|alvos?|objetivos?|targets?|gain)(?:\s*[1-9](?![\d.,]))?\b"),
    ("entry", r"\bentrada\b|\bentry\b|\bpre[cç]o\b|\bzona\b|@"),
]
NUM = r"\d[\d.,]*\d|\d"


def _norm(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def _candidates(token: str) -> list[float]:
    """Leituras possíveis de um número escrito por humanos: '4.180,50', '4,180.50', '29,700', '4180.5'."""
    t = token.strip().strip(".,")
    out = set()
    if "," in t and "." in t:
        out.add(float(t.replace(".", "").replace(",", ".")) if t.rfind(",") > t.rfind(".") else float(t.replace(",", "")))
    elif "," in t:
        out.add(float(t.replace(",", ".")) if t.count(",") == 1 else float(t.replace(",", "")))
        if re.fullmatch(r"\d{1,3}(,\d{3})+", t):
            out.add(float(t.replace(",", "")))
    elif "." in t:
        if t.count(".") == 1:
            out.add(float(t))
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", t):
            out.add(float(t.replace(".", "")))
    else:
        out.add(float(t))
    return sorted(out)


def _pick(token: str, ref: float | None) -> float:
    cands = _candidates(token)
    if ref and ref > 0:
        return min(cands, key=lambda x: abs(math.log(x / ref)) if x > 0 else 1e9)
    return cands[-1]


def parse_signal(text: str, ref_prices: dict[str, float] | None = None) -> dict:
    """Ativo, direção, entrada, stop e alvos de um sinal em texto livre. `ref_prices` (preço atual por ativo)
    desfaz ambiguidades como '29,700'. Retorna {"error": ...} quando falta algo essencial."""
    q = _norm(text)
    asset = None
    for key, words in ASSET_ALIASES.items():
        if any(re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", q) for w in words):
            asset = key
            break
    if asset is None:
        return {"error": "Não reconheci o ativo. O OneB avalia ouro (XAUUSD), Nasdaq (US100), S&P 500 (US500) e euro/dólar."}
    is_long = any(re.search(rf"\b{w}\b", q) for w in LONG_WORDS)
    is_short = any(re.search(rf"\b{w}\b", q) for w in SHORT_WORDS)
    if is_long == is_short:
        return {"error": "Não ficou claro se o sinal é de compra ou de venda."}
    direction = "long" if is_long else "short"
    ref = (ref_prices or {}).get(asset)

    # tira o nome do ativo para os números do nome (US100, NAS100, US500) não virarem preço
    clean = q
    for w in sorted(ASSET_ALIASES[asset], key=len, reverse=True):
        clean = re.sub(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", " ", clean)
    marks = []
    for kind, pattern in LABELS:
        for m in re.finditer(pattern, clean):
            if not any(a <= m.start() < b for _, a, b in marks):
                marks.append((kind, m.start(), m.end()))
    marks.sort(key=lambda x: x[1])
    stop, targets, entry_nums, loose = None, [], [], []
    for m in re.finditer(NUM, clean):
        if re.fullmatch(r"\d", m.group()) and re.search(r"(tp|alvo|objetivo|target|gain)\s*$", clean[max(0, m.start() - 9):m.start()]):
            continue  # o "1" de "TP1"
        owner = None  # o rótulo mais próximo antes do número
        for kind, _, end in marks:
            if end <= m.start():
                owner = kind
        value = _pick(m.group(), ref)
        if owner == "stop":
            stop = value if stop is None else stop
        elif owner == "target":
            targets.append(value)
        elif owner == "entry":
            entry_nums.append(value)
        else:
            loose.append(value)  # número sem rótulo antes (ex.: "OURO COMPRA 4180 ...")
    if not entry_nums and loose:
        entry_nums = loose[:1]
    if not entry_nums:
        return {"error": "Não achei o preço de entrada.", "asset": asset, "direction": direction}
    if stop is None:
        return {"error": "Não achei o stop. Sinal sem stop não dá para avaliar: o risco é ilimitado.", "asset": asset, "direction": direction}
    if not targets:
        return {"error": "Não achei nenhum alvo (TP).", "asset": asset, "direction": direction}
    # zona de entrada ("4180 - 4182"): usa o meio; números absurdos (fora de 20% da entrada) são descartados
    entry = float(np.mean(entry_nums[:2]))
    near = lambda x: abs(x / entry - 1) < 0.2  # noqa: E731
    targets = [t for t in targets if near(t)]
    if not near(stop) or not targets:
        return {"error": "Os preços de stop ou alvo não batem com a entrada.", "asset": asset, "direction": direction}
    side = 1 if direction == "long" else -1
    if side * (entry - stop) <= 0:
        return {"error": f"O stop está do lado errado para uma {'compra' if side == 1 else 'venda'}.", "asset": asset, "direction": direction}
    bad = [t for t in targets if side * (t - entry) <= 0]
    if bad:
        return {"error": "Há alvo do lado errado da entrada.", "asset": asset, "direction": direction}
    targets = sorted(set(targets), key=lambda t: side * (t - entry))
    return {"asset": asset, "direction": direction, "entry": entry, "stop": stop, "targets": targets,
            "stop_distance": abs(entry - stop), "target_distances": [abs(t - entry) for t in targets],
            "target_r": [abs(t - entry) / abs(entry - stop) for t in targets]}


def _utc(m5: pd.DataFrame) -> pd.DataFrame:
    d = m5[["open", "high", "low", "close"]].dropna().copy()
    idx = pd.DatetimeIndex(d.index)
    d.index = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    return d[~d.index.duplicated()].sort_index()


def h1_atr(m5: pd.DataFrame) -> pd.Series:
    h = m5.resample("1h").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    prev = h["close"].shift()
    tr = pd.concat([h["high"] - h["low"], (h["high"] - prev).abs(), (h["low"] - prev).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    atr.index = atr.index + pd.Timedelta(hours=1)
    return atr.dropna()


def wilson(hits: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = hits / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, mid - half), min(1.0, mid + half)


def base_rates(m5: pd.DataFrame, direction: str, stop_atr: float, target_r: list[float], spread: float) -> dict:
    """Taxa-base: entradas de hora em hora nos dados, stop = stop_atr x ATR(14) do H1 da hora, alvos em R; até 24 h.
    Stop e alvo na mesma barra contam como stop; sem nenhum em 24 h, sai no fechamento (resultado em R)."""
    d = _utc(m5)
    atr = h1_atr(d)
    idx = d.index
    entries = np.where(idx.minute == 0)[0]
    entries = entries[entries + HORIZON_BARS < len(idx)]
    if len(entries) == 0:
        return {"n": 0, "targets": []}
    a = atr.reindex(idx[entries], method="ffill").to_numpy()
    span = (idx[entries + HORIZON_BARS] - idx[entries]).total_seconds() / 3600
    ok = np.isfinite(a) & (a > 0) & (span <= 72)
    entries, a = entries[ok], a[ok]
    side = 1 if direction == "long" else -1
    hi, lo, op, cl = (d[c].to_numpy() for c in ("high", "low", "open", "close"))
    entry = op[entries] + side * spread
    stop_dist = stop_atr * a
    out = []
    for r in target_r:
        state = np.zeros(len(entries))  # 0 aberto, 1 alvo, -1 stop
        for step in range(HORIZON_BARS):
            j = entries + step
            open_ = state == 0
            if not open_.any():
                break
            if side == 1:
                hit_stop, hit_tp = lo[j] <= entry - stop_dist, hi[j] >= entry + r * stop_dist
            else:
                hit_stop, hit_tp = hi[j] >= entry + stop_dist, lo[j] <= entry - r * stop_dist
            state[open_ & hit_stop] = -1
            state[open_ & hit_tp & ~hit_stop] = 1
        exit_r = side * (cl[entries + HORIZON_BARS] - entry) / stop_dist
        result = np.where(state == 1, r, np.where(state == -1, -1.0, exit_r))
        hits = int((state == 1).sum())
        out.append({"target_r": float(r), "n": int(len(entries)), "p_target": hits / len(entries) if len(entries) else None,
                    "ci95": wilson(hits, len(entries)), "p_stop": float((state == -1).mean()), "p_open_24h": float((state == 0).mean()),
                    "mean_r": float(result.mean()), "breakeven_p": 1 / (1 + r)})
    return {"n": int(len(entries)), "from": idx[entries[0]].isoformat() if len(entries) else None,
            "to": idx[entries[-1]].isoformat() if len(entries) else None, "targets": out}


def neutral(a: dict, b: dict) -> dict:
    """Média de compra e venda (mesmas entradas): a chance de um alvo sem saber a direção."""
    n = a["n"] + b["n"]
    hits = round(a["p_target"] * a["n"] + b["p_target"] * b["n"])
    return {"target_r": a["target_r"], "n": n, "p_target": hits / n if n else None, "ci95": wilson(hits, n),
            "p_stop": (a["p_stop"] + b["p_stop"]) / 2, "p_open_24h": (a["p_open_24h"] + b["p_open_24h"]) / 2,
            "mean_r": (a["mean_r"] + b["mean_r"]) / 2, "breakeven_p": a["breakeven_p"]}


def current_atr(m5: pd.DataFrame) -> float | None:
    atr = h1_atr(_utc(m5))
    return float(atr.iloc[-1]) if len(atr) else None


def resolve_signal(m5: pd.DataFrame, created_at: pd.Timestamp, direction: str, stop_dist: float, target_dists: list[float],
                   spread: float) -> dict | None:
    """Confere um sinal gravado como entrada a mercado na primeira barra depois do momento em que foi colado, com as
    DISTÂNCIAS do sinal (o preço do gráfico é o do futuro; o do sinal, o do CFD da corretora). Até 24 h.

    Para cada alvo: 'hit' / 'stop' (inclusive os dois na mesma barra) / 'expired' / 'open', e o resultado em R de
    quem saísse naquele alvo (+R no alvo, -1 no stop, o fechamento das 24 h se nenhum dos dois)."""
    d = _utc(m5)
    t0 = pd.Timestamp(created_at)
    t0 = t0.tz_localize("UTC") if t0.tzinfo is None else t0.tz_convert("UTC")
    # o momento gravado tem microssegundos e as barras podem estar em segundos: arredonda para cima
    i0 = d.index.searchsorted(t0.ceil("s").as_unit(d.index.unit))
    if i0 >= len(d):
        return None
    side = 1 if direction == "long" else -1
    entry = float(d["open"].iloc[i0]) + side * spread
    end = d.index[i0] + pd.Timedelta(hours=24)
    window = d[(d.index >= d.index[i0]) & (d.index < end)]
    complete = d.index[-1] >= end - pd.Timedelta(minutes=5)
    hi, lo = window["high"].to_numpy(), window["low"].to_numpy()
    exit_r = side * (float(window["close"].iloc[-1]) - entry) / stop_dist if complete else None
    results, r_out = [], []
    for td in target_dists:
        res = "expired" if complete else "open"
        for h, lw in zip(hi, lo):
            hit_stop = lw <= entry - stop_dist if side == 1 else h >= entry + stop_dist
            hit_tp = h >= entry + td if side == 1 else lw <= entry - td
            if hit_stop:
                res = "stop"
                break
            if hit_tp:
                res = "hit"
                break
        results.append(res)
        r_out.append(td / stop_dist if res == "hit" else -1.0 if res == "stop" else exit_r if res == "expired" else None)
    return {"results": results, "result_r": r_out, "ref_entry": entry, "entered_at": d.index[i0].isoformat()}
