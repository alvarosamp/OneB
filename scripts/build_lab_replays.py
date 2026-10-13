"""Gera os replays guiados do Laboratório da Academia a partir de dias reais (Dukascopy M5).

    python scripts/build_lab_replays.py

Cada replay é um dia escolhido por critério objetivo (não "a dedo"), com legendas
geradas a partir do que aconteceu nas barras. Saída pequena, versionada em
app/academy_replays/ (fora de "data", que o .dockerignore exclui), para o servidor de produção não precisar do HD externo.
"""
from __future__ import annotations

import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "app" / "academy_replays"
MARKET = Path(r"D:\OneB\market-data")
SOURCES = {
    "NAS100": MARKET / "dukascopy-nas100-2019-2026/normalized/NAS100_M5_2019-03-01_2026-09-26.csv.gz",
    "XAUUSD": MARKET / "dukascopy-xau-2019-2026/normalized/XAUUSD_M5_2019-03-01_2026-09-26.csv.gz",
    "SPX500": MARKET / "dukascopy-spx500-2019-2026/normalized/SPX500_M5_2019-03-01_2026-09-26.csv.gz",
    "EURUSD": MARKET / "dukascopy-eurusd-2019-2026/normalized/EURUSD_M5_2019-03-01_2026-09-26.csv.gz",
}
EVENTS = ROOT / "configs" / "events" / "macro_events_2019_2026.json"
BRT = pd.Timedelta(hours=-3)  # Brasil sem horário de verão desde 2019


def load(asset: str) -> pd.DataFrame:
    path = SOURCES[asset]
    if not path.exists():  # durante a reconstrução o arquivo antigo fica com outro nome
        path = path.with_name(path.name + ".pre_reverify")
    d = pd.read_csv(path, compression="gzip")
    d.index = pd.to_datetime(d["timestamp"], utc=True)
    return d[["open", "high", "low", "close", "spread_close"]]


def hhmm(ts: pd.Timestamp) -> str:
    return (ts + BRT).strftime("%H:%M")


def br(x: float, digits: int) -> str:
    """Número no formato brasileiro (5.331,25)."""
    return f"{x:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def pct(x: float) -> str:
    return f"{x * 100:+.2f}%".replace(".", ",")


def session(d: pd.DataFrame, day, start: str, end: str, tz: str) -> pd.DataFrame:
    """Barras do pregão no horário local da praça (respeita o horário de verão de lá)."""
    zone = ZoneInfo(tz)
    lo = pd.Timestamp(f"{day} {start}").tz_localize(zone).tz_convert("UTC")
    hi = pd.Timestamp(f"{day} {end}").tz_localize(zone).tz_convert("UTC")
    return d[(d.index >= lo) & (d.index < hi)]


def sessions(d: pd.DataFrame, start: str, end: str, tz: str, since: str = "2025-01-01") -> dict:
    days = sorted({ts.date() for ts in d.index if ts >= pd.Timestamp(since, tz="UTC") and ts.weekday() < 5})
    expected = (pd.Timestamp(f"2000-01-01 {end}") - pd.Timestamp(f"2000-01-01 {start}")) / pd.Timedelta(minutes=5)
    out = {}
    for day in days:
        s = session(d, day, start, end, tz)
        if len(s) >= 0.9 * expected:
            out[day] = s
    return out


def opening_range(s: pd.DataFrame, bars: int) -> tuple[float, float]:
    first = s.iloc[:bars]
    return float(first["high"].max()), float(first["low"].min())


def bars_json(s: pd.DataFrame, digits: int) -> list[dict]:
    return [{"t": int(ts.timestamp() * 1000), "o": round(r.open, digits), "h": round(r.high, digits),
             "l": round(r.low, digits), "c": round(r.close, digits)} for ts, r in s.iterrows()]


def build(slug, title, asset, label, context, s, captions, summary, digits, hint):
    spread = float(np.median(s["spread_close"]))
    return {"slug": slug, "title": title, "asset": asset, "label": label, "date": str(s.index[0].date()),
            "timezone": "Horário de Brasília", "spread": round(spread, digits + 1), "digits": digits,
            "summary": summary, "hint": hint, "context_bars": len(context),
            "bars": bars_json(pd.concat([context, s]), digits),
            "captions": [{"at": len(context) + i, "text": t} for i, t in captions]}


