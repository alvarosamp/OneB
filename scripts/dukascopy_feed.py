"""Leitor do feed histórico público da Dukascopy (datafeed.dukascopy.com, arquivos .bi5).

Substitui o `npx dukascopy-node`. A partir da 1.50 ele só usa jetta.dukascopy.com, que
desde 08/10/2026 responde 202 vazio com `x-amzn-waf-action: challenge` (desafio
antirrobô da AWS). Não contornamos o desafio: usamos o feed clássico, que responde a
um cliente comum, uma requisição por vez, com pausa e espera crescente em erro.

Arquivos (mês com base 0 na URL):
  minuto: {SYM}/{AAAA}/{MM}/{DD}/{BID|ASK}_candles_min_1.bi5   (tempo em s desde o início do dia)
  hora:   {SYM}/{AAAA}/{MM}/{BID|ASK}_candles_hour_1.bi5       (s desde o início do mês)
  dia:    {SYM}/{AAAA}/{BID|ASK}_candles_day_1.bi5             (s desde o início do ano)
Registro de 24 bytes, big-endian: tempo, abertura, fechamento, mínima, máxima (inteiros
em pontos) e volume (float, em milhões).

Regra de segurança: vazio só vale quando a fonte RESPONDEU (200 sem conteúdo ou 404).
Erro de rede, 202, 429 ou 5xx viram FeedUnavailable depois das tentativas, e nunca
"sem dados".
"""
from __future__ import annotations

import lzma
import struct
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

BASE = "https://datafeed.dukascopy.com/datafeed"
CACHE = Path(r"D:\OneB\market-data\dukascopy-feed-cache")
MIN_INTERVAL_SECONDS = 8.0
BACKOFF_SECONDS = (30, 60, 120, 300, 600, 900, 1800)  # queda de conexão: até ~1 h por arquivo
TIMEOUT_SECONDS = 60
COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]

# Casas decimais do inteiro de preço. Calibrado contra os arquivos já baixados em
# D:/OneB/market-data (scripts/calibrate_dukascopy_feed.py); instrumento fora da tabela falha.
DECIMALS = {
    "eurusd": 5, "gbpusd": 5, "audusd": 5, "nzdusd": 5, "usdcad": 5, "usdchf": 5, "usdjpy": 3,
    "xauusd": 3, "xagusd": 3,
    "usa500idxusd": 3, "usatechidxusd": 3, "usa30idxusd": 3, "deuidxeur": 3, "gbridxgbp": 3,
    "fraidxeur": 3, "jpnidxjpy": 3, "ausidxaud": 3, "hkgidxhkd": 3, "eusidxeur": 3,
    "lightcmdusd": 3, "brentcmdusd": 3, "gascmdusd": 4, "coppercmdusd": 4,
}

_last_request = 0.0
# Ritmo gratuito e respeitoso: uma requisição a cada MIN_INTERVAL_SECONDS. Um 429 (pedidos demais)
# pausa TUDO por RATE_LIMIT_PAUSES (15 min, 30 min, 60 min...) em vez de insistir.
RATE_LIMIT_PAUSES = (900, 1800, 3600, 3600, 3600, 3600)


class FeedUnavailable(RuntimeError):
    """A fonte não respondeu de forma conclusiva (rede, 202, 429, 5xx)."""


def _get(url: str) -> bytes:
    """Corpo do arquivo; b'' quando a fonte afirma que não há dados (404 ou 200 vazio)."""
    global _last_request
    last_error = ""
    errors = limited = 0
    while errors <= len(BACKOFF_SECONDS) and limited <= len(RATE_LIMIT_PAUSES):
        pause = MIN_INTERVAL_SECONDS - (time.monotonic() - _last_request)
        if pause > 0:
            time.sleep(pause)
        _last_request = time.monotonic()
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
                if response.status == 200:
                    return response.read()
                last_error = f"HTTP {response.status}"
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return b""
            last_error = f"HTTP {exc.code}"
            if exc.code == 429:
                if limited < len(RATE_LIMIT_PAUSES):
                    print(f"429 da Dukascopy: pausa de {RATE_LIMIT_PAUSES[limited] // 60} min", flush=True)
                    time.sleep(RATE_LIMIT_PAUSES[limited])
                limited += 1
                continue
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last_error = type(exc).__name__ + ": " + str(exc)[:120]
        if errors < len(BACKOFF_SECONDS):
            time.sleep(BACKOFF_SECONDS[errors])
        errors += 1
    raise FeedUnavailable(f"{url}: {last_error}")


def _records(raw: bytes) -> list[tuple]:
    if not raw:
        return []
    data = lzma.decompress(raw)
    if len(data) % 24:
        raise FeedUnavailable(f"arquivo truncado ({len(data)} bytes)")
    return list(struct.iter_unpack(">5if", data))


