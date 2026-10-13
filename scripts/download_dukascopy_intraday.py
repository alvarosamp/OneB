"""Download public Dukascopy M1 bid/ask data and create normalized gzip CSVs.

This source provides XAUUSD spot and USA 100 Technical Index CFDs, not CME GC
or NQ futures. The distinction is recorded in the generated manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

import sys as _sys

_sys.path.insert(0, str(Path(__file__).resolve().parent))
import dukascopy_canary as canary  # noqa: E402
import dukascopy_feed as feed  # noqa: E402

INSTRUMENTS = {
    "XAUUSD": {"dukascopy": "xauusd", "description": "Dukascopy spot gold"},
    "NAS100": {"dukascopy": "usatechidxusd", "description": "Dukascopy USA 100 Technical Index CFD"},
    "SPX500": {"dukascopy": "usa500idxusd", "description": "Dukascopy USA 500 Index CFD"},
    "EURUSD": {"dukascopy": "eurusd", "description": "Dukascopy EUR/USD spot"},
    "WTI": {"dukascopy": "lightcmdusd", "description": "Dukascopy WTI light crude CFD"},
}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _easter(year: int) -> date:
    """Domingo de Páscoa (algoritmo de Meeus/Butcher)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


# Lacunas verificadas NA FONTE (pedido de um único dia volta vazio). Lista explícita:
# qualquer outro dia faltando continua reprovando o bloco.
# 07/10/2026: a antiga entrada xauusd:ask 2019-12-12 era falsa (3 provas sem cache: 288 barras).
# Lacunas só entram em source_gaps.json, com evidência; nenhuma fica fixa no código.
KNOWN_SOURCE_GAPS: dict[tuple[str, str], set[date]] = {}


def _market_closed(day: date) -> bool:
    """Dias úteis em que o ouro spot legitimamente não negocia (ou quase nada)."""
    if (day.month, day.day) in {(12, 24), (12, 25), (12, 26), (12, 31), (1, 1), (1, 2)}:
        return True
    return day == _easter(day.year) - timedelta(days=2)  # Sexta-feira Santa


def missing_weekdays(path: Path, start: str, end: str, min_bars: int = 100, known_gaps: set | None = None) -> list[str]:
    """Dias úteis do intervalo com menos de `min_bars` barras (exceto feriados conhecidos).

    O dukascopy-node grava arquivo PARCIAL quando o servidor devolve HTTP 429 no
    meio do bloco; olhar só as pontas do arquivo deixa buracos internos passarem.
    """
    if not path.exists() or path.stat().st_size <= 100:
        return ["arquivo_ausente"]
    try:
        stamps = pd.to_datetime(pd.read_csv(path, usecols=["timestamp"])["timestamp"], unit="ms", utc=True)
    except Exception:
        return ["arquivo_ilegivel"]
    counts = stamps.dt.date.value_counts()
    out = []
    day = date.fromisoformat(start)
    last = date.fromisoformat(end)
    while day < last:
        if day.weekday() < 5 and not _market_closed(day) and day not in (known_gaps or set()) and counts.get(day, 0) < min_bars:
            out.append(day.isoformat())
        day += timedelta(days=1)
    return out


def _csv_covers(path: Path, start: str, end: str) -> bool:
    return not missing_weekdays(path, start, end)


SOURCE_GAPS_FILE = "source_gaps.json"
_recorded_gaps: dict[str, dict] = {}


def _gap_key(instrument: str, price_type: str) -> str:
    return f"{INSTRUMENTS[instrument]['dukascopy']}:{price_type}"


def _load_recorded_gaps(raw_dir: Path) -> None:
    path = raw_dir / SOURCE_GAPS_FILE
    if path.exists():
        _recorded_gaps.update(json.loads(path.read_text(encoding="utf-8")))


def _record_gap(raw_dir: Path, instrument: str, price_type: str, day: date,
                evidence: str = "pedido de um único dia devolveu arquivo vazio (0 linhas)") -> None:
    key = _gap_key(instrument, price_type)
    _recorded_gaps.setdefault(key, {})[day.isoformat()] = {
        "evidence": evidence,
        "verified_at": date.today().isoformat(),
    }
    (raw_dir / SOURCE_GAPS_FILE).write_text(json.dumps(_recorded_gaps, ensure_ascii=False, indent=2), encoding="utf-8")


def _known_gaps(instrument: str, price_type: str) -> set:
    static = KNOWN_SOURCE_GAPS.get((INSTRUMENTS[instrument]["dukascopy"], price_type), set())
    recorded = {date.fromisoformat(d) for d in _recorded_gaps.get(_gap_key(instrument, price_type), {})}
    return static | recorded