def nas_trend_and_range(d: pd.DataFrame) -> list[dict]:
    days = sessions(d, "09:30", "16:00", "America/New_York")
    stats = []
    for day, s in days.items():
        rng = s["high"].max() - s["low"].min()
        body = abs(s["close"].iloc[-1] - s["open"].iloc[0])
        stats.append((day, body / rng if rng else 0, rng))
    df = pd.DataFrame(stats, columns=["day", "efficiency", "range"])
    big = df[df["range"] >= df["range"].quantile(0.5)]
    trend_day = big.sort_values("efficiency").iloc[-1]["day"]
    normal = df[(df["range"] >= df["range"].quantile(0.3)) & (df["range"] <= df["range"].quantile(0.7))]
    range_day = normal.sort_values("efficiency").iloc[0]["day"]
    out = []
    for kind, day in (("tendencia", trend_day), ("lateral", range_day)):
        s = days[day]
        context = d[(d.index < s.index[0])].iloc[-36:]
        hi, lo = opening_range(s, 6)
        caps = [(0, f"Abertura do pregão de Nova York às {hhmm(s.index[0])}. Observe os primeiros 30 minutos antes de decidir."),
                (5, f"Faixa dos primeiros 30 min: máxima {br(hi, 1)}, mínima {br(lo, 1)}. Pause e escreva: o que faria você comprar, vender ou esperar?")]
        after = s.iloc[6:]
        up = after.index[after["close"] > hi]
        down = after.index[after["close"] < lo]
        first_break = min([x for x in (up[:1].tolist() + down[:1].tolist())], default=None)
        if first_break is not None:
            i = s.index.get_loc(first_break)
            side = "acima da máxima" if first_break in up else "abaixo da mínima"
            caps.append((i, f"{hhmm(first_break)}: fechamento {side} da faixa inicial. Rompimento ou armadilha? Onde ficaria o stop?"))
            ref = hi if first_break in up else lo
            later = s.iloc[i + 1:i + 13]
            back = later.index[(later["close"] < ref) if first_break in up else (later["close"] > ref)]
            if len(back):
                j = s.index.get_loc(back[0])
                caps.append((j, f"{hhmm(back[0])}: o preço voltou para dentro da faixa. Quem comprou o rompimento está perdendo."))
        change = s["close"].iloc[-1] / s["open"].iloc[0] - 1
        rng = s["high"].max() - s["low"].min()
        caps.append((len(s) - 1, f"Fechamento: {pct(change)} no dia, amplitude de {br(rng, 0)} pontos. Compare com o seu plano."))
        caps.sort()
        if kind == "tendencia":
            out.append(build("nasdaq-dia-de-tendencia", "Nasdaq: dia de tendência", "NAS100", "Nasdaq 100 (CFD)", context, s, caps,
                             "Um dos pregões de 2025–2026 em que o preço andou mais numa só direção em relação à amplitude do dia.", 1,
                             "Em dia de tendência, esperar a confirmação custa pouco; brigar contra a direção custa caro."))
        else:
            out.append(build("nasdaq-dia-lateral", "Nasdaq: dia lateral", "NAS100", "Nasdaq 100 (CFD)", context, s, caps,
                             "Um pregão de amplitude comum em que o preço terminou perto de onde começou: rompimentos tendem a falhar.", 1,
                             "Dia lateral é onde o “sem setup” mais protege capital."))
    return out


def gold_london_fakeout(d: pd.DataFrame) -> list[dict]:
    days = sessions(d, "08:00", "13:00", "Europe/London")
    # Só faixas iniciais de tamanho pelo menos mediano: faixa minúscula não ensina nada.
    min_range = float(np.median([np.subtract(*opening_range(s, 12)) for s in days.values()]))
    best = None
    for day, s in days.items():
        hi, lo = opening_range(s, 12)  # primeira hora de Londres
        if hi - lo < min_range:
            continue
        after = s.iloc[12:]
        up = after.index[after["close"] > hi]
        if not len(up):
            continue
        i = s.index.get_loc(up[0])
        later = s.iloc[i + 1:i + 13]
        below = later.index[later["close"] < lo]
        if len(below):
            score = (hi - s["low"].iloc[i:].min()) / (hi - lo)
            if best is None or score > best[0]:
                best = (score, day, i, s.index.get_loc(below[0]), hi, lo)
    if best is None:
        return []
    _, day, i, j, hi, lo = best
    s = days[day]
    context = d[d.index < s.index[0]].iloc[-36:]
    caps = [(0, f"Abertura de Londres às {hhmm(s.index[0])}. O ouro costuma ganhar volume agora."),
            (11, f"Faixa da primeira hora: máxima {br(hi, 2)}, mínima {br(lo, 2)}. Pause: o que você faria num rompimento?"),
            (i, f"{hhmm(s.index[i])}: fechou acima da máxima da faixa. Parece compra…"),
            (j, f"{hhmm(s.index[j])}: atravessou a faixa inteira e fechou abaixo da mínima. Rompimento falso."),
            (len(s) - 1, f"Fim da manhã de Londres: {pct(s['close'].iloc[-1] / s['open'].iloc[0] - 1)}. O setup “Gold Fakeout” tenta operar esse padrão; nos nossos testes, depois de custos, ele não teve vantagem.")]
    return [build("ouro-rompimento-falso-londres", "Ouro: rompimento falso em Londres", "XAUUSD", "Ouro (XAU/USD)", context, s, caps,
                  "O dia de 2025–2026 com o rompimento falso mais forte na abertura de Londres (maior queda após romper a máxima da primeira hora).", 2,
                  "Um padrão bonito no gráfico não é uma estratégia: precisa sobreviver a custos e a muitos dias.")]


