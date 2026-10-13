"""Candles diários (d1) bid/ask da Dukascopy para o teste de tendência (tsmom_v1).

    python scripts/download_dukascopy_daily.py            # universo do pré-registro
    python scripts/download_dukascopy_daily.py eurusd xauusd

Grava em D:/OneB/market-data/dukascopy-daily (HD externo). Retomável: instrumento
com arquivo normalizado é pulado. Um arquivo vazio NÃO é aceito como "sem dados":
o instrumento falha e é refeito depois (lição do cache envenenado de 07/10/2026).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.setups import load_preregistered  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dukascopy_canary as canary  # noqa: E402
import dukascopy_feed as feed  # noqa: E402

OUT = Path(r"D:\OneB\market-data\dukascopy-daily")


def _fetch_range(instrument: str, side: str, start: str, end: str, directory: Path, timeframe: str = "d1",
                 reuse_min_rows: int = 200) -> pd.DataFrame | None:
    stem = f"{instrument}_{side}_{start[:4]}" if timeframe == "d1" else f"{instrument}_{side}_{start[:7]}_{timeframe}"
    path = directory / f"{stem}.csv"
    convert = (lambda f: daily_from_hourly(f)) if timeframe == "h1" else trading_bars
    if path.exists() and path.stat().st_size > 0 and pd.Timestamp(end) < pd.Timestamp.now():
        cached = convert(pd.read_csv(path))
        if len(cached) >= reuse_min_rows and covers(cached, start, end):  # já baixado completo numa passada anterior
            return cached
    path.unlink(missing_ok=True)
    try:
        feed.write_csv(instrument, side, timeframe, start, end, path, volumes=False)
    except feed.FeedUnavailable:
        return None
    return convert(pd.read_csv(path))


def daily_from_hourly(frame: pd.DataFrame) -> pd.DataFrame:
    """Dia UTC (mesma fronteira das velas d1 da fonte) a partir das barras de 1 hora com negociação."""
    bars = trading_bars(frame)
    if bars.empty:
        return bars
    day = pd.to_datetime(bars["timestamp"], unit="ms", utc=True).dt.floor("D").rename("day")
    g = bars.groupby(day)
    out = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(), "close": g["close"].last()})
    # Milissegundos desde a época, explícito (asi8 muda de unidade entre versões do pandas).
    out["timestamp"] = (out.index - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(milliseconds=1)
    return out.reset_index(drop=True)[["timestamp", "open", "high", "low", "close"]]


# Ano em que a Dukascopy começa a ter candles do instrumento (metadados do dukascopy-node,
# startDayForMinuteCandles). Antes dele, ano vazio é esperado; depois, ano vazio é falha
# de pedido (limite de requisições), nunca "lacuna": o ask de 2011 do usa500idxusd veio
# cheio enquanto o bid do mesmo ano veio vazio, e em 2021 o inverso.
# A avaliação começa em 2013 e cada instrumento precisa de ~312 pregões de histórico:
# de 2012 em diante nenhum ano pode faltar.
STRICT_FROM_YEAR = 2012
DROPPED: dict[str, list[str]] = {}
MISSING: dict[tuple[str, str], list[int]] = {}
FROM_HOURLY: dict[str, list[int]] = {}

SOURCE_START_YEAR = {
    "usa500idxusd": 2011, "usatechidxusd": 2011, "usa30idxusd": 2013, "deuidxeur": 2013, "gbridxgbp": 2011,
    "jpnidxjpy": 2011, "fraidxeur": 2011, "ausidxaud": 2014, "hkgidxhkd": 2013, "eusidxeur": 2014,
    "xauusd": 2003, "xagusd": 2003, "lightcmdusd": 2011, "brentcmdusd": 2010, "gascmdusd": 2012, "coppercmdusd": 2012,
    "eurusd": 2003, "gbpusd": 2003, "usdjpy": 2003, "audusd": 2003, "usdcad": 2003, "usdchf": 2003, "nzdusd": 2003,
}


def covers(frame: pd.DataFrame, start: str, end: str, max_gap: int = 5) -> bool:
    """Nenhum trecho de mais de `max_gap` dias úteis sem barra entre start e end (bordas incluídas).
    Feriados somam 1 ou 2 dias; um mês faltando soma ~21."""
    if frame.empty:
        return False
    days = set(pd.to_datetime(frame["timestamp"], unit="ms", utc=True).dt.tz_localize(None).dt.normalize())
    run = 0
    for d in pd.bdate_range(start, pd.Timestamp(end) - pd.Timedelta(days=1)):
        run = 0 if d in days else run + 1
        if run > max_gap:
            return False
    return True


def _hourly_year(instrument: str, side: str, year: int, lo: str, hi: str, directory: Path, attempts: int,
                 leading_empty_ok: bool = False) -> pd.DataFrame | None:
    """Dias montados a partir do h1, pedindo mês a mês (o pedido anual de h1 também volta pela metade).
    No ano de início do instrumento, meses vazios antes do primeiro dado são esperados."""
    parts = []
    for month in range(1, 13):
        mlo = max(lo, f"{year}-{month:02d}-01")
        mhi = min(hi, f"{year + 1}-01-01" if month == 12 else f"{year}-{month + 1:02d}-01")
        if mlo >= mhi:
            continue
        got = None
        for attempt in range(attempts):
            g = _fetch_range(instrument, side, mlo, mhi, directory, timeframe="h1", reuse_min_rows=1)
            if g is not None and len(g) and covers(g, mlo, mhi):
                got = g
                break
            if g is not None and len(g) and leading_empty_ok and not parts:
                got = g  # primeiro mês com dados: o instrumento começa no meio dele
                break
            if g is not None and not len(g) and leading_empty_ok and not parts and attempt >= 1:
                break  # ainda antes do início do instrumento na fonte
            time.sleep(min(120, 10 * 2**attempt))
        if got is None and leading_empty_ok and not parts:
            continue
        if got is None:
            return None
        parts.append(got)
    return pd.concat(parts, ignore_index=True).drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True) if parts else None


def _fetch(instrument: str, side: str, start: str, end: str, directory: Path, attempts: int = 5) -> pd.DataFrame:
    """Baixa ano a ano (um pedido longo para depois do primeiro ano e ainda grava o arquivo).
    A partir do ano de início do instrumento na fonte, todo ano precisa vir com dados
    (>= 200 pregões, exceto o ano de início e o último); senão o instrumento falha e é
    refeito numa próxima passada."""
    first_year = SOURCE_START_YEAR[instrument]
    frames = []
    for year in range(int(start[:4]), int(end[:4]) + 1):
        lo = max(start, f"{year}-01-01")
        hi = min(end, f"{year + 1}-01-01")
        short_ok = year in (first_year, int(end[:4]))
        frame = None
        def ok(got: pd.DataFrame | None) -> bool:
            if got is None:
                return False
            if year < first_year:
                return True
            if year == first_year:  # o instrumento começa no meio do ano na fonte
                return len(got) > 0 and covers(got, str(pd.to_datetime(got["timestamp"].min(), unit="ms").date()), hi)
            return (short_ok or len(got) >= 200) and covers(got, lo, hi)

        # A vela diária da fonte tem buracos reais (ex.: usatechidxusd bid 2017 vazio no d1 e
        # completo no h1). Duas tentativas no d1; depois o dia é montado a partir do h1.
        for attempt in range(2):
            got = _fetch_range(instrument, side, lo, hi, directory)
            if ok(got):
                frame = got
                break
            time.sleep(15)
        if frame is None and year >= first_year:
            got = _hourly_year(instrument, side, year, lo, hi, directory, attempts, leading_empty_ok=year == first_year)
            if ok(got):
                frame = got
                FROM_HOURLY.setdefault(f"{instrument}:{side}", []).append(year)
        if frame is None or len(frame) == 0:
            # Ano vazio/incompleto só é aceito com a fonte saudável; senão foi bloqueio.
            canary.wait_until_healthy()
            got = _fetch_range(instrument, side, lo, hi, directory)
            if ok(got) and (len(got) or year < first_year):
                frame = got
        if frame is None and year < STRICT_FROM_YEAR:
            # Antes de 2012 (fora do que a avaliação de 2013+ precisa) um ano ausente na fonte
            # encerra o trecho antigo: ele é descartado e registrado, nunca emendado.
            DROPPED.setdefault(f"{instrument}:{side}", []).append(f"dados antes de {year + 1} descartados ({year} ausente na fonte)")
            frames = []
            continue
        if frame is None:
            # Ano ausente num lado só é reconstruído a partir do outro lado em main(); ausente
            # nos dois lados, o instrumento falha.
            MISSING.setdefault((instrument, side), []).append(year)
            continue
        if len(frame):
            frames.append(frame)
        time.sleep(1)
    if not frames:
        raise RuntimeError(f"{instrument} {side}: nenhum dado")
    return pd.concat(frames, ignore_index=True).drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)


def fill_side(target: pd.DataFrame, other: pd.DataFrame, years: list[int], sign: int) -> tuple[pd.DataFrame, float]:
    """Reconstrói anos ausentes de um lado (bid ou ask) a partir do outro, deslocando pelo
    spread mediano observado nos dias em que os dois lados existem. Muda só o custo do
    spread naquele ano; a direção do preço vem do lado observado."""
    both = target.merge(other, on="timestamp", suffixes=("_t", "_o"))
    spread = float((sign * (both["close_t"] - both["close_o"])).median())
    years_of = pd.to_datetime(other["timestamp"], unit="ms", utc=True).dt.year
    rows = other[years_of.isin(years).to_numpy()].copy()
    for col in ("open", "high", "low", "close"):
        rows[col] = rows[col] + sign * spread
    return pd.concat([target, rows], ignore_index=True).sort_values("timestamp").reset_index(drop=True), spread


def trading_bars(frame: pd.DataFrame) -> pd.DataFrame:
    """Só barras com negociação: a fonte preenche fins de semana e dias parados com barras planas."""
    days = pd.to_datetime(frame["timestamp"], unit="ms", utc=True).dt.tz_localize(None)
    flat = (frame["high"] == frame["low"]) & (frame["open"] == frame["close"])
    return frame[(days.dt.weekday < 5).to_numpy() & ~flat.to_numpy()].reset_index(drop=True)


def audit(frame: pd.DataFrame) -> dict:
    """Buracos de dados (não feriados): maior sequência de dias úteis sem barra e pregões por ano completo."""
    days = pd.to_datetime(frame["timestamp"], unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
    first, last = days.min(), days.max()
    weekdays = pd.bdate_range(first, last)
    present = set(days)
    missing = [d for d in weekdays if d not in present]
    run = longest = 0
    for d in weekdays:
        run = run + 1 if d not in present else 0
        longest = max(longest, run)
    per_year = days.dt.year.value_counts()
    full_years = range(first.year + 1, last.year)  # o primeiro e o último ano podem ser parciais
    min_year = min((int(per_year.get(y, 0)) for y in full_years), default=None)
    ret = frame["close"].pct_change()
    return {"first": str(first.date()), "last": str(last.date()), "rows": int(len(frame)),
            "missing_weekdays": len(missing), "missing_fraction": round(len(missing) / max(1, len(weekdays)), 5),
            "max_gap_weekdays": int(longest), "min_full_year_rows": min_year,
            "missing_sample": [str(d.date()) for d in missing[:10]],
            "big_moves": [{"date": str(days.iloc[i].date()), "return": round(float(ret.iloc[i]), 4)}
                          for i in ret.index[ret.abs() > 0.20]]}


def complete(info: dict, end: str) -> bool:
    """Regra de qualidade do pré-registro tsmom_v1 (emenda de 07/10/2026) + o arquivo precisa chegar ao fim
    pedido (sob HTTP 429 o dukascopy-node grava só os primeiros anos e sai com sucesso)."""
    reaches_end = pd.Timestamp(info["last"]) >= pd.Timestamp(end) - pd.Timedelta(days=10)
    return reaches_end and info["max_gap_weekdays"] <= 5 and (info["min_full_year_rows"] is None or info["min_full_year_rows"] >= 200)


def fail(manifest: dict, path: Path, instrument: str, reason: str) -> None:
    """Falha fica no manifesto (o teste exclui e divulga o motivo); a próxima passada tenta de novo."""
    print(f"FALHA {instrument}: {reason}", flush=True)
    manifest[instrument] = {"failed": reason, "checked_at": date.today().isoformat()}
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    spec, spec_sha = load_preregistered("tsmom_v1")
    universe = [i for group in ("equity_index", "commodity", "fx") for i in spec["universe"][group]]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instruments", nargs="*", default=universe)
    args = parser.parse_args()
    raw, norm = OUT / "raw", OUT / "normalized"
    raw.mkdir(parents=True, exist_ok=True)
    norm.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    start, end = spec["data"]["from"], spec["data"]["to_exclusive"]
    for instrument in args.instruments:
        target = norm / f"{instrument}_D1.csv.gz"
        if target.exists():
            print(f"{instrument} já baixado", flush=True)
            continue
        try:
            bid = _fetch(instrument, "bid", start, end, raw)
            ask = _fetch(instrument, "ask", start, end, raw)
        except RuntimeError as exc:
            fail(manifest, manifest_path, instrument, str(exc))
            continue
        miss_bid, miss_ask = MISSING.get((instrument, "bid"), []), MISSING.get((instrument, "ask"), [])
        if set(miss_bid) & set(miss_ask):
            fail(manifest, manifest_path, instrument, f"anos {sorted(set(miss_bid) & set(miss_ask))} ausentes nos dois lados (d1 e h1)")
            continue
        imputed = {}
        if miss_ask:
            ask, sp = fill_side(ask, bid, miss_ask, +1)
            imputed["ask"] = {"years": miss_ask, "median_spread": round(sp, 6)}
        if miss_bid:
            bid, sp = fill_side(bid, ask, miss_bid, -1)
            imputed["bid"] = {"years": miss_bid, "median_spread": round(sp, 6)}
        common = max(bid["timestamp"].min(), ask["timestamp"].min())
        bid, ask = bid[bid["timestamp"] >= common], ask[ask["timestamp"] >= common]
        if abs(len(bid) - len(ask)) > 0.02 * max(len(bid), len(ask)):
            fail(manifest, manifest_path, instrument, f"bid {len(bid)} e ask {len(ask)} linhas não batem")
            continue
        merged = bid.merge(ask, on="timestamp", suffixes=("_bid", "_ask"), how="inner")
        out = pd.DataFrame({"timestamp": merged["timestamp"]})
        for col in ("open", "high", "low", "close"):
            out[col] = (merged[f"{col}_bid"] + merged[f"{col}_ask"]) / 2
        out["spread"] = merged["close_ask"] - merged["close_bid"]
        out = out[out["close"] > 0].sort_values("timestamp").drop_duplicates("timestamp")
        info = audit(out)
        if not complete(info, end):
            fail(manifest, manifest_path, instrument, f"cobertura insuficiente {info['first']}..{info['last']} buraco {info['max_gap_weekdays']}")
            continue
        info["imputed_from_other_side"] = imputed
        info["days_built_from_h1"] = {k: v for k, v in FROM_HOURLY.items() if k.startswith(instrument + ":")}
        info["bid_rows"], info["ask_rows"] = int(len(bid)), int(len(ask))
        info["dropped"] = {k: v for k, v in DROPPED.items() if k.startswith(instrument + ":")}
        info["downloaded_at"] = date.today().isoformat()
        out.to_csv(target, index=False, compression="gzip")
        manifest[instrument] = info
        manifest["_spec_sha256"] = spec_sha
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{instrument} {info['first']}..{info['last']} linhas={info['rows']} faltando={info['missing_fraction']:.2%} "
              f"saltos>20%={len(info['big_moves'])}", flush=True)
        time.sleep(5)


if __name__ == "__main__":
    main()