def _npx(instrument: str, price_type: str, timeframe: str, start: str, end: str, directory: Path, stem: str, attempts: int) -> Path | None:
    """Um bloco do feed Dukascopy (dukascopy_feed) com tentativas. Devolve o arquivo ou None.

    O nome ficou do tempo do `npx dukascopy-node`, abandonado em 09/10/2026 (ver dukascopy_feed).
    """
    path = directory / f"{stem}.csv"
    for attempt in range(attempts):
        path.unlink(missing_ok=True)
        try:
            return feed.write_csv(INSTRUMENTS[instrument]["dukascopy"], price_type, timeframe, start, end, path, volumes=True)
        except feed.FeedUnavailable:
            time.sleep(min(RETRY_WAIT_MAX_SECONDS, 5 * 2**attempt))
    return None


PROBE_CONFIRMATIONS = 3
PROBE_SPACING_SECONDS = 60


def _cache_files(cache_dir: Path, instrument: str, price_type: str, day: date) -> list[Path]:
    """Entradas de cache de um dia: o .bi5 do feed e, de downloads antigos, o JSON do dukascopy-node."""
    files = []
    suffix = f"%2F{price_type.upper()}%2F{day.year}%2F{day.month}%2F{day.day}.json"
    if cache_dir.exists():
        files += list(cache_dir.glob(f"candles%2Fminute%2F*{suffix}"))
    bi5 = (feed.CACHE / INSTRUMENTS[instrument]["dukascopy"].upper() / str(day.year) / f"{day.month - 1:02d}"
           / f"{day.day:02d}" / f"{price_type.upper()}_candles_min_1.bi5")
    return files + ([bi5] if bi5.exists() else [])


def _probe_day_rows(instrument: str, price_type: str, timeframe: str, day: date, directory: Path) -> int | None:
    """Pedido isolado de um dia, SEM cache. Devolve o número de barras, ou None se o pedido falhou."""
    try:
        rows = feed.candles(INSTRUMENTS[instrument]["dukascopy"], price_type, timeframe, day.isoformat(),
                            (day + timedelta(days=1)).isoformat(), use_cache=False)
    except feed.FeedUnavailable:
        return None
    # Feriado: o feed preenche horas paradas com barras planas (ex.: NAS100 em 04/07/2023:
    # 288 barras, 92% planas). Só conta barra com negociação (máxima > mínima).
    return 0 if rows.empty else int((rows["high"] > rows["low"]).sum())


def _confirmed_day_rows(instrument: str, price_type: str, timeframe: str, day: date, directory: Path) -> int | None:
    """Barras do dia só quando PROBE_CONFIRMATIONS provas sem cache, espaçadas, concordam.

    Sob limite de requisições o dukascopy-node pode devolver arquivo vazio com sucesso;
    uma prova isolada não distingue isso de uma lacuna real (ex.: EURUSD 02/04/2025).
    Devolve None se as provas discordam ou falham: o dia NÃO vira lacuna.
    """
    counts = []
    for attempt in range(PROBE_CONFIRMATIONS):
        if attempt:
            time.sleep(PROBE_SPACING_SECONDS)
        # Vazio só conta se a fonte estiver respondendo dados para um dia conhecido.
        canary.wait_until_healthy()
        rows = _probe_day_rows(instrument, price_type, timeframe, day, directory)
        if rows is None:
            return None
        if rows >= 100:
            return rows  # dados existem: não é lacuna nem pregão curto
        counts.append(rows)
    return counts[0] if len(set(counts)) == 1 else None


def _rows(path: Path | None) -> pd.DataFrame:
    if path is None or not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])