EVENT_LABEL = {"CPI": "CPI (inflação)", "NFP": "payroll (emprego)"}


def event_day(d: pd.DataFrame, asset: str, label: str, kind: str, digits: int, slug: str, title: str) -> list[dict]:
    """O evento de 2025-2026 com o maior movimento em 30 min (critério objetivo), das 2 h antes às 2 h depois."""
    spec = json.loads(EVENTS.read_text(encoding="utf-8"))["events"][kind]
    hh, mm = map(int, spec["time_et"].split(":"))
    best = None
    for day in spec["dates"]:
        if day < "2025-01-01":
            continue
        t0 = pd.Timestamp(f"{day} {hh:02d}:{mm:02d}").tz_localize(ZoneInfo("America/New_York")).tz_convert("UTC")
        w = d[(d.index >= t0 - pd.Timedelta(hours=2)) & (d.index < t0 + pd.Timedelta(hours=2))]
        if len(w) < 44 or t0 not in w.index:
            continue
        before = w[w.index < t0]["close"].iloc[-1]
        after = w[w.index < t0 + pd.Timedelta(minutes=30)]["close"].iloc[-1]
        move = abs(after / before - 1)
        if best is None or move > best[0]:
            best = (move, t0, w)
    if best is None:
        return []
    _, t0, w = best
    i0 = w.index.get_loc(t0)
    context, s = w.iloc[:i0], w.iloc[i0:]
    before = context["close"].iloc[-1]
    first5 = s["close"].iloc[0] / before - 1
    p30 = s["close"].iloc[5] / before - 1
    # A pausa de decisão fica no último candle ANTES da divulgação (índice -1 relativo ao evento).
    caps = [(-1, f"Às {hhmm(t0)} sai o {EVENT_LABEL[kind]}. Pause: com posição aberta, onde estaria o seu stop? Você entraria antes, ou esperaria?"),
            (0, f"{hhmm(t0)}: saiu o {EVENT_LABEL[kind]}. Primeiros 5 min: {pct(first5)}, várias vezes o movimento de um dia normal."),
            (5, f"Meia hora depois: {pct(p30)} desde antes da divulgação. Nos nossos dados, o movimento típico nesses 30 minutos é de 3 a 4 vezes o normal."),
            (len(s) - 1, f"Duas horas depois: {pct(s['close'].iloc[-1] / before - 1)}. A direção dos primeiros minutos se manteve? No estudo do OneB, ela não é confiável.")]
    return [build(slug, title, asset, label, context, s, caps,
                  f"O {EVENT_LABEL[kind]} de 2025–2026 com o maior movimento na primeira meia hora.", digits,
                  "Em dia de divulgação forte, reduzir o tamanho ou esperar a primeira meia hora protege mais do que adivinhar a direção.")]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    replays = (nas_trend_and_range(load("NAS100")) + gold_london_fakeout(load("XAUUSD"))
               + event_day(load("SPX500"), "SPX500", "S&P 500 (CFD)", "CPI", 1, "sp500-dia-de-cpi", "S&P 500: dia de CPI")
               + event_day(load("EURUSD"), "EURUSD", "Euro/dólar", "NFP", 5, "eurusd-dia-de-payroll", "Euro/dólar: dia de payroll"))
    index = []
    for r in replays:
        (OUT / f"{r['slug']}.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
        index.append({k: r[k] for k in ("slug", "title", "asset", "label", "date", "summary")} | {"bars": len(r["bars"])})
        print(r["slug"], r["date"], len(r["bars"]), "barras", len(r["captions"]), "legendas")
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