def _file(symbol: str, side: str, kind: str, year: int, month: int = 1, day: int = 1, *, complete: bool,
          use_cache: bool = True) -> pd.DataFrame:
    """Um arquivo do feed como DataFrame (timestamp em ms). Período já encerrado vai para o cache em D:."""
    sym, sd = symbol.upper(), side.upper()
    if kind == "min":
        rel, origin = f"{sym}/{year}/{month - 1:02d}/{day:02d}/{sd}_candles_min_1.bi5", datetime(year, month, day)
    elif kind == "hour":
        rel, origin = f"{sym}/{year}/{month - 1:02d}/{sd}_candles_hour_1.bi5", datetime(year, month, 1)
    else:
        rel, origin = f"{sym}/{year}/{sd}_candles_day_1.bi5", datetime(year, 1, 1)
    cached = CACHE / rel
    if complete and use_cache and cached.exists():
        raw = cached.read_bytes()
    else:
        raw = _get(f"{BASE}/{rel}")
        if complete and CACHE.parent.exists():
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(raw)  # inclusive vazio: a fonte respondeu de forma conclusiva
    recs = _records(raw)
    if not recs:
        return pd.DataFrame(columns=COLUMNS)
    scale = 10.0 ** -DECIMALS[symbol.lower()]
    base_ms = int(origin.replace(tzinfo=timezone.utc).timestamp() * 1000)
    frame = pd.DataFrame(recs, columns=["t", "open", "close", "low", "high", "volume"])
    out = pd.DataFrame({"timestamp": base_ms + frame["t"].astype("int64") * 1000})
    decimals = DECIMALS[symbol.lower()]
    for col in ("open", "high", "low", "close"):
        out[col] = (frame[col] * scale).round(decimals)
    out["volume"] = (frame["volume"].astype(float) * 1e6).round()
    return out[COLUMNS]


def _drop_flats(frame: pd.DataFrame) -> pd.DataFrame:
    """Sem negociação: o feed preenche com barra plana de volume zero."""
    flat = (frame["volume"] == 0) & (frame["high"] == frame["low"])
    return frame[~flat]


def _resample(frame: pd.DataFrame, minutes: int) -> pd.DataFrame:
    if frame.empty:
        return frame
    step = minutes * 60_000
    g = frame.groupby(frame["timestamp"] // step * step, sort=True)
    out = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                        "close": g["close"].last(), "volume": g["volume"].sum()})
    return out.rename_axis("timestamp").reset_index()[COLUMNS]


def _days(start: date, end: date):
    d = start
    while d < end:
        yield d
        d += timedelta(days=1)


def _months(start: date, end: date):
    y, m = start.year, start.month
    while date(y, m, 1) < end:
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def candles(instrument: str, side: str, timeframe: str, start: str, end: str, ignore_flats: bool = True,
            use_cache: bool = True) -> pd.DataFrame:
    """Velas [start, end) em UTC, como o dukascopy-node entregava: timestamp em ms, volume em unidades.

    m1/m5 vêm dos arquivos de minuto; h1 do arquivo do mês (mês corrente: dos minutos);
    d1 do arquivo do ano (ano corrente: das horas, por dia UTC).
    """
    if instrument.lower() not in DECIMALS:
        raise KeyError(f"{instrument}: casas decimais não calibradas (ver DECIMALS)")
    lo, hi = date.fromisoformat(start[:10]), date.fromisoformat(end[:10])
    today = datetime.now(timezone.utc).date()
    month_now = (today.year, today.month)
    frames: list[pd.DataFrame] = []
    if timeframe in ("m1", "m5"):
        for d in _days(lo, min(hi, today)):
            if d.weekday() == 5:  # sábado: a fonte não publica negociação
                continue
            frames.append(_file(instrument, side, "min", d.year, d.month, d.day, complete=True, use_cache=use_cache))
    elif timeframe == "h1":
        for y, m in _months(lo, hi):
            if (y, m) < month_now:
                frames.append(_file(instrument, side, "hour", y, m, complete=True, use_cache=use_cache))
            else:
                mins = [_file(instrument, side, "min", d.year, d.month, d.day, complete=True, use_cache=use_cache)
                        for d in _days(max(lo, date(y, m, 1)), min(hi, today)) if d.weekday() != 5]
                frames.append(_resample(_drop_flats(pd.concat(mins)) if mins else pd.DataFrame(columns=COLUMNS), 60))
    elif timeframe == "d1":
        for y in range(lo.year, hi.year + 1):
            if y < today.year:
                frames.append(_file(instrument, side, "day", y, complete=True, use_cache=use_cache))
            else:
                hours = candles(instrument, side, "h1", max(lo, date(y, 1, 1)).isoformat(), min(hi, today).isoformat(),
                                use_cache=use_cache)
                frames.append(_resample(hours, 1440))
    else:
        raise ValueError(f"timeframe sem suporte: {timeframe}")
    frames = [f for f in frames if not f.empty]
    frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)
    if ignore_flats and not frame.empty:
        frame = _drop_flats(frame)
    if timeframe == "m5":
        frame = _resample(frame, 5)
    lo_ms = int(datetime(lo.year, lo.month, lo.day, tzinfo=timezone.utc).timestamp() * 1000)
    hi_ms = int(datetime(hi.year, hi.month, hi.day, tzinfo=timezone.utc).timestamp() * 1000)
    frame = frame[(frame["timestamp"] >= lo_ms) & (frame["timestamp"] < hi_ms)]
    return frame.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)


def write_csv(instrument: str, side: str, timeframe: str, start: str, end: str, path: Path, volumes: bool = True) -> Path:
    """Grava o CSV no formato do dukascopy-node. FeedUnavailable propaga: nada é gravado."""
    frame = candles(instrument, side, timeframe, start, end)
    cols = COLUMNS if volumes else COLUMNS[:-1]
    path.parent.mkdir(parents=True, exist_ok=True)
    out = frame[cols].copy()
    out["timestamp"] = out["timestamp"].astype("int64")
    if volumes:
        out["volume"] = out["volume"].astype("int64")
    out.to_csv(path, index=False)
    return path