def _download_range(
    instrument: str, price_type: str, timeframe: str, start: str, end: str, raw_dir: Path, stem: str
) -> Path:
    """Baixa um bloco; se falhar, divide em semanas e depois em dias.

    Um dia só vira lacuna da fonte se o pedido DAQUELE dia isolado voltar vazio,
    e fica registrado em source_gaps.json com a evidência.
    """
    path = raw_dir / f"{stem}.csv"
    if not missing_weekdays(path, start, end, known_gaps=_known_gaps(instrument, price_type)):
        return path
    if _npx(instrument, price_type, timeframe, start, end, raw_dir, stem, attempts=2) and             not missing_weekdays(path, start, end, known_gaps=_known_gaps(instrument, price_type)):
        return path

    pieces_dir = raw_dir / "pieces"
    pieces_dir.mkdir(exist_ok=True)
    frames = []
    cursor, final = date.fromisoformat(start), date.fromisoformat(end)
    while cursor < final:
        week_end = min(final, cursor + timedelta(days=7))
        week_stem = f"{stem}__{cursor.isoformat()}"
        week = _npx(instrument, price_type, timeframe, cursor.isoformat(), week_end.isoformat(), pieces_dir, week_stem, attempts=2)
        if week is not None and not missing_weekdays(week, cursor.isoformat(), week_end.isoformat(), known_gaps=_known_gaps(instrument, price_type)):
            frames.append(_rows(week))
        else:
            day = cursor
            while day < week_end:
                if day.weekday() < 5 and not _market_closed(day) and day not in _known_gaps(instrument, price_type):
                    day_path = _npx(instrument, price_type, timeframe, day.isoformat(), (day + timedelta(days=1)).isoformat(),
                                    pieces_dir, f"{stem}__d{day.isoformat()}", attempts=4)
                    rows = _rows(day_path)
                    if day_path is None or len(rows) < 100:
                        # Vazio ou curto pode ser falha (cache envenenado / limite de requisições):
                        # apaga o cache do dia e exige provas sem cache que concordem.
                        for cached in _cache_files(raw_dir.parent / "cache", instrument, price_type, day):
                            cached.unlink(missing_ok=True)
                        confirmed = _confirmed_day_rows(instrument, price_type, timeframe, day, pieces_dir)
                        if confirmed is None:
                            raise RuntimeError(f"Dia {day} sem resposta e as provas não confirmam lacuna da fonte: {stem}")
                        if confirmed >= 100:
                            day_path = _npx(instrument, price_type, timeframe, day.isoformat(), (day + timedelta(days=1)).isoformat(),
                                            pieces_dir, f"{stem}__d{day.isoformat()}", attempts=4)
                            rows = _rows(day_path)
                            if len(rows) < 100:
                                raise RuntimeError(f"Dia {day}: a prova tem {confirmed} barras mas o download não: {stem}")
                        elif confirmed == 0:
                            _record_gap(raw_dir.parent.parent, instrument, price_type, day,  # raiz do output
                                        evidence=f"{PROBE_CONFIRMATIONS} pedidos isolados sem cache, espaçados {PROBE_SPACING_SECONDS}s, devolveram 0 linhas")
                        else:
                            # Pregão curto real (ex.: feriado nos EUA para índices): dados existem, só são poucos.
                            _record_gap(raw_dir.parent.parent, instrument, price_type, day,
                                        evidence=f"sessão curta na fonte: {confirmed} barras em {PROBE_CONFIRMATIONS} pedidos isolados sem cache")
                    frames.append(rows)
                day += timedelta(days=1)
        cursor = week_end
    combined = pd.concat([f for f in frames if not f.empty], ignore_index=True).drop_duplicates("timestamp").sort_values("timestamp")
    combined.to_csv(path, index=False)
    missing = missing_weekdays(path, start, end, known_gaps=_known_gaps(instrument, price_type))
    if missing:
        raise RuntimeError(f"Bloco incompleto mesmo após dividir: {path.name} sem {missing[:5]}")
    shutil.rmtree(pieces_dir, ignore_errors=True)
    return path


def download_side(
    instrument: str,
    price_type: str,
    timeframe: str,
    start: str,
    end: str,
    raw_dir: Path,
    chunk_days: int = 30,
) -> Path:
    label = timeframe.upper()
    destination = raw_dir / f"{instrument}_{price_type}_{label}_{start}_{end}.csv"
    if _csv_covers(destination, start, end):
        return destination
    chunk_dir = raw_dir / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    cursor = date.fromisoformat(start)
    final_date = date.fromisoformat(end)
    parts = []
    while cursor < final_date:
        chunk_end = min(final_date, cursor + timedelta(days=chunk_days))
        stem = f"{instrument}_{price_type}_{label}_{cursor.isoformat()}_{chunk_end.isoformat()}"
        parts.append(_download_range(instrument, price_type, timeframe, cursor.isoformat(), chunk_end.isoformat(), chunk_dir, stem))
        cursor = chunk_end
        time.sleep(2)
    frames = [pd.read_csv(part) for part in parts]
    combined = pd.concat(frames, ignore_index=True).drop_duplicates("timestamp").sort_values("timestamp")
    combined.to_csv(destination, index=False)
    return destination


def _read_side(path: Path, prefix: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    expected = {"timestamp", "open", "high", "low", "close", "volume"}
    if not expected <= set(frame.columns):
        raise ValueError(f"Esquema inesperado em {path}: {sorted(frame.columns)}")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    return frame.rename(columns={column: f"{prefix}_{column}" for column in ("open", "high", "low", "close", "volume")})


def normalize_pair(instrument: str, timeframe: str, bid_path: Path, ask_path: Path, output_dir: Path, start: str, end: str) -> tuple[Path, dict]:
    bid = _read_side(bid_path, "bid")
    ask = _read_side(ask_path, "ask")
    merged = bid.merge(ask, on="timestamp", how="inner", validate="one_to_one").sort_values("timestamp")
    for field in ("open", "high", "low", "close"):
        merged[field] = (merged[f"bid_{field}"] + merged[f"ask_{field}"]) / 2
    merged["volume"] = merged["bid_volume"].fillna(merged["ask_volume"]).fillna(0)
    merged["spread_open"] = merged["ask_open"] - merged["bid_open"]
    merged["spread_close"] = merged["ask_close"] - merged["bid_close"]
    columns = [
        "timestamp", "open", "high", "low", "close", "volume",
        "bid_open", "bid_high", "bid_low", "bid_close",
        "ask_open", "ask_high", "ask_low", "ask_close", "spread_open", "spread_close",
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{instrument}_{timeframe.upper()}_{start}_{end}.csv.gz"
    merged[columns].to_csv(destination, index=False, compression="gzip")
    positive_spread = merged["spread_open"].dropna()
    metadata = {
        "instrument": instrument,
        "description": INSTRUMENTS[instrument]["description"],
        "rows": int(len(merged)),
        "start": merged["timestamp"].min().isoformat() if len(merged) else None,
        "end": merged["timestamp"].max().isoformat() if len(merged) else None,
        "bid_rows": int(len(bid)),
        "ask_rows": int(len(ask)),
        "matched_ratio": round(float(len(merged) / max(len(bid), len(ask))), 6),
        "median_spread": round(float(positive_spread.median()), 6) if len(positive_spread) else None,
        "p95_spread": round(float(positive_spread.quantile(0.95)), 6) if len(positive_spread) else None,
        "output": str(destination.resolve()),
        "sha256": file_hash(destination),
    }
    return destination, metadata


def main() -> None:
    today = date.today()
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=Path(r"D:\OneB\market-data\dukascopy"))
    parser.add_argument("--start", default=(today - timedelta(days=365 * 3)).isoformat())
    parser.add_argument("--end", default=today.isoformat())
    parser.add_argument("--timeframe", choices=["m1", "m5"], default="m5")
    parser.add_argument("--instrument", action="append", choices=sorted(INSTRUMENTS), default=[])
    parser.add_argument(
        "--chunk-days",
        type=int,
        default=30,
        help="Days per downloader invocation. NAS100 is more reliable at 14 days than at 30.",
    )
    parser.add_argument("--batch-pause-ms", type=int, default=3000, help="Pausa entre requisições (subir se houver HTTP 429).")
    parser.add_argument("--retry-wait-max", type=int, default=30, help="Espera máxima (s) entre tentativas de um bloco.")
    args = parser.parse_args()
    global BATCH_PAUSE_MS, RETRY_WAIT_MAX_SECONDS
    BATCH_PAUSE_MS, RETRY_WAIT_MAX_SECONDS = args.batch_pause_ms, args.retry_wait_max
    instruments = args.instrument or list(INSTRUMENTS)
    raw_dir = args.output_root / "raw"
    normalized_dir = args.output_root / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    _load_recorded_gaps(args.output_root)
    records = []
    for instrument in instruments:
        if args.chunk_days < 1:
            raise ValueError("--chunk-days must be positive")
        bid = download_side(instrument, "bid", args.timeframe, args.start, args.end, raw_dir, args.chunk_days)
        ask = download_side(instrument, "ask", args.timeframe, args.start, args.end, raw_dir, args.chunk_days)
        _, metadata = normalize_pair(instrument, args.timeframe, bid, ask, normalized_dir, args.start, args.end)
        metadata["raw_bid_sha256"] = file_hash(bid)
        metadata["raw_ask_sha256"] = file_hash(ask)
        records.append(metadata)
    manifest = {
        "source": "Dukascopy public historical feed via dukascopy-node",
        "source_pages": {
            "XAUUSD": "https://www.dukascopy-node.app/instrument/xauusd",
            "NAS100": "https://www.dukascopy-node.app/instrument/usatechidxusd",
        },
        "warning": "XAUUSD spot and NAS100 CFD are not CME GC/NQ futures; results cannot be relabeled as futures evidence.",
        "timeframe": args.timeframe.upper(),
        "date_from": args.start,
        "date_to_exclusive": args.end,
        "chunk_days": args.chunk_days,
        "datasets": records,
        "source_gaps": _recorded_gaps,
        "source_gaps_fraction_of_weekdays": {
            key: round(len(days) / max(1, sum(1 for i in range((date.fromisoformat(args.end) - date.fromisoformat(args.start)).days)
                                              if (date.fromisoformat(args.start) + timedelta(days=i)).weekday() < 5)), 5)
            for key, days in _recorded_gaps.items()
        },
        "source_gaps_warning": "Acima de 1% de dias úteis vazios a base deve ser tratada como suspeita.",
        "source_gaps_static": {f"{k[0]}:{k[1]}": sorted(d.isoformat() for d in v) for k, v in KNOWN_SOURCE_GAPS.items()},
    }
    manifest_path = args.output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
